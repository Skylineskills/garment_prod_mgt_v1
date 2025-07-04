import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import os
import io

# Constants
FABRIC_STANDARD = {
    "top": 1.5,
    "trouser": 1.0,
    "suit": 2.5
}

PRODUCT_MAPPING = {"Tops": "top", "Trousers": "trouser", "Suits": "suit"}

# Ensure data directory exists
data_dir = "data"
if not os.path.exists(data_dir):
    try:
        os.makedirs(data_dir)
    except Exception as e:
        st.error(f"Failed to create data directory: {e}")
        st.stop()

# Database path
db_path = os.path.join(data_dir, "production.db")

# Database setup
try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
except sqlite3.OperationalError as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

# Create tables
try:
    # Create 'orders' table
    c.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE,
        customer TEXT,
        product TEXT,
        due_date TEXT,
        quantity INTEGER,
        cutting INTEGER DEFAULT 0,
        sewing INTEGER DEFAULT 0,
        finishing INTEGER DEFAULT 0,
        packaging INTEGER DEFAULT 0
    )
    ''')

    # Create 'fabric_cost_1' table with additional cost fields
    c.execute('''
    CREATE TABLE IF NOT EXISTS fabric_cost_1 (
        order_number TEXT PRIMARY KEY,
        item_type TEXT,
        units INTEGER,
        fabric_issued REAL,
        fabric_rate REAL,
        accessories_rate REAL,
        printing_rate REAL,
        overhead_per_unit REAL,
        labor_cutting_rate REAL DEFAULT 0.0,
        labor_sewing_rate REAL DEFAULT 0.0,
        labor_finishing_rate REAL DEFAULT 0.0,
        dyeing_rate REAL DEFAULT 0.0,
        embroidery_rate REAL DEFAULT 0.0,
        shipping_cost REAL DEFAULT 0.0,
        misc_cost REAL DEFAULT 0.0,
        last_updated TEXT
    )
    ''')

    # Create 'fabric_standards' table
    c.execute('''
    CREATE TABLE IF NOT EXISTS fabric_standards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_type TEXT,
        size TEXT,
        style TEXT,
        fabric_per_unit REAL
    )
    ''')

    # Create 'fabric_cost_history' table
    c.execute('''
    CREATE TABLE IF NOT EXISTS fabric_cost_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        item_type TEXT,
        units INTEGER,
        fabric_issued REAL,
        fabric_rate REAL,
        accessories_rate REAL,
        printing_rate REAL,
        overhead_per_unit REAL,
        labor_cutting_rate REAL,
        labor_sewing_rate REAL,
        labor_finishing_rate REAL,
        dyeing_rate REAL,
        embroidery_rate REAL,
        shipping_cost REAL,
        misc_cost REAL,
        last_updated TEXT
    )
    ''')

    # Create 'accessories_details' table
    c.execute('''
    CREATE TABLE IF NOT EXISTS accessories_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        accessory_type TEXT,
        quantity REAL,
        rate REAL,
        last_updated TEXT
    )
    ''')

    # Insert default fabric standards if not already present
    c.execute("SELECT COUNT(*) FROM fabric_standards")
    if c.fetchone()[0] == 0:
        c.executemany('''
            INSERT INTO fabric_standards (product_type, size, style, fabric_per_unit)
            VALUES (?, ?, ?, ?)
        ''', [
            ('top', 'standard', 'regular', 1.5),
            ('trouser', 'standard', 'regular', 1.0),
            ('suit', 'standard', 'regular', 2.5)
        ])

    conn.commit()
except Exception as e:
    st.error(f"Error setting up database: {e}")
    conn.close()
    st.stop()

# Sidebar Navigation
st.sidebar.title("Order Flow Insight")
page = st.sidebar.radio("Go to", ["Dashboard", "Orders", "Record", "Cost Sheet", "Data Entry"])

# User credentials
users = {"admin": "admin123", "user1": "password1"}

# Login screen
def login():
    st.title("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if username in users and users[username] == password:
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success(f"Welcome, {username}!")
                st.rerun()
            else:
                st.error("Invalid credentials.")

# Initialize login state
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Show login page or main app
if not st.session_state["authenticated"]:
    login()
    conn.close()
    st.stop()

# Logout button
st.sidebar.write(f"Logged in as: {st.session_state['username']}")
if st.sidebar.button("Logout"):
    st.session_state["authenticated"] = False
    conn.close()
    st.rerun()

# Dashboard Page
if page == "Dashboard":
    st.title("Dashboard")
    try:
        df = pd.read_sql("SELECT * FROM orders", conn)
    except Exception as e:
        st.error(f"Error fetching orders: {e}")
        conn.close()
        st.stop()

    metric_card_style = """
<div style="background-color: white; padding: 1.5rem; margin: 0.5rem; border-radius: 0.5rem; box-shadow: 0 0 10px rgba(0, 0, 0, 0.05); width: 100%; height: 150px; display: flex; flex-direction: column; justify-content: space-between; align-items: center;">
    <div style="font-size: 1.1rem; color: #333;">{label}</div>
    <div style="font-size: 2rem; font-weight: bold; color: #000;">{value}</div>
    <div style="font-size: 0.9rem; color: green;">{delta}</div>
</div>
"""

    left_column, mid_column_1, mid_column_2, right_column = st.columns(4)

    if not df.empty:
        df["total_completed"] = df[["cutting", "sewing", "finishing", "packaging"]].min(axis=1)
        overall_completion = int((df["packaging"].sum() / df["quantity"].sum()) * 100)

        # Metric 1 - Overall Completion
        with left_column:
            st.markdown(metric_card_style.format(
                label="Overall Completion",
                value=f"{overall_completion}%",
                delta="↑ Across all deptts"
            ), unsafe_allow_html=True)

        # Metric 2 - Active Orders
        with mid_column_1:
            st.markdown(metric_card_style.format(
                label="Active Orders",
                value=len(df),
                delta=" "
            ), unsafe_allow_html=True)

        # Dates and metrics
        df["due_date"] = pd.to_datetime(df["due_date"], errors='coerce')
        today = date.today()
        on_track = len(df[df["due_date"].dt.date > today])
        at_risk = len(df[df["due_date"].dt.date < today])

        # Metric 3 - On Track Orders
        with mid_column_2:
            st.markdown(metric_card_style.format(
                label="On Track Orders",
                value=on_track,
                delta=" "
            ), unsafe_allow_html=True)

        # Metric 4 - At Risk Orders
        with right_column:
            st.markdown(metric_card_style.format(
                label="At Risk Orders",
                value=at_risk,
                delta="↑ Need attention"
            ), unsafe_allow_html=True)

        actual_production = df[["cutting", "sewing", "finishing", "packaging"]].mean().reset_index()
        actual_production.columns = ["process", "actual_production"]

        standard_production = pd.DataFrame({"process": ["cutting", "sewing", "finishing", "packaging"], "standard_production": [120]*4})
        comparison_df = pd.merge(actual_production, standard_production, on="process")
        melted_df = comparison_df.melt(id_vars="process", value_vars=["standard_production", "actual_production"], var_name="Type", value_name="Production")

        st.plotly_chart(px.bar(melted_df, x="process", y="Production", color="Type", barmode="group", title="Standard vs Actual Production"))

        df.dropna(subset=["due_date"], inplace=True)
        df["month"] = df["due_date"].dt.to_period("M").astype(str)
        monthly_summary = df.groupby("month")[["quantity", "cutting", "sewing", "finishing", "packaging"]].sum().reset_index()

        st.subheader("Month-wise Production Summary")
        st.dataframe(monthly_summary)
        st.plotly_chart(px.line(monthly_summary, x="month", y=["cutting", "sewing", "finishing", "packaging"], title="Monthly Trend by Process"))
    else:
        st.info("No data available. Add orders to get started.")

# Orders Page
elif page == "Orders":
    st.title("Update and Track Order")
    search_order = st.text_input("Search by Order Number")
    try:
        df = pd.read_sql("SELECT * FROM orders WHERE order_number LIKE ?" if search_order else "SELECT * FROM orders", conn, params=(f"%{search_order}%",) if search_order else ())
    except Exception as e:
        st.error(f"Error fetching orders: {e}")
        conn.close()
        st.stop()

    if not df.empty:
        for _, row in df.iterrows():
            with st.expander(f"{row['order_number']} | {row['customer']} | {row['product']} | Due: {row['due_date']}"):
                st.write(f"**Quantity**: {row['quantity']}")
                col1, col2, col3, col4 = st.columns(4)
                cutting = col1.number_input("Cutting", 0, row["quantity"], row["cutting"], key=f"cut{row['id']}")
                sewing = col2.number_input("Sewing", 0, row["quantity"], row["sewing"], key=f"sew{row['id']}")
                finishing = col3.number_input("Finishing", 0, row["quantity"], row["finishing"], key=f"fin{row['id']}")
                packaging = col4.number_input("Packaging", 0, row["quantity"], row["packaging"], key=f"pack{row['id']}")
                if st.button("Update", key=f"update{row['id']}"):
                    try:
                        c.execute("""
                            UPDATE orders SET cutting=?, sewing=?, finishing=?, packaging=? WHERE id=?
                        """, (cutting, sewing, finishing, packaging, row["id"]))
                        conn.commit()
                        st.success("Updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating order: {e}")
    else:
        st.info("No orders yet.")

# Record Page
elif page == "Record":
    st.title("Monthly Production Information")
    try:
        df = pd.read_sql("SELECT * FROM orders", conn)
    except Exception as e:
        st.error(f"Error fetching orders: {e}")
        conn.close()
        st.stop()

    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df.dropna(subset=["due_date"], inplace=True)
    df["month"] = df["due_date"].dt.to_period("M").astype(str)
    df["due_date"] = df["due_date"].dt.date
    df["status"] = df.apply(lambda row: "Closed" if row["packaging"] >= row["quantity"] else "Open", axis=1)

    st.subheader("Search and Filter Orders")
    col1, col2, col3 = st.columns(3)
    search_order = col1.text_input("Order Number")
    search_customer = col2.text_input("Customer")
    status_filter = col3.selectbox("Status", ["All", "Open", "Closed"])

    filtered_df = df.copy()
    if search_order:
        filtered_df = filtered_df[filtered_df["order_number"].str.contains(search_order, case=False)]
    if search_customer:
        filtered_df = filtered_df[filtered_df["customer"].str.contains(search_customer, case=False)]
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]

    st.subheader("Order-wise Production Status")
    st.dataframe(filtered_df[["order_number", "customer", "due_date", "quantity", "cutting", "sewing", "finishing", "packaging", "status"]])
    st.download_button("\U0001F4C4 Download as CSV", filtered_df.to_csv(index=False), "orderwise_production_report.csv", "text/csv")

# Cost Sheet Page
elif page == "Cost Sheet":
    st.title("Cost Charged to Order")

    # Fetch orders
    try:
        c.execute("SELECT order_number, product, quantity FROM orders")
        order_data = c.fetchall()
        order_map = {row[0]: row for row in order_data}
    except Exception as e:
        st.error(f"Error fetching orders: {e}")
        conn.close()
        st.stop()

    if not order_map:
        st.warning("No orders available.")
    else:
        selected_order = st.selectbox("Select Order Number", list(order_map.keys()))

        if selected_order:
            order_number, product, units = order_map[selected_order]
            item_type = PRODUCT_MAPPING.get(product.capitalize(), product.lower())

            # Fetch standard fabric requirement
            try:
                c.execute("SELECT fabric_per_unit FROM fabric_standards WHERE product_type = ? AND size = ?",
                          (item_type, 'standard'))
                standard_fabric = c.fetchone()
                fabric_required_std = standard_fabric[0] * units if standard_fabric else FABRIC_STANDARD.get(item_type, 0) * units
                st.write(f"**Item Type:** {item_type.capitalize()}")
                st.write(f"**Units Ordered:** {units}")
                st.write(f"**Standard Fabric Required:** {fabric_required_std:.2f} meters")
            except Exception as e:
                st.error(f"Error fetching fabric standards: {e}")
                fabric_required_std = FABRIC_STANDARD.get(item_type, 0) * units

            if item_type not in FABRIC_STANDARD and not standard_fabric:
                st.warning(f"No standard fabric requirement defined for item type: {item_type}")

            # Fetch existing cost data
            try:
                c.execute("""
                    SELECT fabric_issued, fabric_rate, accessories_rate, printing_rate, overhead_per_unit,
                           labor_cutting_rate, labor_sewing_rate, labor_finishing_rate,
                           dyeing_rate, embroidery_rate, shipping_cost, misc_cost
                    FROM fabric_cost_1 WHERE order_number = ?
                """, (order_number,))
                existing_cost = c.fetchone()
                defaults = existing_cost if existing_cost else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            except Exception as e:
                st.error(f"Error fetching cost data: {e}")
                defaults = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

            with st.form("cost_form"):
                fabric_required_override = st.number_input("Override Standard Fabric per Unit (meters)", min_value=0.0, step=0.1, value=FABRIC_STANDARD.get(item_type, 0))
                fabric_required = fabric_required_override * units if fabric_required_override else fabric_required_std
                st.write(f"**Total Fabric Required:** {fabric_required:.2f} meters")
                fabric_issued = st.number_input("Fabric Issued (meters)", min_value=0.0, step=0.1, value=defaults[0])
                fabric_rate = st.number_input("Fabric Rate per Meter", min_value=0.0, step=1.0, value=defaults[1])
                accessories_rate = st.number_input("Accessories Rate per Unit", min_value=0.0, step=1.0, value=defaults[2])
                printing_rate = st.number_input("Printing Rate per Unit", min_value=0.0, step=1.0, value=defaults[3])
                overhead_per_unit = st.number_input("Overhead per Unit", min_value=0.0, step=1.0, value=defaults[4])
                labor_cutting_rate = st.number_input("Labor Cutting Rate per Unit", min_value=0.0, step=1.0, value=defaults[5])
                labor_sewing_rate = st.number_input("Labor Sewing Rate per Unit", min_value=0.0, step=1.0, value=defaults[6])
                labor_finishing_rate = st.number_input("Labor Finishing Rate per Unit", min_value=0.0, step=1.0, value=defaults[7])
                dyeing_rate = st.number_input("Dyeing Rate per Unit", min_value=0.0, step=1.0, value=defaults[8])
                embroidery_rate = st.number_input("Embroidery Rate per Unit", min_value=0.0, step=1.0, value=defaults[9])
                shipping_cost = st.number_input("Shipping Cost (Total)", min_value=0.0, step=1.0, value=defaults[10])
                misc_cost = st.number_input("Miscellaneous Cost (Total)", min_value=0.0, step=1.0, value=defaults[11])
                st.info("Typical ranges: Fabric Rate ($1–$50/meter), Accessories Rate ($0–$20/unit), Printing Rate ($0–$10/unit).")
                submitted = st.form_submit_button("Save Cost Record")

                # Validation
                if fabric_issued < fabric_required * 0.8 or fabric_issued > fabric_required * 1.2:
                    st.warning(f"Fabric issued ({fabric_issued:.2f} meters) deviates significantly from required ({fabric_required:.2f} meters).")
                if fabric_rate < 1.0 or fabric_rate > 50.0:
                    st.warning("Fabric rate seems unusual. Typical range is $1–$50 per meter.")

            # Calculations
            fabric_cost = fabric_issued * fabric_rate
            accessories_cost = units * accessories_rate
            printing_cost = units * printing_rate
            overhead_cost = units * overhead_per_unit
            labor_cutting_cost = units * labor_cutting_rate
            labor_sewing_cost = units * labor_sewing_rate
            labor_finishing_cost = units * labor_finishing_rate
            dyeing_cost = units * dyeing_rate
            embroidery_cost = units * embroidery_rate
            total_cost = (fabric_cost + accessories_cost + printing_cost + overhead_cost +
                          labor_cutting_cost + labor_sewing_cost + labor_finishing_cost +
                          dyeing_cost + embroidery_cost + shipping_cost + misc_cost)
            cost_per_unit = total_cost / units if units else 0

            if st.button("Preview Costs"):
                st.write(f"Preview - Fabric Cost: {fabric_cost:,.2f}")
                st.write(f"Preview - Accessories Cost: {accessories_cost:,.2f}")
                st.write(f"Preview - Total Cost: {total_cost:,.2f}")

            st.subheader("\U0001F4B0 Cost Summary")
            st.write(f"Fabric Cost: **{fabric_cost:,.2f}**")
            st.write(f"Accessories Cost: **{accessories_cost:,.2f}**")
            st.write(f"Printing Cost: **{printing_cost:,.2f}**")
            st.write(f"Overhead Cost: **{overhead_cost:,.2f}**")
            st.write(f"Labor Cutting Cost: **{labor_cutting_cost:,.2f}**")
            st.write(f"Labor Sewing Cost: **{labor_sewing_cost:,.2f}**")
            st.write(f"Labor Finishing Cost: **{labor_finishing_cost:,.2f}**")
            st.write(f"Dyeing Cost: **{dyeing_cost:,.2f}**")
            st.write(f"Embroidery Cost: **{embroidery_cost:,.2f}**")
            st.write(f"Shipping Cost: **{shipping_cost:,.2f}**")
            st.write(f"Miscellaneous Cost: **{misc_cost:,.2f}**")
            st.success(f"Total Cost: **{total_cost:,.2f}**")
            st.write(f"Cost per Unit: **{cost_per_unit:,.2f}**")

            pie_data = pd.DataFrame({
                "Component": ["Fabric Cost", "Accessories Cost", "Printing Cost", "Overhead Cost",
                              "Labor Cutting Cost", "Labor Sewing Cost", "Labor Finishing Cost",
                              "Dyeing Cost", "Embroidery Cost", "Shipping Cost", "Miscellaneous Cost"],
                "Amount": [fabric_cost, accessories_cost, printing_cost, overhead_cost,
                           labor_cutting_cost, labor_sewing_cost, labor_finishing_cost,
                           dyeing_cost, embroidery_cost, shipping_cost, misc_cost]
            })
            st.plotly_chart(px.pie(pie_data, names="Component", values="Amount", title="Cost Distribution"),
                            use_container_width=True)

            if submitted:
                try:
                    last_updated = datetime.now().isoformat()
                    c.execute("""
                        INSERT INTO fabric_cost_history (
                            order_number, item_type, units,
                            fabric_issued, fabric_rate,
                            accessories_rate, printing_rate, overhead_per_unit,
                            labor_cutting_rate, labor_sewing_rate, labor_finishing_rate,
                            dyeing_rate, embroidery_rate, shipping_cost, misc_cost,
                            last_updated
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        order_number, item_type, units,
                        fabric_issued, fabric_rate,
                        accessories_rate, printing_rate, overhead_per_unit,
                        labor_cutting_rate, labor_sewing_rate, labor_finishing_rate,
                        dyeing_rate, embroidery_rate, shipping_cost, misc_cost,
                        last_updated
                    ))
                    c.execute("""
                        INSERT INTO fabric_cost_1 (
                            order_number, item_type, units,
                            fabric_issued, fabric_rate,
                            accessories_rate, printing_rate, overhead_per_unit,
                            labor_cutting_rate, labor_sewing_rate, labor_finishing_rate,
                            dyeing_rate, embroidery_rate, shipping_cost, misc_cost,
                            last_updated
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(order_number) DO UPDATE SET
                            item_type=excluded.item_type,
                            units=excluded.units,
                            fabric_issued=excluded.fabric_issued,
                            fabric_rate=excluded.fabric_rate,
                            accessories_rate=excluded.accessories_rate,
                            printing_rate=excluded.printing_rate,
                            overhead_per_unit=excluded.overhead_per_unit,
                            labor_cutting_rate=excluded.labor_cutting_rate,
                            labor_sewing_rate=excluded.labor_sewing_rate,
                            labor_finishing_rate=excluded.labor_finishing_rate,
                            dyeing_rate=excluded.dyeing_rate,
                            embroidery_rate=excluded.embroidery_rate,
                            shipping_cost=excluded.shipping_cost,
                            misc_cost=excluded.misc_cost,
                            last_updated=excluded.last_updated
                    """, (
                        order_number, item_type, units,
                        fabric_issued, fabric_rate,
                        accessories_rate, printing_rate, overhead_per_unit,
                        labor_cutting_rate, labor_sewing_rate, labor_finishing_rate,
                        dyeing_rate, embroidery_rate, shipping_cost, misc_cost,
                        last_updated
                    ))
                    conn.commit()
                    st.success("Cost record saved/updated successfully.")
                except sqlite3.IntegrityError:
                    st.error("Error: Order number already exists or invalid data provided.")
                except Exception as e:
                    st.error(f"Error saving cost: {str(e)}. Please check input values.")

            # Accessories Breakdown
            st.subheader("Accessories Breakdown")
            with st.form("accessories_form"):
                accessory_type = st.text_input("Accessory Type (e.g., Buttons, Zippers)")
                accessory_quantity = st.number_input("Quantity", min_value=0.0, step=0.1)
                accessory_rate = st.number_input("Rate per Unit", min_value=0.0, step=1.0)
                add_accessory = st.form_submit_button("Add Accessory")

                if add_accessory:
                    try:
                        c.execute("""
                            INSERT INTO accessories_details (order_number, accessory_type, quantity, rate, last_updated)
                            VALUES (?, ?, ?, ?, ?)
                        """, (order_number, accessory_type, accessory_quantity, accessory_rate, datetime.now().isoformat()))
                        conn.commit()
                        st.success("Accessory added.")
                    except Exception as e:
                        st.error(f"Error adding accessory: {e}")

            try:
                c.execute("SELECT accessory_type, quantity, rate FROM accessories_details WHERE order_number = ?", (order_number,))
                accessories = c.fetchall()
                if accessories:
                    accessories_df = pd.DataFrame(accessories, columns=["Accessory Type", "Quantity", "Rate"])
                    accessories_df["Total Cost"] = accessories_df["Quantity"] * accessories_df["Rate"]
                    st.dataframe(accessories_df)
                    total_accessories_cost = accessories_df["Total Cost"].sum()
                    st.write(f"**Total Accessories Cost**: {total_accessories_cost:,.2f}")
                else:
                    total_accessories_cost = units * accessories_rate
            except Exception as e:
                st.error(f"Error fetching accessories: {e}")

            # Cost History
            st.subheader("Cost History")
            try:
                c.execute("SELECT * FROM fabric_cost_history WHERE order_number = ? ORDER BY last_updated DESC", (order_number,))
                history_rows = c.fetchall()
                if history_rows:
                    history_df = pd.DataFrame(history_rows, columns=[
                        "ID", "Order Number", "Item Type", "Units",
                        "Fabric Issued", "Fabric Rate", "Accessories Rate",
                        "Printing Rate", "Overhead per Unit",
                        "Labor Cutting Rate", "Labor Sewing Rate", "Labor Finishing Rate",
                        "Dyeing Rate", "Embroidery Rate", "Shipping Cost", "Misc Cost",
                        "Last Updated"
                    ])
                    st.dataframe(history_df)
                else:
                    st.info("No cost history available for this order.")
            except Exception as e:
                st.error(f"Error fetching cost history: {e}")

        st.header("📥 Download Order-Wise Cost Data")
        try:
            c.execute('''
                SELECT
                    o.order_number,
                    o.customer,
                    o.product,
                    o.quantity,
                    COALESCE(f.item_type, '') as item_type,
                    COALESCE(f.units, 0) as units,
                    COALESCE(f.fabric_issued, 0.0) as fabric_issued,
                    COALESCE(f.fabric_rate, 0.0) as fabric_rate,
                    COALESCE(f.accessories_rate, 0.0) as accessories_rate,
                    COALESCE(f.printing_rate, 0.0) as printing_rate,
                    COALESCE(f.overhead_per_unit, 0.0) as overhead_per_unit,
                    COALESCE(f.labor_cutting_rate, 0.0) as labor_cutting_rate,
                    COALESCE(f.labor_sewing_rate, 0.0) as labor_sewing_rate,
                    COALESCE(f.labor_finishing_rate, 0.0) as labor_finishing_rate,
                    COALESCE(f.dyeing_rate, 0.0) as dyeing_rate,
                    COALESCE(f.embroidery_rate, 0.0) as embroidery_rate,
                    COALESCE(f.shipping_cost, 0.0) as shipping_cost,
                    COALESCE(f.misc_cost, 0.0) as misc_cost,
                    COALESCE(f.last_updated, '') as last_updated
                FROM orders o
                LEFT JOIN fabric_cost_1 f ON f.order_number = o.order_number
                ORDER BY f.last_updated DESC
            ''')
            rows = c.fetchall()
            columns = [
                "Order Number", "Customer", "Product", "Quantity", "Item Type", "Units",
                "Fabric Issued", "Fabric Rate", "Accessories Rate",
                "Printing Rate", "Overhead per Unit",
                "Labor Cutting Rate", "Labor Sewing Rate", "Labor Finishing Rate",
                "Dyeing Rate", "Embroidery Rate", "Shipping Cost", "Miscellaneous Cost",
                "Last Updated"
            ]
            df = pd.DataFrame(rows, columns=columns)
            if df.empty:
                st.warning("No cost data available to download.")
            else:
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Download Cost Data as CSV",
                    data=csv,
                    file_name="order_cost_data.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"Error fetching cost data for download: {e}")

# Data Entry Page
elif page == "Data Entry":
    st.title("Add New Order")
    with st.form("order_form"):
        order_number = st.text_input("Order Number", "ORD-2023-004")
        customer = st.text_input("Customer", "Acme Corp")
        product = st.selectbox("Product", ["Tops", "Trousers", "Suits"])
        due_date = st.date_input("Due Date")
        quantity = st.number_input("Total Quantity", min_value=1, step=1)
        submitted = st.form_submit_button("Add Order")

        if submitted:
            try:
                c.execute("""
                    INSERT INTO orders (order_number, customer, product, due_date, quantity)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_number, customer, product, due_date.strftime("%Y-%m-%d"), quantity))
                conn.commit()
                st.success("Order added successfully!")
            except sqlite3.IntegrityError:
                st.error("Order number must be unique.")
            except Exception as e:
                st.error(f"Error adding order: {e}")

# Close database connection
conn.close()
