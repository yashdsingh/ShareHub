from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.utils import secure_filename
import os
import sqlite3

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.secret_key = "sharehub"

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Users Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT,
        role TEXT
    )
    """)

    # Products Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    category TEXT,
    condition TEXT,
    image TEXT,
    donor_id INTEGER
)
""")

    # Requests Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        receiver_id INTEGER,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= HOME =================

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/donor_register", methods=["GET", "POST"])
def donor_register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO users(name, email, password, role)
        VALUES (?, ?, ?, ?)
        """, (name, email, password, "donor"))

        conn.commit()
        conn.close()

        flash("Registration successful! Please log in.", "success")

        return redirect("/donor_login")

    return render_template("donor_register.html")

@app.route("/receiver_register", methods=["GET", "POST"])
def receiver_register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO users(name, email, password, role)
        VALUES (?, ?, ?, ?)
        """, (name, email, password, "receiver"))

        conn.commit()
        conn.close()

        flash("Registration successful! Please log in.", "success")

        return redirect("/receiver_login")

    return render_template("receiver_register.html")

@app.route("/donor_login", methods=["GET", "POST"])
def donor_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM users
        WHERE email=? AND password=? AND role='donor'
        """, (email, password))

        user = cur.fetchone()

        conn.close()

        if user:

            session["user_id"] = user[0]
            session["role"] = user[4]

            return redirect("/dashboard")

        flash("Invalid email or password.", "error")

    return render_template("donor_login.html")

@app.route("/receiver_login", methods=["GET", "POST"])
def receiver_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM users
        WHERE email=? AND password=? AND role='receiver'
        """, (email, password))

        user = cur.fetchone()

        conn.close()

        if user:

            session["user_id"] = user[0]
            session["role"] = user[4]

            return redirect("/dashboard")

        flash("Invalid email or password.", "error")

    return render_template("receiver_login.html")



# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # ================= PRODUCTS =================
    # NOTE: products.donor_id is now included (as product[7]) so the
    # template can check if the logged-in user owns each product.

    cur.execute("""
    SELECT products.id,
           products.title,
           products.description,
           products.category,
           products.condition,
           products.image,
           users.name,
           products.donor_id

    FROM products

    JOIN users
    ON products.donor_id = users.id
    """)

    products = cur.fetchall()

    # ================= REQUESTS =================

    requests_data = []

    if session["role"] == "donor":

        cur.execute("""
        SELECT requests.id,
               products.title,
               receiver.name,
               requests.status

        FROM requests

        JOIN products
        ON requests.product_id = products.id

        JOIN users AS receiver
        ON requests.receiver_id = receiver.id

        WHERE products.donor_id = ?
        """, (session["user_id"],))

        requests_data = cur.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        products=products,
        requests=requests_data,
        role=session["role"],
        current_user_id=session["user_id"]
    )
# ================= ADD PRODUCT =================

@app.route("/add_product", methods=["GET", "POST"])
def add_product():

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        condition = request.form["condition"]

        image = request.files["image"]

        filename = ""

        if image:

            filename = secure_filename(image.filename)

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO products
        (title, description, category, condition, image, donor_id)

        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            title,
            description,
            category,
            condition,
            filename,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        flash("Product added successfully!", "success")

        return redirect("/dashboard")

    return render_template("add_product.html")

# ================= EDIT PRODUCT =================

@app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):

    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Fetch the product first so we can check ownership either way
    cur.execute("""
    SELECT id, title, description, category, condition, image, donor_id
    FROM products
    WHERE id=?
    """, (product_id,))

    product = cur.fetchone()

    # Product doesn't exist, or it doesn't belong to the logged-in user
    if not product or product[6] != session["user_id"]:
        conn.close()
        flash("You don't have permission to edit this product.", "error")
        return redirect("/dashboard")

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        condition = request.form["condition"]

        image = request.files.get("image")
        filename = product[5]  # keep existing image by default

        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        cur.execute("""
        UPDATE products
        SET title=?, description=?, category=?, condition=?, image=?
        WHERE id=?
        """, (title, description, category, condition, filename, product_id))

        conn.commit()
        conn.close()

        flash("Product updated successfully!", "success")

        return redirect("/dashboard")

    conn.close()

    return render_template("edit_product.html", product=product)

# ================= DELETE PRODUCT =================

@app.route("/delete_product/<int:product_id>")
def delete_product(product_id):

    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT donor_id FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()

    if not product or product[0] != session["user_id"]:
        conn.close()
        flash("You don't have permission to delete this product.", "error")
        return redirect("/dashboard")

    # Remove any pending/approved/rejected requests tied to this product first
    cur.execute("DELETE FROM requests WHERE product_id=?", (product_id,))
    cur.execute("DELETE FROM products WHERE id=?", (product_id,))

    conn.commit()
    conn.close()

    flash("Product deleted.", "success")

    return redirect("/dashboard")

# ================= REQUEST PRODUCT =================
@app.route("/request/<int:product_id>")
def request_product(product_id):

    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # CHECK DUPLICATE REQUEST

    cur.execute("""
    SELECT * FROM requests
    WHERE product_id=? AND receiver_id=?
    """, (
        product_id,
        session["user_id"]
    ))

    existing = cur.fetchone()

    if not existing:

        cur.execute("""
        INSERT INTO requests
        (product_id, receiver_id, status)

        VALUES (?, ?, ?)
        """, (
            product_id,
            session["user_id"],
            "Pending"
        ))

        conn.commit()

        flash("Request sent to the donor!", "success")

    else:

        flash("You've already requested this product.", "error")

    conn.close()

    return redirect("/dashboard")

# ================= APPROVE REQUEST =================

@app.route("/approve/<int:req_id>")
def approve(req_id):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    UPDATE requests
    SET status='Approved'
    WHERE id=?
    """, (req_id,))

    conn.commit()
    conn.close()

    flash("Request approved.", "success")

    return redirect("/dashboard")

# ================= REJECT REQUEST =================

@app.route("/reject/<int:req_id>")
def reject(req_id):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    UPDATE requests
    SET status='Rejected'
    WHERE id=?
    """, (req_id,))

    conn.commit()
    conn.close()

    flash("Request rejected.", "error")

    return redirect("/dashboard")

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect("/")

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)