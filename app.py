"""
Vehicle Service Management System
---------------------------------
A simple Flask + MySQL application.

Run:
    pip install flask mysql-connector-python python-dotenv xhtml2pdf
    python app.py
"""

import os
import re
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from io import BytesIO

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash
from xhtml2pdf import pisa

# Load values from the .env file (never hard-code passwords in code)
load_dotenv()

app = Flask(__name__)

_secret = os.environ.get("SECRET_KEY")
if not _secret:
    # Never fall back to a known, guessable key. A random one still works,
    # but everyone gets logged out whenever the server restarts.
    print("WARNING: SECRET_KEY is not set in .env - using a temporary random key.")
    _secret = secrets.token_hex(32)
app.secret_key = _secret
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

STATUSES = ("Pending", "In Progress", "Completed")
PHONE_RE = re.compile(r"^\+?[0-9]{10,13}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VEHICLE_NO_RE = re.compile(r"^[A-Z0-9-]{4,20}$")


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------
def get_db():
    """Create a new MySQL connection using values from .env"""
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "vehicle_service"),
    )


def query(sql, params=(), fetch=None):
    """
    Run a parameterized SQL query (safe against SQL injection).
    fetch = "one" | "all" | None (for INSERT/UPDATE/DELETE)
    The connection is always closed, even if the query fails.
    """
    conn = get_db()
    try:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            conn.commit()
            return None
        finally:
            cur.close()
    finally:
        conn.close()


def exists(table, row_id):
    """True if a row with this id exists. `table` is always a fixed string."""
    return query(f"SELECT id FROM {table} WHERE id = %s", (row_id,), fetch="one") is not None


def is_id(value):
    return bool(value) and value.isdigit()


@app.errorhandler(mysql.connector.Error)
def database_error(err):
    """Any database problem we did not handle ourselves ends up here."""
    app.logger.error("Database error: %s", err)
    return (
        "Database error. Please make sure MySQL is running and try again.",
        500,
    )


# ---------------------------------------------------------------------------
# CSRF protection (stops other websites from submitting forms for the admin)
# ---------------------------------------------------------------------------
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST":
        expected = session.get("csrf_token")
        sent = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400, "Invalid or missing form token. Reload the page and try again.")


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------
def render_pdf(template_name, **context):
    """Render a template to HTML, then convert it to a PDF in memory."""
    html = render_template(template_name, **context)
    pdf_buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=pdf_buffer)
    if result.err:
        return None
    pdf_buffer.seek(0)
    return pdf_buffer


