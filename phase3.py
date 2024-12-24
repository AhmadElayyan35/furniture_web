from flask import Flask, request, render_template, redirect, url_for, session
import pymysql

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection configuration
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '0000',
    'database': 'AlAmeanFur',
    'port': 3306
}

def get_db_connection():
    return pymysql.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
        port=db_config['port'],
        cursorclass=pymysql.cursors.DictCursor
    )




@app.route('/add_order', methods=['POST'])
def add_order():
    try:
        cart = request.json.get('cart', [])  # Get the cart data from the frontend
        client_id = session.get('client_id')  # Retrieve ClientID from session

        if not client_id:
            return {"error": "User not logged in"}, 401

        if not cart:
            return {"error": "Cart is empty"}, 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Insert a new order for each product in the cart
            for item in cart:
                # Insert a new order in the Orders table
                insert_order_query = """
                    INSERT INTO Orders (ClientID, OrderDate, TotalAmount) 
                    VALUES (%s, NOW(), %s)
                """
                total_amount = item['price'] * item['quantity']
                cursor.execute(insert_order_query, (client_id, total_amount))
                order_id = cursor.lastrowid  # Get the new OrderID

                # Insert the product into the OrderItems table
                insert_item_query = """
                    INSERT INTO OrderItems (OrderID, ProductID, Quantity, Price) 
                    SELECT %s, ProductID, %s, %s FROM Products WHERE sName = %s
                """
                cursor.execute(
                    insert_item_query,
                    (order_id, item['quantity'], item['price'], item['name'])
                )

            conn.commit()

        return {"message": "Orders successfully added!"}, 200
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        if conn:
            conn.close()

@app.route('/products')
def products():
    conn = None
    try:
        conn = get_db_connection()

        # Fetch product data
        with conn.cursor() as cursor:
            query = "SELECT ProductID, sName AS product_name, Price, ImageURL FROM Products"
            cursor.execute(query)
            products = cursor.fetchall()

        return render_template('products.html', products=products)
    except pymysql.MySQLError as e:
        return render_template('error.html', error=f"Database Error: {str(e)}")
    except Exception as e:
        return render_template('error.html', error=f"Unexpected Error: {str(e)}")
    finally:
        if conn:
            conn.close()


# Login Route (Index)
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()  # Clean up input
        password = request.form['password'].strip()
        conn = None

        try:
            conn = get_db_connection()

            # Fetch user from Users table
            with conn.cursor() as cursor:
                user_query = "SELECT UserID, Username FROM Users WHERE Username = %s AND PasswordHash = %s"
                cursor.execute(user_query, (username, password))
                user = cursor.fetchone()

                if user:
                    session['user_id'] = user['UserID']  # Store UserID in session
                    session['username'] = user['Username']  # Store Username in session

                    # Check if the user is the admin
                    if username == 'admin':
                        return redirect(url_for('admin_dashboard'))

                    # Match UserID with ClientID in the Clients table
                    client_query = "SELECT ClientID FROM Clients WHERE ClientID = %s"
                    cursor.execute(client_query, (user['UserID'],))
                    client = cursor.fetchone()

                    if client:
                        session['client_id'] = client['ClientID']  # Store ClientID in session
                        return redirect(url_for('client_dashboard'))
                    else:
                        error = "You are not registered as a client."
                        return render_template('index.html', error=error)

                error = "Invalid username or password."
                return render_template('index.html', error=error)

        except Exception as e:
            return render_template('error.html', error=f"Unexpected Error: {str(e)}")
        finally:
            if conn:
                conn.close()

    # If GET request, render the login page
    return render_template('index.html')
# Admin Dashboard
@app.route('/admin')
def admin_dashboard():
    if 'username' in session and session['username'] == 'admin':  # Ensure only admin can access
        return render_template('admin.html', username=session['username'])
    else:
        return redirect(url_for('login'))






# Client Dashboard
@app.route('/client')
def client_dashboard():
    if 'username' in session and session['username'] != 'admin':  # Ensure only non-admin users can access
        username = session['username']  # Retrieve the username from the session
        return render_template('client.html', username=username)
    else:
        return redirect(url_for('login'))

