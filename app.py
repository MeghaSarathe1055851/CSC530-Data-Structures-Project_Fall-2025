from flask import Flask, render_template, request, redirect, session, flash
import json
import random
import datetime
from functools import wraps
import heapq

app = Flask(__name__)
app.secret_key = "your-secret-key"

# ============================== FILE PATHS ==============================

PRODUCTS_FILE = "products.json"
USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

# ============================== LOAD & SAVE ==============================

def load_data(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

products = load_data(PRODUCTS_FILE, {})
users = load_data(USERS_FILE, {})
orders = load_data(ORDERS_FILE, {})

# ensure order history exists
for uid in users:
    users[uid].setdefault("order_history", [])

# ============================== AUTH CHECK ==============================

def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.")
                return redirect("/")
            if users[session["user_id"]]["role"] != role:
                flash("Unauthorized access.")
                return redirect("/")
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ============================== LOGIN ==============================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid = request.form["user_id"].strip()
        pwd = request.form["password"]

        if not uid.isdigit() or not (1000 <= int(uid) <= 9999):
            flash("User ID must be a 4-digit number.")
            return redirect("/")

        if uid in users and users[uid]["password"] == pwd:
            session["user_id"] = uid
            return redirect("/admin" if users[uid]["role"] == "admin" else "/customer")

        flash("Invalid credentials.")
        return redirect("/")

    return render_template("index.html")

# ============================== REGISTER ==============================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uid = request.form["user_id"].strip()
        name = request.form["name"]
        role = request.form["role"]
        pwd = request.form["password"]

        if not uid.isdigit() or not (1000 <= int(uid) <= 9999):
            flash("User ID must be a 4-digit number.")
            return redirect("/register")

        if uid in users:
            flash("User ID already exists.")
            return redirect("/register")

        users[uid] = {
            "id": uid,
            "name": name,
            "role": role,
            "password": pwd,
            "order_history": []
        }

        save_data(USERS_FILE, users)
        flash("Registration successful!")
        return redirect("/")

    return render_template("register.html")

# ============================== LOGOUT ==============================

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect("/")

# ============================== ADMIN DASHBOARD ==============================

@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    out_of_stock = [p for p in products.values() if p["quantity"] <= 0]
    total_orders = len(orders)
    total_revenue = sum(o["total"] for o in orders.values())

    freq = {}
    for o in orders.values():
        for pid, qty in o["items"].items():
            freq[pid] = freq.get(pid, 0) + qty

    most_frequent = ("None", 0)
    if freq:
        most_frequent = max(freq.items(), key=lambda x: x[1])

    return render_template(
        "admin.html",
        products=products.values(),
        out_of_stock=out_of_stock,
        total_orders=total_orders,
        total_revenue=total_revenue,
        most_frequent=most_frequent
    )

# ============================== OUT OF STOCK ==============================

@app.route("/admin/out_of_stock")
@role_required("admin")
def view_out_of_stock():
    items = [p for p in products.values() if p["quantity"] <= 0]
    return render_template("out_of_stock.html", products=items)

# ============================== REVENUE REPORT ==============================

@app.route("/admin/revenue_report")
@role_required("admin")
def revenue_report():
    report = list(orders.values())
    for r in report:
        r["customer_name"] = users[r["customer_id"]]["name"]
    return render_template("revenue_report.html", orders=report)

# ============================== TOP PRODUCT ==============================

@app.route("/admin/top_product")
@role_required("admin")
def top_product():
    freq = {}
    for o in orders.values():
        for pid, qty in o["items"].items():
            freq[pid] = freq.get(pid, 0) + qty

    if not freq:
        flash("No product sales recorded yet.")
        return redirect("/admin")

    pid = max(freq, key=freq.get)
    return render_template(
        "top_product.html",
        product=products[pid],
        total_sold=freq[pid],
        orders=orders,
        users=users
    )

# ============================== ADD PRODUCT ==============================

@app.route("/admin/add_product", methods=["POST"])
@role_required("admin")
def add_product():
    name = request.form["name"]
    category = request.form["category"]
    price = float(request.form["price"])
    qty = int(request.form["quantity"])

    pid = str(random.randint(10000, 99999))
    while pid in products:
        pid = str(random.randint(10000, 99999))

    products[pid] = {
        "id": pid,
        "name": name,
        "category": category,
        "price": price,
        "quantity": qty,
        "reviews": [],
        "visible_to_customers": True
    }
    save_data(PRODUCTS_FILE, products)

    flash("Product added successfully!")
    return redirect("/admin")

# ============================== UPDATE PRODUCT ==============================

@app.route("/admin/update_product", methods=["POST"])
@role_required("admin")
def update_product():
    pid = request.form["product_id"]
    products[pid]["name"] = request.form["name"]
    products[pid]["category"] = request.form["category"]
    products[pid]["price"] = float(request.form["price"])
    products[pid]["quantity"] = int(request.form["quantity"])

    save_data(PRODUCTS_FILE, products)
    flash("Product updated.")
    return redirect("/admin")

# ============================== DELETE PRODUCT ==============================

@app.route("/admin/delete_product", methods=["POST"])
@role_required("admin")
def delete_product():
    pid = request.form["product_id"]
    confirm = request.form.get("confirm", "no")

    if confirm == "yes":
        products.pop(pid, None)
        save_data(PRODUCTS_FILE, products)
        flash("Product deleted.")

    return redirect("/admin")

# ============================== SORT PRODUCTS ==============================

@app.route("/admin/view_products_sorted")
@role_required("admin")
def sorted_products():
    prod = list(products.values())
    heap = [(p["price"], random.random(), p) for p in prod]
    heapq.heapify(heap)
    sorted_list = [heapq.heappop(heap)[2] for _ in range(len(heap))]

    return render_template(
        "admin.html",
        products=sorted_list,
        out_of_stock=[p for p in products.values() if p["quantity"] <= 0],
        total_orders=len(orders),
        total_revenue=sum(o["total"] for o in orders.values()),
        most_frequent=("None", 0)
    )

# ============================== SEARCH PRODUCT ==============================

@app.route("/admin/search_product")
@role_required("admin")
def search_product():
    q = request.args.get("query", "").lower()
    results = [p for p in products.values() if q in p["name"].lower()]

    return render_template(
        "admin.html",
        products=results,
        out_of_stock=[p for p in products.values() if p["quantity"] <= 0],
        total_orders=len(orders),
        total_revenue=sum(o["total"] for o in orders.values()),
        most_frequent=("None", 0)
    )

# ============================== ADMIN VIEW ORDERS ==============================

@app.route("/admin/view_orders")
@role_required("admin")
def admin_orders():
    return render_template(
        "orders.html",
        orders=orders.values(),
        users=users,
        products=products
    )

# ============================== UPDATE ORDER STATUS ==============================

@app.route("/admin/update_order_status", methods=["POST"])
@role_required("admin")
def update_order_status():
    oid = request.form["order_id"]
    status = request.form["status"]

    if oid in orders:
        orders[oid]["status"] = status
        save_data(ORDERS_FILE, orders)
        flash("Order status updated.")

    return redirect("/admin/view_orders")

# ============================== CUSTOMER DASHBOARD ==============================

@app.route("/customer")
@role_required("customer")
def customer_dashboard():
    user = users[session["user_id"]]
    return render_template("customer.html", user=user)

# ============================== BROWSE PRODUCTS ==============================

@app.route("/browse")
@role_required("customer")
def browse():
    prods = [p for p in products.values() if p.get("visible_to_customers", True)]

    # Read filters
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort = request.args.get("sort")

    # Apply MIN filter if number provided
    if min_price:
        try:
            min_p = float(min_price)
            prods = [p for p in prods if p["price"] >= min_p]
        except:
            pass

    # Apply MAX filter if number provided
    if max_price:
        try:
            max_p = float(max_price)
            prods = [p for p in prods if p["price"] <= max_p]
        except:
            pass

    # Sort by price
    if sort == "price":
        prods = sorted(prods, key=lambda x: x["price"])

    # ================== Reviewable Products for Customer ==================
    reviewable_products = set()
    user_orders = users[session['user_id']]['order_history']

    for oid in user_orders:
        if oid in orders:
            order = orders[oid]
            if order['status'] == "delivered":
                for pid in order['items']:
                    reviewable_products.add(pid)

    # ================== RETURN TEMPLATE ==================
    return render_template(
        "browse.html",
        products=prods,
        min_price=min_price,
        max_price=max_price,
        reviewable_products=reviewable_products
    )

# ============================== SEARCH ==============================

@app.route("/search")
@role_required("customer")
def search():
    q = request.args.get("query", "").lower()
    results = [p for p in products.values()
               if p.get("visible_to_customers", True)
               and q in p["name"].lower()]

    return render_template("browse.html", products=results)

# ============================== CART PAGE ==============================

@app.route("/cart")
@role_required("customer")
def cart():
    cart = session.get("cart", {})
    items = []
    subtotal = 0

    for pid, qty in cart.items():
        p = products.get(pid)
        if p:
            items.append({"product": p, "quantity": qty})
            subtotal += p["price"] * qty

    # If coupon already applied, load discount
    discount = session.get("discount_amount", 0)

    # Apply 6% flat tax
    tax = round((subtotal - discount) * 0.06, 2)
    total = round(subtotal - discount + tax, 2)

    is_first_order = (len(users[session["user_id"]]["order_history"]) == 0)

    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=total,
        is_first_order=is_first_order,
    )

