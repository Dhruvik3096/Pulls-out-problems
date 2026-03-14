import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os

app = Flask(__name__)
app.secret_key = 'pocketworld_secret_2026'

DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'shopkeeper'
        )
    ''')
    
    # Add email column if it doesn't exist (for existing DBs)
    try:
        conn.execute('ALTER TABLE users ADD COLUMN email TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists
        
    # Add role column if it doesn't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'admin'")
    except sqlite3.OperationalError:
        pass # Column already exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            location TEXT NOT NULL DEFAULT 'Warehouse A'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL,
            supplier TEXT NOT NULL,
            product_id INTEGER,
            quantity INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL,
            destination TEXT NOT NULL,
            product_id INTEGER,
            quantity INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL,
            from_location TEXT NOT NULL,
            to_location TEXT NOT NULL,
            product_id INTEGER,
            quantity INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL,
            product_id INTEGER,
            adjustment INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Seed default admin user
    user = conn.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    if user is None:
        conn.execute('INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)', 
                     ('admin', 'password123', 'admin@pocketworld.local', 'admin'))
    else:
        conn.execute("UPDATE users SET email = 'admin@pocketworld.local', role = 'admin' WHERE username = 'admin'")

    # Seed some demo products if none exist
    products = conn.execute('SELECT * FROM products').fetchall()
    if not products:
        demo_products = [
            ('MacBook Pro 16"', 'MBP-001', 'Electronics', 45, 'Warehouse A'),
            ('USB-C Hub 7-Port', 'USB-HUB-7', 'Accessories', 8, 'Warehouse B'),
            ('Wireless Keyboard', 'KBD-WL-001', 'Peripherals', 120, 'Warehouse A'),
            ('4K Monitor 27"', 'MON-4K-27', 'Electronics', 3, 'Warehouse C'),
            ('Ergonomic Chair', 'CHR-ERG-01', 'Furniture', 25, 'Warehouse B'),
            ('Standing Desk', 'DSK-STD-01', 'Furniture', 0, 'Warehouse A'),
            ('Webcam HD 1080p', 'WBC-HD-01', 'Peripherals', 60, 'Warehouse A'),
            ('NVMe SSD 1TB', 'SSD-1TB-01', 'Storage', 5, 'Warehouse B'),
        ]
        for p in demo_products:
            conn.execute('INSERT INTO products (name, sku, category, quantity, location) VALUES (?, ?, ?, ?, ?)', p)

        # Seed demo receipts
        demo_receipts = [
            ('RCT-001', 'TechSupplier Co.', 1, 10, 'Pending'),
            ('RCT-002', 'AccessoryHub Ltd.', 2, 50, 'Done'),
            ('RCT-003', 'FurniturePro', 5, 5, 'Pending'),
        ]
        for r in demo_receipts:
            conn.execute('INSERT INTO receipts (reference, supplier, product_id, quantity, status) VALUES (?, ?, ?, ?, ?)', r)

        # Seed demo deliveries
        demo_deliveries = [
            ('DLV-001', 'Client A - New York', 3, 5, 'Pending'),
            ('DLV-002', 'Client B - London', 7, 2, 'Done'),
        ]
        for d in demo_deliveries:
            conn.execute('INSERT INTO deliveries (reference, destination, product_id, quantity, status) VALUES (?, ?, ?, ?, ?)', d)

        # Seed demo transfers
        demo_transfers = [
            ('TRF-001', 'Warehouse A', 'Warehouse B', 1, 3, 'Pending'),
            ('TRF-002', 'Warehouse B', 'Warehouse C', 4, 1, 'Done'),
        ]
        for t in demo_transfers:
            conn.execute('INSERT INTO transfers (reference, from_location, to_location, product_id, quantity, status) VALUES (?, ?, ?, ?, ?, ?)', t)

    conn.commit()
    conn.close()

init_db()

def get_stock_status(quantity):
    if quantity == 0:
        return 'Out of Stock'
    elif quantity < 10:
        return 'Low Stock'
    else:
        return 'In Stock'

# ─── Auth ───────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        role = request.form.get('role', 'shopkeeper')
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template('register.html')
            
        conn = get_db_connection()
        # Check if user already exists
        existing_user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        
        if existing_user:
            conn.close()
            flash("Username or email already exists.", "error")
            return render_template('register.html')
            
        conn.execute('INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)', (username, password, email, role))
        conn.commit()
        conn.close()
        
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username)).fetchone()
        conn.close()
        
        if user:
            import random
            otp = str(random.randint(100000, 999999))
            session['reset_otp'] = otp
            session['reset_user_id'] = user['id']
            
            # Simulate sending email by flashing the code to the UI
            flash(f"Check your email! (Simulated: Your OTP is {otp})", 'info')
            return redirect(url_for('verify_otp'))
        else:
            flash("User not found.", "error")
            
    return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_user_id' not in session or 'reset_otp' not in session:
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == session['reset_otp']:
            session['otp_verified'] = True
            return redirect(url_for('reset_password'))
        else:
            flash("Invalid OTP. Try again.", "error")
            
    return render_template('verify_otp.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'):
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            user_id = session['reset_user_id']
            conn = get_db_connection()
            conn.execute('UPDATE users SET password = ? WHERE id = ?', (new_password, user_id))
            conn.commit()
            conn.close()
            
            # Clear reset session vars
            session.pop('reset_otp', None)
            session.pop('reset_user_id', None)
            session.pop('otp_verified', None)
            
            flash("Password updated successfully! You can now log in.", "success")
            return redirect(url_for('login'))
            
    return render_template('reset_password.html')

# ─── Dashboard ──────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    total_products = len(products)
    low_stock = sum(1 for p in products if p['quantity'] > 0 and p['quantity'] < 10)
    out_of_stock = sum(1 for p in products if p['quantity'] == 0)
    pending_receipts = conn.execute("SELECT COUNT(*) as c FROM receipts WHERE status='Pending'").fetchone()['c']
    pending_deliveries = conn.execute("SELECT COUNT(*) as c FROM deliveries WHERE status='Pending'").fetchone()['c']
    pending_transfers = conn.execute("SELECT COUNT(*) as c FROM transfers WHERE status='Pending'").fetchone()['c']
    conn.close()
    # Convert Row objects to plain dicts for JSON serialization in charts
    products_json = [dict(p) for p in products]
    return render_template('dashboard.html',
        products=products,
        products_json=products_json,
        total_products=total_products,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        pending_receipts=pending_receipts,
        pending_deliveries=pending_deliveries,
        pending_transfers=pending_transfers,
        get_stock_status=get_stock_status
    )

# ─── Products ───────────────────────────────────────────────────────────────

@app.route('/products')
def products():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    return render_template('products.html', products=products, get_stock_status=get_stock_status)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        sku = request.form['sku']
        category = request.form['category']
        quantity = request.form['quantity']
        location = request.form.get('location', 'Warehouse A')
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO products (name, sku, category, quantity, location) VALUES (?, ?, ?, ?, ?)',
                         (name, sku, category, quantity, location))
            conn.commit()
            flash('Product added successfully!')
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            flash('Error: SKU already exists.')
        finally:
            conn.close()
    return render_template('add_product.html')

@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    new_quantity = request.form['quantity']
    conn = get_db_connection()
    conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (new_quantity, id))
    conn.commit()
    conn.close()
    flash('Product updated!')
    return redirect(url_for('dashboard'))

@app.route('/delete_product/<int:id>')
def delete_product(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Product deleted!')
    return redirect(url_for('dashboard'))

# ─── Receipts ───────────────────────────────────────────────────────────────

@app.route('/receipts', methods=['GET', 'POST'])
def receipts():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    
    if request.method == 'POST':
        product_id = request.form['product_id']
        supplier = request.form['supplier']
        quantity = int(request.form['quantity'])
        
        # Generate generic reference if none provided
        ref = request.form.get('reference') 
        if not ref:
            ref = f"RCV-{conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]+1:04d}"
            
        conn.execute('INSERT INTO receipts (reference, product_id, supplier, quantity, status) VALUES (?, ?, ?, ?, ?)',
                     (ref, product_id, supplier, quantity, 'Done'))
        conn.execute('UPDATE products SET quantity = quantity + ? WHERE id = ?', (quantity, product_id))
        conn.commit()
        flash('Receipt added successfully!')
        return redirect(url_for('receipts'))

    products = conn.execute('SELECT id, name FROM products ORDER BY name').fetchall()
    
    rows = conn.execute('''
        SELECT r.*, p.name as product_name FROM receipts r
        LEFT JOIN products p ON r.product_id = p.id
        ORDER BY r.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('receipts.html', receipts=rows, products=products)