def send_pdf(template_name, filename, back_url, **context):
    pdf = render_pdf(template_name, **context)
    if pdf is None:
        flash("Could not create the PDF. Please try again.", "error")
        return redirect(back_url)
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Login protection
# ---------------------------------------------------------------------------
def login_required(view):
    """Decorator: send the user to the login page if not logged in."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def check_admin_login(username, password):
    """
    Preferred: ADMIN_PASSWORD_HASH in .env (a hashed password).
    Fallback:  ADMIN_PASSWORD in .env (plain text) so old setups keep working.
    """
    admin_user = os.environ.get("ADMIN_USER", "")
    if not admin_user or not secrets.compare_digest(
        username.encode(), admin_user.encode()
    ):
        return False

    password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    if password_hash:
        return check_password_hash(password_hash, password)

    plain = os.environ.get("ADMIN_PASSWORD", "")
    return bool(plain) and secrets.compare_digest(password.encode(), plain.encode())


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("admin"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if check_admin_login(username, password):
            session.clear()  # start a fresh session after login
            session["admin"] = username
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    counts = query(
        """SELECT
               (SELECT COUNT(*) FROM customers) AS customers,
               (SELECT COUNT(*) FROM vehicles)  AS vehicles,
               COUNT(*)                                            AS services,
               COALESCE(SUM(status = 'Completed'), 0)              AS completed,
               COALESCE(SUM(status = 'Pending'), 0)                AS pending,
               COALESCE(SUM(status = 'In Progress'), 0)            AS in_progress,
               COALESCE(SUM(CASE WHEN status = 'Completed'
                                 THEN cost END), 0)                AS revenue
           FROM services""",
        fetch="one",
    )
    stats = counts

    # Latest 5 service records for a quick overview
    recent = query(
        """SELECT s.id, s.service_type, s.service_date, s.cost, s.status,
                  v.vehicle_number, c.name AS customer_name
           FROM services s
           JOIN vehicles v ON v.id = s.vehicle_id
           JOIN customers c ON c.id = v.customer_id
           ORDER BY s.service_date DESC, s.id DESC
           LIMIT 5""",
        fetch="all",
    )
    return render_template("dashboard.html", stats=stats, recent=recent)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@app.route("/customers")
@login_required
def customers():
    search = request.args.get("search", "").strip()
    if search:
        rows = query(
            """SELECT * FROM customers
               WHERE name LIKE %s OR phone LIKE %s
               ORDER BY id DESC""",
            (f"%{search}%", f"%{search}%"),
            fetch="all",
        )
    else:
        rows = query("SELECT * FROM customers ORDER BY id DESC", fetch="all")

    # If an "edit" id is given, load that customer into the form
    edit_id = request.args.get("edit")
    editing = None
    if is_id(edit_id):
        editing = query(
            "SELECT * FROM customers WHERE id = %s", (edit_id,), fetch="one"
        )

    return render_template(
        "customers.html", customers=rows, editing=editing, search=search
    )


@app.route("/customers/save", methods=["POST"])
@login_required
def save_customer():
    customer_id = request.form.get("id", "").strip()
    if not is_id(customer_id):
        customer_id = ""
    name = request.form.get("name", "").strip()
    phone = re.sub(r"[\s-]", "", request.form.get("phone", ""))
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()

    back = url_for("customers", edit=customer_id) if customer_id else url_for("customers")

    error = None
    if not name or not phone:
        error = "Name and phone are required."
    elif len(name) > 100:
        error = "Name is too long (max 100 characters)."
    elif not PHONE_RE.match(phone):
        error = "Enter a valid phone number (10 to 13 digits)."
    elif email and (len(email) > 100 or not EMAIL_RE.match(email)):
        error = "Enter a valid email address."
    elif len(address) > 255:
        error = "Address is too long (max 255 characters)."

    if error:
        flash(error, "error")
        return redirect(back)

    if customer_id:
        if not exists("customers", customer_id):
            flash("Customer not found.", "error")
            return redirect(url_for("customers"))
        query(
            """UPDATE customers SET name=%s, phone=%s, email=%s, address=%s
               WHERE id=%s""",
            (name, phone, email or None, address or None, customer_id),
        )
        flash("Customer updated.", "success")
    else:
        query(
            "INSERT INTO customers (name, phone, email, address) VALUES (%s,%s,%s,%s)",
            (name, phone, email or None, address or None),
        )
        flash("Customer added.", "success")

    return redirect(url_for("customers"))


@app.route("/customers/delete/<int:customer_id>", methods=["POST"])
@login_required
def delete_customer(customer_id):
    count = query(
        "SELECT COUNT(*) AS n FROM vehicles WHERE customer_id = %s",
        (customer_id,),
        fetch="one",
    )["n"]
    if count:
        flash(
            f"Cannot delete: this customer still has {count} vehicle(s). "
            "Delete those vehicles first.",
            "error",
        )
        return redirect(url_for("customers"))

    query("DELETE FROM customers WHERE id = %s", (customer_id,))
    flash("Customer deleted.", "success")
    return redirect(url_for("customers"))


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------
@app.route("/vehicles")
@login_required
def vehicles():
    search = request.args.get("search", "").strip()
    base_sql = """SELECT v.*, c.name AS customer_name
                  FROM vehicles v
                  JOIN customers c ON c.id = v.customer_id"""

    if search:
        rows = query(
            base_sql
            + " WHERE v.vehicle_number LIKE %s OR c.name LIKE %s ORDER BY v.id DESC",
            (f"%{search}%", f"%{search}%"),
            fetch="all",
        )
    else:
        rows = query(base_sql + " ORDER BY v.id DESC", fetch="all")

    edit_id = request.args.get("edit")
    editing = None
    if is_id(edit_id):
        editing = query("SELECT * FROM vehicles WHERE id = %s", (edit_id,), fetch="one")

    customer_list = query("SELECT id, name FROM customers ORDER BY name", fetch="all")
    return render_template(
        "vehicles.html",
        vehicles=rows,
        customers=customer_list,
        editing=editing,
        search=search,
    )


@app.route("/vehicles/save", methods=["POST"])
@login_required
def save_vehicle():
    vehicle_id = request.form.get("id", "").strip()
    if not is_id(vehicle_id):
        vehicle_id = ""
    customer_id = request.form.get("customer_id", "").strip()
    vehicle_number = re.sub(r"\s+", "", request.form.get("vehicle_number", "")).upper()
    model = request.form.get("model", "").strip()
    vehicle_type = request.form.get("vehicle_type", "").strip()

    back = url_for("vehicles", edit=vehicle_id) if vehicle_id else url_for("vehicles")

    error = None
    if not customer_id or not vehicle_number:
        error = "Customer and vehicle number are required."
    elif not is_id(customer_id) or not exists("customers", customer_id):
        error = "Please select a valid customer."
    elif not VEHICLE_NO_RE.match(vehicle_number):
        error = "Vehicle number can only have letters, digits and '-' (4 to 20 characters)."
    elif len(model) > 50 or len(vehicle_type) > 30:
        error = "Model (max 50) or vehicle type (max 30) is too long."

    if error:
        flash(error, "error")
        return redirect(back)

    try:
        if vehicle_id:
            if not exists("vehicles", vehicle_id):
                flash("Vehicle not found.", "error")
                return redirect(url_for("vehicles"))
            query(
                """UPDATE vehicles SET customer_id=%s, vehicle_number=%s,
                   model=%s, vehicle_type=%s WHERE id=%s""",
                (customer_id, vehicle_number, model, vehicle_type, vehicle_id),
            )
            flash("Vehicle updated.", "success")
        else:
            query(
                """INSERT INTO vehicles (customer_id, vehicle_number, model, vehicle_type)
                   VALUES (%s,%s,%s,%s)""",
                (customer_id, vehicle_number, model, vehicle_type),
            )
            flash("Vehicle added.", "success")
    except mysql.connector.IntegrityError:
        # vehicle_number is UNIQUE in the database
        flash(f"A vehicle with number {vehicle_number} is already registered.", "error")
        return redirect(back)

    return redirect(url_for("vehicles"))


@app.route("/vehicles/delete/<int:vehicle_id>", methods=["POST"])
@login_required
def delete_vehicle(vehicle_id):
    count = query(
        "SELECT COUNT(*) AS n FROM services WHERE vehicle_id = %s",
        (vehicle_id,),
        fetch="one",
    )["n"]
    if count:
        flash(
            f"Cannot delete: this vehicle has {count} service record(s). "
            "Delete those service records first.",
            "error",
        )
        return redirect(url_for("vehicles"))

    query("DELETE FROM vehicles WHERE id = %s", (vehicle_id,))
    flash("Vehicle deleted.", "success")
    return redirect(url_for("vehicles"))


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
def parse_cost(value):
    """Return the cost as a Decimal with 2 places, or None if it is invalid."""
    try:
        cost = Decimal((value or "").strip() or "0")
    except InvalidOperation:
        return None
    if not cost.is_finite() or cost < 0 or cost > Decimal("99999999.99"):
        return None
    return cost.quantize(Decimal("0.01"))


@app.route("/services")
@login_required
def services():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    sql = """SELECT s.*, v.vehicle_number, c.name AS customer_name
             FROM services s
             JOIN vehicles v ON v.id = s.vehicle_id
             JOIN customers c ON c.id = v.customer_id"""
    where, params = [], []
    if search:
        where.append("(v.vehicle_number LIKE %s OR c.name LIKE %s)")
        params += [f"%{search}%", f"%{search}%"]
    if status_filter in STATUSES:
        where.append("s.status = %s")
        params.append(status_filter)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.service_date DESC, s.id DESC"
    rows = query(sql, tuple(params), fetch="all")

    edit_id = request.args.get("edit")
    editing = None
    if is_id(edit_id):
        editing = query("SELECT * FROM services WHERE id = %s", (edit_id,), fetch="one")

    vehicle_list = query(
        """SELECT v.id, v.vehicle_number, c.name AS customer_name
           FROM vehicles v JOIN customers c ON c.id = v.customer_id
           ORDER BY v.vehicle_number""",
        fetch="all",
    )
    return render_template(
        "services.html",
        services=rows,
        vehicles=vehicle_list,
        editing=editing,
        search=search,
        status_filter=status_filter,
        statuses=STATUSES,
    )


@app.route("/services/save", methods=["POST"])
@login_required
def save_service():
    service_id = request.form.get("id", "").strip()
    if not is_id(service_id):
        service_id = ""
    vehicle_id = request.form.get("vehicle_id", "").strip()
    service_type = request.form.get("service_type", "").strip()
    service_date = request.form.get("service_date", "").strip()
    status = request.form.get("status", "Pending")
    cost = parse_cost(request.form.get("cost", "0"))

    back = url_for("services", edit=service_id) if service_id else url_for("services")

    error = None
    if not vehicle_id or not service_type or not service_date:
        error = "Vehicle, service type and date are required."
    elif not is_id(vehicle_id) or not exists("vehicles", vehicle_id):
        error = "Please select a valid vehicle."
    elif len(service_type) > 100:
        error = "Service type is too long (max 100 characters)."
    elif cost is None:
        error = "Cost must be a number that is zero or more."
    elif status not in STATUSES:
        error = "Invalid status."
    else:
        try:
            datetime.strptime(service_date, "%Y-%m-%d")
        except ValueError:
            error = "Enter a valid service date."

    if error:
        flash(error, "error")
        return redirect(back)

    if service_id:
        if not exists("services", service_id):
            flash("Service record not found.", "error")
            return redirect(url_for("services"))
        query(
            """UPDATE services SET vehicle_id=%s, service_type=%s,
               service_date=%s, cost=%s, status=%s WHERE id=%s""",
            (vehicle_id, service_type, service_date, cost, status, service_id),
        )
        flash("Service record updated.", "success")
    else:
        query(
            """INSERT INTO services (vehicle_id, service_type, service_date, cost, status)
               VALUES (%s,%s,%s,%s,%s)""",
            (vehicle_id, service_type, service_date, cost, status),
        )
        flash("Service record added.", "success")

    return redirect(url_for("services"))


@app.route("/services/delete/<int:service_id>", methods=["POST"])
@login_required
def delete_service(service_id):
    query("DELETE FROM services WHERE id = %s", (service_id,))
    flash("Service record deleted.", "success")
    return redirect(url_for("services"))


# ---------------------------------------------------------------------------
# PDF downloads
# ---------------------------------------------------------------------------
@app.route("/services/invoice/<int:service_id>")
@login_required
def service_invoice(service_id):
    service = query(
        """SELECT s.*, v.vehicle_number, v.model, v.vehicle_type,
                  c.name AS customer_name, c.phone, c.email, c.address
           FROM services s
           JOIN vehicles v ON v.id = s.vehicle_id
           JOIN customers c ON c.id = v.customer_id
           WHERE s.id = %s""",
        (service_id,),
        fetch="one",
    )
    if not service:
        flash("Service record not found.", "error")
        return redirect(url_for("services"))

    # An invoice only makes sense once the work is finished
    if service["status"] != "Completed":
        flash("An invoice can only be generated for Completed services.", "error")
        return redirect(url_for("services"))

    return send_pdf(
        "invoice.html",
        f"invoice_{service_id:05d}.pdf",
        url_for("services"),
        service=service,
        invoice_no=f"INV-{service_id:05d}",
        invoice_date=date.today(),
    )


@app.route("/vehicles/export")
@login_required
def export_vehicles():
    rows = query(
        """SELECT v.*, c.name AS customer_name
           FROM vehicles v JOIN customers c ON c.id = v.customer_id
           ORDER BY v.id DESC""",
        fetch="all",
    )
    table_rows = [
        [v["id"], v["vehicle_number"], v["model"], v["vehicle_type"], v["customer_name"]]
        for v in rows
    ]
    return send_pdf(
        "list_pdf.html",
        "vehicle_list.pdf",
        url_for("vehicles"),
        title="Vehicle List",
        columns=["ID", "Vehicle No.", "Model", "Type", "Customer"],
        rows=table_rows,
    )


@app.route("/services/export")
@login_required
def export_services():
    rows = query(
        """SELECT s.*, v.vehicle_number, c.name AS customer_name
           FROM services s
           JOIN vehicles v ON v.id = s.vehicle_id
           JOIN customers c ON c.id = v.customer_id
           ORDER BY s.service_date DESC, s.id DESC""",
        fetch="all",
    )
    table_rows = [
        [
            s["id"],
            s["customer_name"],
            s["vehicle_number"],
            s["service_type"],
            s["service_date"],
            f"Rs. {s['cost']}",
            s["status"],
        ]
        for s in rows
    ]
    return send_pdf(
        "list_pdf.html",
        "service_records.pdf",
        url_for("services"),
        title="Service Records",
        columns=["ID", "Customer", "Vehicle No.", "Service", "Date", "Cost", "Status"],
        rows=table_rows,
    )


if __name__ == "__main__":
    # Debug mode only when you explicitly ask for it in .env (FLASK_DEBUG=1)
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