# ============================== APPLY COUPON ==============================

@app.route("/apply_coupon", methods=["POST"])
@role_required("customer")
def apply_coupon():
    code = request.form.get("discount_code", "").strip().upper()
    user_id = session["user_id"]
    is_first_order = len(users[user_id]["order_history"]) == 0

    session["discount_amount"] = 0  # reset before applying

    if not code:
        flash("Enter a coupon code.", "danger")
        return redirect("/cart")

    if not is_first_order:
        flash("Coupons are only valid for your first purchase.", "warning")
        return redirect("/cart")

    # VALID COUPONS
    cart = session.get("cart", {})
    subtotal = sum(products[pid]["price"] * qty for pid, qty in cart.items())

    if code == "WELCOME10":
        session["discount_amount"] = 10
        flash("Coupon applied! You saved $10.", "success")

    elif code == "FIRST25":
        session["discount_amount"] = round(subtotal * 0.25, 2)
        flash("25% discount applied!", "success")

    else:
        flash("Invalid coupon code.", "danger")

    return redirect("/cart")

# ============================== ADD TO CART ==============================

@app.route("/cart/add", methods=["POST"])
@role_required("customer")
def add_to_cart():
    pid = request.form["product_id"]
    qty = int(request.form["quantity"])

    if pid not in products or products[pid]["quantity"] < qty:
        flash("Not enough stock available.", "danger")
        return redirect("/browse")

    cart = session.setdefault("cart", {})
    cart[pid] = cart.get(pid, 0) + qty
    session.modified = True

    flash("Product added to cart!", "success")
    return redirect("/cart")