# Logout
@app.route('/logout')
def logout():
    session.pop('username', None)  # Clear the session
    return redirect(url_for('index'))  # Redirect to the home page (index route)

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    else:
        return redirect(url_for('login'))


@app.route('/clients_orders')
def clients_orders():
    conn = None
    try:
        conn = get_db_connection()

        # Fetch clients and their orders
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    c.ClientID,
                    c.sName AS client_name,
                    c.Points,
                    COUNT(o.OrderID) AS total_orders,
                    COALESCE(SUM(o.TotalAmount), 0) AS total_spent
                FROM Clients c
                LEFT JOIN Orders o ON c.ClientID = o.ClientID
                GROUP BY c.ClientID, c.sName, c.Points
                ORDER BY c.sName
            """
            cursor.execute(query)
            clients_orders_data = cursor.fetchall()

        return render_template('clients_orders.html', clients=clients_orders_data)

    except pymysql.MySQLError as e:
        return render_template('error.html', error=f"Database Error: {str(e)}")
    except Exception as e:
        return render_template('error.html', error=f"Unexpected Error: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.route('/client_products/<int:client_id>')
def client_products(client_id):
    conn = None
    try:
        conn = get_db_connection()

        # Fetch the products ordered by the client
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    p.sName AS product_name,
                    i.Quantity,
                    i.Price,
                    (i.Quantity * i.Price) AS total
                FROM OrderItems i
                JOIN Products p ON i.ProductID = p.ProductID
                JOIN Orders o ON i.OrderID = o.OrderID
                WHERE o.ClientID = %s
            """
            cursor.execute(query, (client_id,))
            products = cursor.fetchall()

        # Fetch client info for the header
        with conn.cursor() as cursor:
            client_query = "SELECT sName FROM Clients WHERE ClientID = %s"
            cursor.execute(client_query, (client_id,))
            client = cursor.fetchone()

        return render_template('client_products.html', client=client, products=products)

    except pymysql.MySQLError as e:
        return render_template('error.html', error=f"Database Error: {str(e)}")
    except Exception as e:
        return render_template('error.html', error=f"Unexpected Error: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.route('/sales_report', methods=['GET', 'POST'])
def sales_report():
    conn = None

    # Final variables to pass to the template:
    total_sales = 0.0
    daily_sales = []
    top_five_products = []

    # If you have multiple filters (dates, multi-clients, multi-products),
    # we track them in these lists/vars:
    start_date = None
    end_date = None
    selected_client_ids = []
    selected_product_ids = []

    # We’ll also fetch the list of all clients and products for the <select> menus:
    clients = []
    products = []

    try:
        conn = get_db_connection()

        # 1) Fetch all clients for the dropdown
        with conn.cursor() as cursor:
            cursor.execute("SELECT ClientID, sName FROM Clients ORDER BY sName")
            clients = cursor.fetchall()  # e.g. [{'ClientID':1, 'sName':'Alice'}, ...]

        # 2) Fetch all products for the dropdown
        with conn.cursor() as cursor:
            cursor.execute("SELECT ProductID, sName FROM Products ORDER BY sName")
            products = cursor.fetchall()

        if request.method == 'POST':
            # Pull form data, trimming whitespace, or set to None if blank
            start_date = request.form.get('start_date', '').strip() or None
            end_date = request.form.get('end_date', '').strip() or None

            # Multi-selects: we get a LIST of IDs
            selected_client_ids = request.form.getlist('client_ids')  # e.g. ['1', '3']
            selected_product_ids = request.form.getlist('product_ids')  # e.g. ['5', '7']

            # Build dynamic WHERE clauses
            where_clauses = []
            query_params = []

            # Optional date filters
            if start_date:
                where_clauses.append("o.OrderDate >= %s")
                query_params.append(start_date)
            if end_date:
                where_clauses.append("o.OrderDate <= %s")
                query_params.append(end_date)

            # Optional multi-select clients
            if selected_client_ids:
                placeholders = ", ".join(["%s"] * len(selected_client_ids))
                where_clauses.append(f"o.ClientID IN ({placeholders})")
                query_params.extend(selected_client_ids)

            # Optional multi-select products
            if selected_product_ids:
                placeholders = ", ".join(["%s"] * len(selected_product_ids))
                where_clauses.append(f"i.ProductID IN ({placeholders})")
                query_params.extend(selected_product_ids)

            # Final WHERE
            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            # (A) Total Sales Query (summing line items)
            total_query = f"""
                SELECT 
                    SUM(i.Price * i.Quantity) AS total_sales
                FROM Orders o
                JOIN OrderItems i ON o.OrderID = i.OrderID
                {where_sql}
            """

            # (B) Daily Sales Query
            daily_query = f"""
                SELECT 
                    DATE_FORMAT(o.OrderDate, '%%Y-%%m-%%d') AS day,
                    SUM(i.Price * i.Quantity) AS daily_amount
                FROM Orders o
                JOIN OrderItems i ON o.OrderID = i.OrderID
                {where_sql}
                GROUP BY day
                ORDER BY day
            """

            # (C) Top 5 Products by total units sold
            top_five_query = f"""
                SELECT 
                    i.ProductID,
                    p.sName AS product_name,
                    SUM(i.Quantity) AS total_qty
                FROM Orders o
                JOIN OrderItems i ON o.OrderID = i.OrderID
                JOIN Products p ON i.ProductID = p.ProductID
                {where_sql}
                GROUP BY i.ProductID
                ORDER BY total_qty DESC
                LIMIT 5
            """

            # Run all queries
            with conn.cursor() as cursor:
                # 1) Total Sales
                cursor.execute(total_query, query_params)
                row = cursor.fetchone()
                total_sales = float(row['total_sales']) if row['total_sales'] else 0.0

                # 2) Daily Sales
                cursor.execute(daily_query, query_params)
                rows = cursor.fetchall()
                daily_sales = [
                    {
                        'day': r['day'],
                        'amount': float(r['daily_amount'])
                    }
                    for r in rows
                ]

                # 3) Top 5 Products
                cursor.execute(top_five_query, query_params)
                rows = cursor.fetchall()
                top_five_products = [
                    {
                        'ProductID': r['ProductID'],
                        'product_name': r['product_name'],
                        'total_qty': int(r['total_qty'])  # or float, if you prefer
                    }
                    for r in rows
                ]

        # If GET request (or no form submitted), we skip the queries and display a blank page
        # or you could run queries for "all data" by default, your choice.

        # Finally, render the template
        return render_template(
            'sales_report.html',
            total_sales=total_sales,
            daily_sales=daily_sales,
            top_five_products=top_five_products,

            # Pass filter data to keep selections in form
            start_date=start_date,
            end_date=end_date,
            selected_client_ids=selected_client_ids,
            selected_product_ids=selected_product_ids,

            # Pass the dropdown lists
            clients=clients,
            products=products
        )

    except pymysql.MySQLError as e:
        return render_template('error.html', error=f"Database Error: {str(e)}")
    except Exception as e:
        return render_template('error.html', error=f"Unexpected Error: {str(e)}")
    finally:
        if conn:
            conn.close()


from datetime import date
import pymysql
from flask import render_template


@app.route('/employee_manage', methods=['GET', 'POST'])
def employee_manage():
    conn = None
    employees = []

    # For the filters:
    selected_role = None
    min_salary = None
    max_salary = None

    # For the sort
    sort_by_salary = None

    # Distinct roles for a dropdown
    roles = []

    try:
        conn = get_db_connection()

        # 1) Distinct roles for the filter dropdown
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT rRole FROM Employees ORDER BY rRole")
            role_rows = cursor.fetchall()
            roles = [row['rRole'] for row in role_rows]

        if request.method == 'POST':
            # If the form has an employee_id and new_salary, we’re updating salary
            if 'employee_id' in request.form and 'new_salary' in request.form:
                employee_id = request.form.get('employee_id')
                new_salary_str = request.form.get('new_salary')
                try:
                    new_salary = float(new_salary_str)
                except ValueError:
                    return render_template('error.html', error="Invalid salary value.")

                with conn.cursor() as cursor:
                    update_sql = "UPDATE Employees SET salary = %s WHERE EmployeeID = %s"
                    cursor.execute(update_sql, (new_salary, employee_id))
                    conn.commit()

            # Grab the filter fields (role, min_salary, max_salary)
            selected_role = request.form.get('role', '').strip() or None
            min_salary_str = request.form.get('min_salary', '').strip() or None
            max_salary_str = request.form.get('max_salary', '').strip() or None

            # Grab the sort choice
            sort_by_salary = request.form.get('sort_by_salary', '')

            where_clauses = []
            params = []

            if selected_role and selected_role != 'ALL':
                where_clauses.append("rRole = %s")
                params.append(selected_role)

            if min_salary_str:
                try:
                    min_salary = float(min_salary_str)
                    where_clauses.append("salary >= %s")
                    params.append(min_salary)
                except ValueError:
                    pass

            if max_salary_str:
                try:
                    max_salary = float(max_salary_str)
                    where_clauses.append("salary <= %s")
                    params.append(max_salary)
                except ValueError:
                    pass

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            # Determine ORDER BY
            # If sort_by_salary is 'asc' or 'desc', we sort by salary
            # Otherwise, default to sorting by name
            if sort_by_salary == 'asc':
                order_by = "salary ASC"
            elif sort_by_salary == 'desc':
                order_by = "salary DESC"
            else:
                order_by = "sName"

            query = f"SELECT * FROM Employees {where_sql} ORDER BY {order_by}"
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                employees = cursor.fetchall()
        else:
            # GET request: show all employees by default, sorted by name
            query = "SELECT * FROM Employees ORDER BY sName"
            with conn.cursor() as cursor:
                cursor.execute(query)
                employees = cursor.fetchall()

        return render_template(
            'employee_manage.html',
            roles=roles,
            employees=employees,
            selected_role=selected_role,
            min_salary=min_salary,
            max_salary=max_salary,
            sort_by_salary=sort_by_salary
        )
    except Exception as e:
        return render_template('error.html', error=f"Error: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.route('/today_sales')
def today_sales():
    conn = None

    # These lists will hold the data passed to the template
    today_details = []     # Each row: product_name, client_name, quantity, line_total
    product_totals = []    # For the bar chart: product_name, total_sales

    try:
        conn = get_db_connection()

        # Query (A): Detailed rows for each order item from today's orders
        detail_query = """
            SELECT 
                c.sName AS client_name,
                p.sName AS product_name,
                i.Quantity,
                i.Price,
                (i.Quantity * i.Price) AS line_total
            FROM Orders o
            JOIN Clients c ON o.ClientID = c.ClientID
            JOIN OrderItems i ON o.OrderID = i.OrderID
            JOIN Products p ON i.ProductID = p.ProductID
            WHERE o.OrderDate = CURDATE()
        """

        # Query (B): Sum total sales by product for the bar chart
        product_query = """
            SELECT 
                p.sName AS product_name,
                SUM(i.Quantity * i.Price) AS product_total
            FROM Orders o
            JOIN OrderItems i ON o.OrderID = i.OrderID
            JOIN Products p ON i.ProductID = p.ProductID
            WHERE o.OrderDate = CURDATE()
            GROUP BY p.ProductID
            ORDER BY product_total DESC
        """

        with conn.cursor() as cursor:
            # 1) Fetch detail rows
            cursor.execute(detail_query)
            rows = cursor.fetchall()
            for r in rows:
                today_details.append({
                    'client_name':    r['client_name'],
                    'product_name':   r['product_name'],
                    'quantity':       r['Quantity'],
                    'price':          float(r['Price']),
                    'line_total':     float(r['line_total'])
                })

            # 2) Fetch product totals for bar chart
            cursor.execute(product_query)
            rows = cursor.fetchall()
            for r in rows:
                product_totals.append({
                    'product_name':   r['product_name'],
                    'product_total':  float(r['product_total'])
                })

        return render_template(
            'today_sales.html',
            today_details=today_details,
            product_totals=product_totals
        )

    except Exception as e:
        return render_template('error.html', error=f"Unexpected Error: {str(e)}")
    finally:
        if conn:
            conn.close()


# View Table Data with Optional Filtering
@app.route('/<table_name>', methods=['GET'])
def view_table(table_name):
    conn = None
    try:
        conn = get_db_connection()
        filters = request.args  # Capture query parameters for filtering
        filter_clauses = []
        filter_values = []

        # Fetch column names
        with conn.cursor() as cursor:
            cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
            columns_info = cursor.fetchall()
            columns = [row['Field'] for row in columns_info]

        # Build filter clauses dynamically based on query parameters
        for key, value in filters.items():
            # Remove leading/trailing whitespace
            value_str = value.strip()
            # Only apply non-empty filters
            if value_str:
                try:
                    float_val = float(value_str)
                    # Numeric/decimal exact match
                    filter_clauses.append(f"`{key}` = %s")
                    filter_values.append(float_val)
                except ValueError:
                    # String partial match (case-insensitive)
                    filter_clauses.append(f"LOWER(`{key}`) LIKE %s")
                    filter_values.append(f"%{value_str.lower()}%")

        # Construct the SQL query
        sql = f"SELECT * FROM `{table_name}`"
        if filter_clauses:
            sql += " WHERE " + " AND ".join(filter_clauses)

        # Fetch data from the database
        with conn.cursor() as cursor:
            cursor.execute(sql, filter_values)
            results = cursor.fetchall()

        return render_template('table.html',
                               table_name=table_name,
                               data=results,
                               columns=columns,
                               filters=filters)
    except pymysql.MySQLError as e:
        return render_template('error.html', error=f"Database Error: {str(e)}")
    except Exception as e:
        return render_template('error.html', error=f"Unexpected Error: {str(e)}")
    finally:
        if conn:
            conn.close()

# Add Data into Table
@app.route('/add/<table_name>', methods=['GET', 'POST'])
def add_data(table_name):
    if request.method == 'POST':
        conn = None
        try:
            data = request.form
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(data.values()))
                conn.commit()
            return redirect(url_for('view_table', table_name=table_name))
        except Exception as e:
            return render_template('error.html', error=f"Error adding data: {str(e)}")
        finally:
            if conn:
                conn.close()
    else:
        return render_template('add.html', table_name=table_name)

# Update Data in Table
@app.route('/update/<table_name>/<int:id>', methods=['GET', 'POST'])
def update_data(table_name, id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            primary_key = table_name[:-1] + "ID"  # Assumes naming convention
            cursor.execute(f"SELECT * FROM {table_name} WHERE {primary_key} = %s", (id,))
            existing_data = cursor.fetchone()

        if not existing_data:
            return render_template('error.html', error="Record not found.")

        if request.method == 'POST':
            data = request.form
            updates = ', '.join([f"{key} = %s" for key in data.keys()])
            sql = f"UPDATE {table_name} SET {updates} WHERE {primary_key} = %s"
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(data.values()) + (id,))
                conn.commit()
            return redirect(url_for('view_table', table_name=table_name))

        return render_template('update.html', table_name=table_name, data=existing_data)
    except Exception as e:
        return render_template('error.html', error=f"Error updating data: {str(e)}")
    finally:
        if conn:
            conn.close()

# Delete Data from Table
@app.route('/delete/<table_name>/<int:id>', methods=['POST'])
def delete_data(table_name, id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            primary_key = table_name[:-1] + "ID"  # Assumes naming convention
            sql = f"DELETE FROM {table_name} WHERE {primary_key} = %s"
            cursor.execute(sql, (id,))
            conn.commit()
        return redirect(url_for('view_table', table_name=table_name))
    except Exception as e:
        return render_template('error.html', error=f"Error deleting data: {str(e)}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)
