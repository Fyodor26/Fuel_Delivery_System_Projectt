from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL  
import MySQLdb.cursors
import re
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import qrcode
from io import BytesIO
import base64
from reportlab.pdfgen import canvas
from flask import send_file
import io
import csv
from flask import make_response

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Nakul123@'
app.config['MYSQL_DB'] = 'fuel_delivery'

app.secret_key = 'your_secret_key'

mysql = MySQL(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/marketplace')
def marketplace():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    
    for product in products:
        # Get reviews
        cur.execute("""
            SELECT r.*, u.username 
            FROM reviews r 
            JOIN users u ON r.user_id = u.id 
            WHERE r.product_id = %s 
            ORDER BY r.created_at DESC
        """, (product['id'],))
        product['reviews'] = cur.fetchall()
        
       
        cur.execute("""
            SELECT AVG(rating) as average_rating, COUNT(*) as total_reviews 
            FROM reviews 
            WHERE product_id = %s
        """, (product['id'],))
        rating_data = cur.fetchone()
        product['average_rating'] = float(rating_data['average_rating']) if rating_data['average_rating'] else 0
        product['total_reviews'] = rating_data['total_reviews']

        # Get recent orders
        cur.execute("""
            SELECT o.*, u.username 
            FROM orders o 
            JOIN users u ON o.user_id = u.id 
            WHERE o.fuel_type = %s 
            ORDER BY o.order_date DESC 
            LIMIT 3
        """, (product['name'],))
        product['recent_orders'] = cur.fetchall()
    
    cur.close()
    return render_template('marketplace.html', products=products, min_date=today)

@app.route('/order', methods=['POST'])
def order():
    if 'loggedin' not in session:
        flash('Please login to place an order', 'error')
        return redirect(url_for('login'))

    cur = None
    try:
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT id FROM users WHERE id = %s", (session['id'],))
        user = cur.fetchone()
        
        if not user:
            session.clear()  
            flash('Your session has expired. Please login again.', 'error')
            return redirect(url_for('login'))

        
        product_id = request.form.get('product_id')
        fuel_type = request.form.get('fuel_type', '').strip()
        quantity = request.form.get('quantity')
        delivery_address = request.form.get('delivery_address')
        delivery_date = request.form.get('delivery_date')

        
        print(f"Form data: product_id={product_id}, fuel_type={fuel_type}, quantity={quantity}, delivery_address={delivery_address}, delivery_date={delivery_date}")

        
        if not all([product_id, fuel_type, quantity, delivery_address, delivery_date]):
            missing_fields = []
            if not product_id: missing_fields.append("product_id")
            if not fuel_type: missing_fields.append("fuel_type")
            if not quantity: missing_fields.append("quantity")
            if not delivery_address: missing_fields.append("delivery_address")
            if not delivery_date: missing_fields.append("delivery_date")
            flash(f'Missing required fields: {", ".join(missing_fields)}', 'error')
            return redirect(url_for('marketplace'))

        
        try:
            quantity = int(quantity)
            if quantity < 1 or quantity > 1000:
                flash('Quantity must be between 1 and 1000 liters', 'error')
                return redirect(url_for('marketplace'))
        except ValueError:
            flash('Invalid quantity entered', 'error')
            return redirect(url_for('marketplace'))

        
        try:
            delivery_date_obj = datetime.strptime(delivery_date, '%Y-%m-%d')
            if delivery_date_obj.date() <= datetime.now().date():
                flash('Please select a future delivery date', 'error')
                return redirect(url_for('marketplace'))
        except ValueError:
            flash('Invalid delivery date', 'error')
            return redirect(url_for('marketplace'))

        
        cur.execute("SELECT price FROM products WHERE id = %s", (product_id,))
        product = cur.fetchone()

        if not product:
            flash('Invalid product selected', 'error')
            return redirect(url_for('marketplace'))

        
        total_price = float(product['price']) * quantity

        
        cur.execute("""
            INSERT INTO orders (
                user_id, 
                fuel_type, 
                quantity, 
                delivery_address, 
                delivery_date, 
                order_date, 
                total_price, 
                status
            ) VALUES (%s, %s, %s, %s, %s, NOW(), %s, 'Pending')
        """, (
            user['id'],  
            fuel_type,
            quantity,
            delivery_address,
            delivery_date,
            total_price
        ))

        mysql.connection.commit()
        flash('Order placed successfully!', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        if cur:
            cur.close()
        print(f"Error placing order: {str(e)}")  
        flash(f'An error occurred while placing your order: {str(e)}', 'error')
        return redirect(url_for('marketplace'))
    finally:
        if cur:
            cur.close()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']
        phone = request.form['phone']
        admin_code = request.form.get('admin_code', '') 
        admin_password = request.form.get('admin_password', '')  
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        
        if account:
            flash('Account already exists with this email!', 'error')
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address!', 'error')
        elif not username or not password or not email:
            flash('Please fill out the form!', 'error')
        else:
            
            if admin_code == 'ADMIN123':
                if not admin_password:
                    flash('Admin password is required for admin accounts', 'error')
                    return redirect(url_for('register'))
                if admin_password != 'AdminPass123!': 
                    flash('Invalid admin password', 'error')
                    return redirect(url_for('register'))
                role = 'admin'
            else:
                role = 'user'
            
            hashed_password = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, email, password, address, phone, role) 
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (username, email, hashed_password, address, phone, role))
            mysql.connection.commit()
            
            if role == 'admin':
                flash('Admin account created successfully!', 'success')
            else:
                flash('Account created successfully!', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Incorrect email/password!')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cur = None
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute('SELECT * FROM orders WHERE user_id = %s ORDER BY order_date DESC', (session['id'],))
        orders = cur.fetchall()
        
        
        print(f"User {session['id']} orders:")
        for order in orders:
            print(f"Order {order['id']} - Status: {order['status']}")
        
        return render_template('dashboard.html', username=session['username'], orders=orders)
    except Exception as e:
        print(f"Error in dashboard route: {str(e)}")
        flash('An error occurred while loading your dashboard', 'error')
        return redirect(url_for('home'))
    finally:
        if cur:
            cur.close()

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'loggedin' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    start_date = end_date = None
    sales_summary = []

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        if start_date and end_date:
            session['start_date'] = start_date
            session['end_date'] = end_date

            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cur.execute("""
                SELECT 
                    DATE(order_date) AS sale_date,
                    COUNT(*) AS total_orders,
                    SUM(quantity) AS total_quantity,
                    SUM(total_price) AS total_revenue
                FROM orders
                WHERE DATE(order_date) BETWEEN %s AND %s
                GROUP BY sale_date
                ORDER BY sale_date DESC
            """, (start_date, end_date))
            sales_summary = cur.fetchall()
            cur.close()

    return render_template('admin.html', sales_summary=sales_summary, start_date=start_date, end_date=end_date)




@app.route('/admin/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    status = request.form['status']
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('UPDATE orders SET status = %s WHERE id = %s', (status, order_id))
    mysql.connection.commit()
    
    flash('Order status updated successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        address = request.form['address']
        phone = request.form['phone']
        
        cursor.execute('''
            UPDATE users 
            SET username = %s, email = %s, address = %s, phone = %s 
            WHERE id = %s
        ''', (username, email, address, phone, session['id']))
        mysql.connection.commit()
        
        session['username'] = username
        flash('Profile updated successfully!')
    
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
    user = cursor.fetchone()
    
    return render_template('profile.html', user=user)

@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')

        if not all([name, price]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('admin_products'))

        try:
            price = float(price)
            if price <= 0:
                raise ValueError('Price must be greater than 0')
        except ValueError:
            flash('Invalid price entered', 'error')
            return redirect(url_for('admin_products'))

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO products (name, description, price)
            VALUES (%s, %s, %s)
        """, (name, description, price))
        mysql.connection.commit()
        cur.close()

        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))

    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM products ORDER BY created_at DESC")
    products = cur.fetchall()
    cur.close()

    return render_template('admin_products.html', products=products)

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('login'))

    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        mysql.connection.commit()
        cur.close()
        flash('Product deleted successfully', 'success')
    except Exception as e:
        flash('Error deleting product', 'error')
    
    return redirect(url_for('admin_products'))

@app.route('/review/<int:order_id>', methods=['GET', 'POST'])
def review(order_id):
    if 'loggedin' not in session:
        flash('Please login to leave a review', 'error')
        return redirect(url_for('login'))
    
    cur = None
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        
        cur.execute("""
            SELECT o.*, p.id as product_id 
            FROM orders o 
            JOIN products p ON o.fuel_type = p.name 
            WHERE o.id = %s AND o.user_id = %s AND o.status = 'Completed'
        """, (order_id, session['id']))
        order = cur.fetchone()
        
        if not order:
            flash('Order not found, not completed, or you do not have permission to review it', 'error')
            return redirect(url_for('dashboard'))
        
        
        cur.execute("""
            SELECT * FROM reviews 
            WHERE user_id = %s AND product_id = %s
        """, (session['id'], order['product_id']))
        existing_review = cur.fetchone()
        
        if request.method == 'POST':
            rating = request.form.get('rating')
            comment = request.form.get('comment', '').strip()
            
            print(f"Review submission - Order ID: {order_id}, Rating: {rating}, Comment: {comment}")
            
            if not rating:
                flash('Please provide a rating', 'error')
                return redirect(url_for('review', order_id=order_id))
            
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    raise ValueError('Rating must be between 1 and 5')
            except ValueError as e:
                flash(f'Invalid rating value: {str(e)}', 'error')
                return redirect(url_for('review', order_id=order_id))
            
            if existing_review:
                
                cur.execute("""
                    UPDATE reviews 
                    SET rating = %s, comment = %s, created_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (rating, comment, existing_review['id']))
                print(f"Updated existing review: {existing_review['id']}")
            else:
                
                cur.execute("""
                    INSERT INTO reviews (user_id, product_id, rating, comment) 
                    VALUES (%s, %s, %s, %s)
                """, (session['id'], order['product_id'], rating, comment))
                print(f"Created new review for product: {order['product_id']}")
            
            mysql.connection.commit()
            flash('Review submitted successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        return render_template('review.html', order=order, review=existing_review)
    
    except Exception as e:
        print(f"Error in review route: {str(e)}")
        flash('An error occurred while processing your review. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    finally:
        if cur:
            cur.close()

@app.route('/complete_order/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cur = None
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        
        cur.execute('SELECT * FROM orders WHERE id = %s AND user_id = %s', (order_id, session['id']))
        order = cur.fetchone()
        
        if not order:
            flash('Order not found or you do not have permission to update it', 'error')
            return redirect(url_for('dashboard'))
        
        
        cur.execute('UPDATE orders SET status = "Completed" WHERE id = %s', (order_id,))
        mysql.connection.commit()
        
        flash('Order marked as completed! You can now leave a review.', 'success')
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        print(f"Error completing order: {str(e)}")
        flash('An error occurred while updating the order status', 'error')
        return redirect(url_for('dashboard'))
    finally:
        if cur:
            cur.close()

# Cart routes
@app.route('/cart')
def cart():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    
    cart_items = session.get('cart', [])
    cart_products = []
    subtotal = 0
    
    if cart_items:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        for item in cart_items:
            cur.execute("SELECT * FROM products WHERE id = %s", (item['product_id'],))
            product = cur.fetchone()
            if product:
               
                if product['name'] == 'Gasoline':
                    total = 98.5 * item['quantity']
                elif product['name'] == 'Diesel':
                    total = 91 * item['quantity']
                elif product['name'] == 'Propane':
                    total = 95 * item['quantity']
                else:
                    total = product['price'] * item['quantity']
                
                cart_products.append({
                    'id': product['id'],
                    'fuel_type': product['name'],
                    'price': product['price'],
                    'quantity': item['quantity'],
                    'total': total
                })
                subtotal += total
        cur.close()
    
    
    delivery_fee = 0 if subtotal >= 1000 else 50
    total = subtotal + delivery_fee
    
    return render_template('cart.html', 
                         cart_items=cart_products,
                         subtotal=subtotal,
                         delivery_fee=delivery_fee,
                         total=total)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    
    if not product_id or quantity < 1:
        flash('Invalid product or quantity', 'error')
        return redirect(url_for('marketplace'))
    
    
    if 'cart' not in session:
        session['cart'] = []
    
   
    cart = session['cart']
    for item in cart:
        if item['product_id'] == int(product_id):
            item['quantity'] += quantity
            break
    else:
        cart.append({
            'product_id': int(product_id),
            'quantity': quantity
        })
    
    session['cart'] = cart
    flash('Item added to cart successfully!', 'success')
    return redirect(url_for('cart'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    product_id = int(request.form.get('product_id'))
    action = request.form.get('action')
    
    if 'cart' not in session:
        return redirect(url_for('cart'))
    
    cart = session['cart']
    for item in cart:
        if item['product_id'] == product_id:
            if action == 'increase':
                item['quantity'] += 1
            elif action == 'decrease' and item['quantity'] > 1:
                item['quantity'] -= 1
            break
    
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    product_id = int(request.form.get('product_id'))
    
    if 'cart' not in session:
        return redirect(url_for('cart'))
    
    cart = session['cart']
    cart = [item for item in cart if item['product_id'] != product_id]
    session['cart'] = cart
    
    flash('Item removed from cart', 'success')
    return redirect(url_for('cart'))

@app.route('/admin/sales')
def admin_sales():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    
    cur.execute("""
        SELECT 
            fuel_type,
            SUM(quantity) as total_quantity,
            SUM(total_price) as total_revenue,
            COUNT(*) as total_orders
        FROM orders
        GROUP BY fuel_type
    """)
    overall_summary = cur.fetchall()
    
    
    cur.execute("""
        SELECT * FROM sales_summary
        WHERE sale_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
        ORDER BY sale_date DESC
    """)
    daily_sales = cur.fetchall()
    
    cur.close()
    return render_template('admin_sales.html', 
                         overall_summary=overall_summary,
                         daily_sales=daily_sales)

@app.route('/admin/monthly_sales')
def monthly_sales():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    
    cur.execute("""
        SELECT 
            DATE_FORMAT(order_date, '%Y-%m') as month,
            COUNT(*) as total_orders,
            SUM(total_price) as total_sales,
            SUM(quantity) as total_quantity,
            fuel_type
        FROM orders 
        WHERE YEAR(order_date) = YEAR(CURRENT_DATE)
        AND status = 'Completed'
        GROUP BY DATE_FORMAT(order_date, '%Y-%m'), fuel_type
        ORDER BY month DESC, fuel_type
    """)
    
    monthly_data = cur.fetchall()
    
    
    sales_by_month = {}
    for record in monthly_data:
        month = record['month']
        if month not in sales_by_month:
            sales_by_month[month] = {
                'total_orders': 0,
                'total_sales': 0,
                'total_quantity': 0,
                'fuel_types': {}
            }
        
        sales_by_month[month]['total_orders'] += record['total_orders']
        sales_by_month[month]['total_sales'] += record['total_sales']
        sales_by_month[month]['total_quantity'] += record['total_quantity']
        sales_by_month[month]['fuel_types'][record['fuel_type']] = {
            'quantity': record['total_quantity'],
            'sales': record['total_sales']
        }
    
    cur.close()
    return render_template('monthly_sales.html', sales_data=sales_by_month)
@app.context_processor
def inject_user_info():
    return dict(role=session.get('role'), username=session.get('username'))

@app.route('/invoice_pdf/<int:order_id>')
def invoice_pdf(order_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('''
        SELECT o.*, u.username, u.email, u.address, u.phone
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.id = %s AND o.user_id = %s
    ''', (order_id, session['id']))
    order = cur.fetchone()
    cur.close()

    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('dashboard'))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle(f"Invoice_{order_id}")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, 800, "FuelDel - Invoice")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"Invoice for Order ID: {order['id']}")
    pdf.drawString(50, 750, f"Customer: {order['username']}")
    pdf.drawString(50, 735, f"Email: {order['email']}")
    pdf.drawString(50, 720, f"Address: {order['address']}")
    pdf.drawString(50, 705, f"Phone: {order['phone']}")
    pdf.drawString(50, 685, f"Fuel Type: {order['fuel_type']}")
    pdf.drawString(50, 670, f"Quantity: {order['quantity']} L")
    pdf.drawString(50, 655, f"Total Price: ₹{order['total_price']}")
    pdf.drawString(50, 640, f"Status: {order['status']}")
    pdf.drawString(50, 625, f"Delivery Date: {order['delivery_date']}")
    pdf.drawString(50, 610, f"Order Date: {order['order_date']}")

    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"invoice_{order_id}.pdf", mimetype='application/pdf')

@app.route('/qr_invoice/<int:order_id>')
def qr_invoice(order_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    invoice_url = url_for('invoice_pdf', order_id=order_id, _external=True)

    
    qr = qrcode.make(invoice_url)

    buffer = io.BytesIO()
    qr.save(buffer, format='PNG')
    buffer.seek(0)

    return send_file(buffer, mimetype='image/png')

@app.route('/download_sales_summary')
def download_sales_summary():
    if 'loggedin' not in session or session['role'] != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT 
            DATE(order_date) AS sale_date,
            COUNT(*) AS total_orders,
            SUM(quantity) AS total_quantity,
            SUM(total_price) AS total_revenue
        FROM orders
        GROUP BY DATE(order_date)
        ORDER BY sale_date DESC
    """)
    summary_data = cur.fetchall()
    cur.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # CSV Header
    writer.writerow(['Date', 'Total Orders', 'Total Quantity', 'Total Revenue'])

    # CSV Rows
    for row in summary_data:
        writer.writerow([row['sale_date'], row['total_orders'], row['total_quantity'], row['total_revenue']])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=sales_summary.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/download_filtered_sales')
def download_filtered_sales():
    if 'loggedin' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    start_date = session.get('start_date')
    end_date = session.get('end_date')

    if not start_date or not end_date:
        flash('Please generate a report first.', 'error')
        return redirect(url_for('admin'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT 
            DATE(order_date) AS sale_date,
            COUNT(*) AS total_orders,
            SUM(quantity) AS total_quantity,
            SUM(total_price) AS total_revenue
        FROM orders
        WHERE DATE(order_date) BETWEEN %s AND %s
        GROUP BY sale_date
        ORDER BY sale_date DESC
    """, (start_date, end_date))
    summary_data = cur.fetchall()
    cur.close()

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Date', 'Total Orders', 'Total Quantity', 'Total Revenue'])

    for row in summary_data:
        writer.writerow([row['sale_date'], row['total_orders'], row['total_quantity'], row['total_revenue']])

    response = make_response(si.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=sales_summary_{start_date}_to_{end_date}.csv"
    response.headers["Content-type"] = "text/csv"
    return response



if __name__ == '__main__':
    app.run(debug=True)