# ─── Deliveries ─────────────────────────────────────────────────────────────

@app.route('/deliveries', methods=['GET', 'POST'])
def deliveries():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    
    if request.method == 'POST':
        product_id = request.form['product_id']
        customer = request.form['customer']
        quantity = int(request.form['quantity'])
        
        # Generate generic reference if none provided
        ref = request.form.get('reference') 
        if not ref:
            ref = f"DEL-{conn.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0]+1:04d}"
            
        # The schema uses 'destination' not 'customer'
        conn.execute('INSERT INTO deliveries (reference, product_id, destination, quantity, status) VALUES (?, ?, ?, ?, ?)',
                     (ref, product_id, customer, quantity, 'Dispatched'))
        conn.execute('UPDATE products SET quantity = MAX(0, quantity - ?) WHERE id = ?', (quantity, product_id))
        conn.commit()
        flash('Delivery dispatched successfully!')
        return redirect(url_for('deliveries'))

    products = conn.execute('SELECT id, name, quantity FROM products WHERE quantity > 0 ORDER BY name').fetchall()
    
    rows = conn.execute('''
        SELECT d.*, p.name as product_name FROM deliveries d
        LEFT JOIN products p ON d.product_id = p.id
        ORDER BY d.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('deliveries.html', deliveries=rows, products=products)

# ─── Transfers ──────────────────────────────────────────────────────────────

@app.route('/transfers', methods=['GET', 'POST'])
def transfers():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    
    if request.method == 'POST':
        product_id = request.form['product_id']
        destination = request.form['destination']
        quantity = int(request.form['quantity'])
        
        # Generate generic reference if none provided
        ref = request.form.get('reference') 
        if not ref:
            ref = f"TRN-{conn.execute('SELECT COUNT(*) FROM transfers').fetchone()[0]+1:04d}"
        
        # Get the current location of the product to log 'from_location'
        current_loc = conn.execute('SELECT location FROM products WHERE id = ?', (product_id,)).fetchone()
        from_loc = current_loc[0] if current_loc else 'System'
            
        # The schema uses 'to_location' and 'from_location'
        conn.execute('INSERT INTO transfers (reference, product_id, from_location, to_location, quantity, status) VALUES (?, ?, ?, ?, ?, ?)',
                     (ref, product_id, from_loc, destination, quantity, 'Completed'))
                     
        # For this simple system, a transfer updates the primary location of the product
        conn.execute('UPDATE products SET location = ? WHERE id = ?', (destination, product_id))
        conn.commit()
        
        flash(f'Transferred to {destination} successfully!')
        return redirect(url_for('transfers'))

    products = conn.execute('SELECT id, name, location, quantity FROM products WHERE quantity > 0 ORDER BY name').fetchall()
    
    rows = conn.execute('''
        SELECT t.*, p.name as product_name FROM transfers t
        LEFT JOIN products p ON t.product_id = p.id
        ORDER BY t.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('transfers.html', transfers=rows, products=products)

# ─── Stock Adjustment ───────────────────────────────────────────────────────

@app.route('/stock_adjustment', methods=['GET', 'POST'])
def stock_adjustment():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        product_id = request.form['product_id']
        adjustment = int(request.form['adjustment'])
        reason = request.form.get('reason', '')
        ref = f"ADJ-{conn.execute('SELECT COUNT(*) FROM stock_adjustments').fetchone()[0]+1:03d}"
        conn.execute('INSERT INTO stock_adjustments (reference, product_id, adjustment, reason) VALUES (?, ?, ?, ?)',
                     (ref, product_id, adjustment, reason))
        conn.execute('UPDATE products SET quantity = MAX(0, quantity + ?) WHERE id = ?', (adjustment, product_id))
        conn.commit()
        flash('Stock adjustment applied!')
        return redirect(url_for('stock_adjustment'))
    products = conn.execute('SELECT * FROM products').fetchall()
    adjustments = conn.execute('''
        SELECT sa.*, p.name as product_name FROM stock_adjustments sa
        LEFT JOIN products p ON sa.product_id = p.id
        ORDER BY sa.created_at DESC LIMIT 20
    ''').fetchall()
    conn.close()
    return render_template('stock_adjustment.html', products=products, adjustments=adjustments)

# ─── Settings ───────────────────────────────────────────────────────────────

@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Optional: Retrieve user role to display in settings if wanted, here we just return username
    return render_template('settings.html', username=session.get('username'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