# ============================== REMOVE FROM CART ==============================

@app.route("/cart/remove", methods=["POST"])
@role_required("customer")
def remove_from_cart():
    pid = request.form["product_id"]
    if "cart" in session and pid in session["cart"]:
        del session["cart"][pid]
        session.modified = True

    flash("Item removed from cart.", "info")
    return redirect("/cart")

# ============================== PLACE ORDER ==============================

@app.route("/place_order", methods=["POST"])
@role_required("customer")
def place_order():
    user_id = session["user_id"]
    address = request.form["address"]

    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect("/cart")

    # STOCK VALIDATION
    for pid, qty in cart.items():
        if products[pid]["quantity"] < qty:
            flash(f"Not enough stock for {products[pid]['name']}.", "danger")
            return redirect("/cart")

    subtotal = sum(products[pid]["price"] * qty for pid, qty in cart.items())
    discount = session.get("discount_amount", 0)

    # TAX = 6%
    tax = round((subtotal - discount) * 0.06, 2)
    total = round(subtotal - discount + tax, 2)

    # CREATE ORDER ID
    oid = str(random.randint(100000, 999999))

    orders[oid] = {
        "id": oid,
        "customer_id": user_id,
        "items": cart.copy(),
        "total": total,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "placed",
        "address": address
    }

    # ADD ORDER TO USER HISTORY
    users[user_id]["order_history"].append(oid)

    # REDUCE STOCK
    for pid, qty in cart.items():
        products[pid]["quantity"] -= qty

    # SAVE FILES
    save_data(ORDERS_FILE, orders)
    save_data(PRODUCTS_FILE, products)
    save_data(USERS_FILE, users)

    # CLEAR CART + COUPON
    session.pop("cart", None)
    session.pop("discount_amount", None)

    flash("Order placed successfully!", "success")
    return redirect("/order_history")

# ============================== ORDER HISTORY ==============================

@app.route("/order_history")
@role_required("customer")
def order_history():
    user_id = session["user_id"]
    history = [orders[oid] for oid in users[user_id]["order_history"] if oid in orders]

    return render_template(
        "history.html",
        orders=history,
        products=products
    )

# ============================== ADD REVIEW ==============================

@app.route("/add_review", methods=["POST"])
@role_required("customer")
def add_review():
    pid = request.form["product_id"]
    review = request.form["review"]

    if pid in products:
        products[pid]["reviews"].append({
            "user": users[session["user_id"]]["name"],
            "text": review
        })
        save_data(PRODUCTS_FILE, products)
        flash("Review added!", "success")

    return redirect("/browse")

# ============================== RUN APP ==============================

if __name__ == "__main__":
    app.run(debug=True)
