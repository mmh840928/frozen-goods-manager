import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- 数据库初始化 ---
DB_PATH = "frozen_goods.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 产品表
    c.execute('''CREATE TABLE IF NOT EXISTS products 
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, stock REAL)''')
    
    # 客户表
    c.execute('''CREATE TABLE IF NOT EXISTS customers 
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    
    # 客户专属价格表
    c.execute('''CREATE TABLE IF NOT EXISTS customer_prices 
                 (customer_id INTEGER, product_id INTEGER, price REAL, 
                  PRIMARY KEY (customer_id, product_id))''')
    
    # 订单表
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER, 
                  quantity REAL, price_per_unit REAL, total_price REAL, 
                  order_date TEXT, payment_status TEXT, 
                  FOREIGN KEY(customer_id) REFERENCES customers(id), 
                  FOREIGN KEY(product_id) REFERENCES products(id))''')
    
    # 预置产品数据
    initial_products = [
        ("大双", 634), ("小双", 103), ("大张", 223), ("小张", 17), 
        ("金帝来", 59), ("热狗肠", 221), ("大脆骨", 58), ("宏原", 181), 
        ("宏黑", 54), ("福丸", 51.5), ("俏丸", 7), ("大福", 15), 
        ("小福", 3), ("大福骨", 5), ("70g福", 33), ("80g福", 14), 
        ("罗汇原味", 8), ("80g罗原", 2), ("火山石考肠", 43), 
        ("地道肠原味", 23), ("玉米肠", 1), ("利原", 2), ("夫宇", 14)
    ]
    c.executemany("INSERT OR IGNORE INTO products (name, stock) VALUES (?, ?)", initial_products)
    
    conn.commit()
    conn.close()

init_db()

# --- 数据库辅助函数 ---
def get_db():
    return sqlite3.connect(DB_PATH)

def get_all_products():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM products", conn)
    conn.close()
    return df

def get_all_customers():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM customers", conn)
    conn.close()
    return df

def get_customer_price(customer_id, product_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT price FROM customer_prices WHERE customer_id = ? AND product_id = ?", (customer_id, product_id))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0.0

# --- Streamlit 界面 ---
st.set_page_config(page_title="冻品订单管理系统", layout="wide")
st.title("❄️ 冻品订单管理系统")

menu = ["🛒 快速下单", "💰 收款对账", "⚙️ 客户价目管理", "📦 库存查看"]
choice = st.sidebar.selectbox("功能菜单", menu)

if choice == "🛒 快速下单":
    st.header("新订单录入")
    
    # 客户选择
    customers_df = get_all_customers()
    cust_list = customers_df['name'].tolist()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_cust_name = st.selectbox("选择客户", ["-- 请选择 --"] + cust_list)
        new_cust = st.text_input("新客户名称 (若名单中没有)")
        if st.button("添加新客户"):
            if new_cust:
                conn = get_db()
                try:
                    conn.execute("INSERT INTO customers (name) VALUES (?)", (new_cust,))
                    conn.commit()
                    st.success(f"客户 {new_cust} 添加成功！")
                    st.rerun()
                except:
                    st.error("客户已存在")
                finally:
                    conn.close()

    # 产品选择
    products_df = get_all_products()
    prod_list = products_df['name'].tolist()
    
    with col2:
        selected_prod_name = st.selectbox("选择产品", ["-- 请选择 --"] + prod_list)
        
    if selected_cust_name != "-- 请选择 --" and selected_prod_name != "-- 请选择 --":
        # 获取 ID
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM customers WHERE name = ?", (selected_cust_name,))
        cust_id = c.fetchone()[0]
        c.execute("SELECT id FROM products WHERE name = ?", (selected_prod_name,))
        prod_id = c.fetchone()[0]
        conn.close()
        
        # 获取专属价格
        price = get_customer_price(cust_id, prod_id)
        
        col3, col4, col5 = st.columns(3)
        with col3:
            final_price = st.number_input("单价 (元)", value=price, step=0.1)
        with col4:
            qty = st.number_input("数量", min_value=0.1, step=1.0)
        with col5:
            total = final_price * qty
            st.subheader(f"总额: {total:.2f} 元")
            
        if st.button("确认提交订单", type="primary"):
            conn = get_db()
            # 记录订单
            conn.execute('''INSERT INTO orders 
                            (customer_id, product_id, quantity, price_per_unit, total_price, order_date, payment_status) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                            (cust_id, prod_id, qty, final_price, total, datetime.now().strftime("%Y-%m-%d %H:%M"), "待收"))
            # 扣减库存
            conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, prod_id))
            conn.commit()
            conn.close()
            st.success("订单已保存并自动扣减库存！")

elif choice == "💰 收款对账":
    st.header("收款对账单")
    
    conn = get_db()
    query = '''
        SELECT o.id, c.name as 客户, p.name as 产品, o.quantity as 数量, 
               o.total_price as 总额, o.order_date as 日期, o.payment_status as 状态 
        FROM orders o 
        JOIN customers c ON o.customer_id = c.id 
        JOIN products p ON o.product_id = p.id 
        WHERE o.payment_status = '待收' 
        ORDER BY o.order_date DESC
    '''
    df_pending = pd.read_sql(query, conn)
    
    if not df_pending.empty:
        st.table(df_pending)
        
        order_id_to_mark = st.number_input("输入订单ID标记为已收款", min_value=1, step=1)
        if st.button("确认收款"):
            conn.execute("UPDATE orders SET payment_status = '已收' WHERE id = ?", (order_id_to_mark,))
            conn.commit()
            st.success(f"订单 {order_id_to_mark} 已标记为已收款")
            st.rerun()
    else:
        st.info("目前没有待收款订单。")
    conn.close()

elif choice == "⚙️ 客户价目管理":
    st.header("专属单价设定")
    
    customers_df = get_all_customers()
    cust_list = customers_df['name'].tolist()
    
    selected_cust = st.selectbox("选择要设定价格的客户", ["-- 请选择 --"] + cust_list)
    
    if selected_cust != "-- 请选择 --":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM customers WHERE name = ?", (selected_cust,))
        cust_id = c.fetchone()[0]
        
        products_df = get_all_products()
        
        # 构建价格编辑表
        price_data = []
        for _, row in products_df.iterrows():
            c.execute("SELECT price FROM customer_prices WHERE customer_id = ? AND product_id = ?", (cust_id, row['id']))
            res = c.fetchone()
            price_data.append({"产品": row['name'], "产品ID": row['id'], "单价": res[0] if res else 0.0})
        
        df_prices = pd.DataFrame(price_data)
        
        # 使用 data_editor 允许直接修改价格
        edited_df = st.data_editor(df_prices, column_config={"产品ID": None}) # 隐藏ID列
        
        if st.button("保存所有价格变更"):
            # 实际上 data_editor 这里的索引和原 df 一致
            # 我们需要把修改后的价格写回数据库
            for index, row in edited_df.iterrows():
                # 重新通过产品名找 ID（因为 ID 列被隐藏了，但我们可以通过 df_prices 映射）
                p_id = df_prices.iloc[index]['产品ID']
                new_price = row['单价']
                conn.execute("INSERT OR REPLACE INTO customer_prices (customer_id, product_id, price) VALUES (?, ?, ?)", 
                             (cust_id, p_id, new_price))
            conn.commit()
            st.success("价格更新成功！")
        conn.close()

elif choice == "📦 库存查看":
    st.header("当前库存实时状态")
    df_stock = get_all_products()
    st.dataframe(df_stock[['name', 'stock']].rename(columns={'name': '产品名称', 'stock': '剩余库存'}), use_container_width=True)
