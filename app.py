import functools
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
    add_expense_to_db,
    get_category_breakdown,
    get_db,
    get_expense_by_id,
    get_profile_stats,
    get_recent_transactions,
    get_user_by_email,
    get_user_by_id,
    init_db,
    register_user,
    seed_db,
    update_expense_in_db,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Auth helpers                                                        #
# ------------------------------------------------------------------ #


def login_required(f: Callable) -> Callable:
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


# ------------------------------------------------------------------ #
# View helpers                                                        #
# ------------------------------------------------------------------ #


_VALID_PRESETS: set[str] = {"all", "last30", "last90", "last365"}
_PRESET_DAYS: dict[str, int] = {"last30": 30, "last90": 90, "last365": 365}
_VALID_CATEGORIES: list[str] = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def parse_date_filter(args: dict) -> tuple[str | None, str | None]:
    """Parse query-string args into a (start_date, end_date) tuple (YYYY-MM-DD).

    Priority: custom start+end > preset > all-time (None, None).
    Any malformed input falls back to (None, None) gracefully.
    """
    today = date.today()

    # Custom range takes priority if both params parse cleanly
    raw_start = args.get("start", "").strip()
    raw_end = args.get("end", "").strip()
    if raw_start and raw_end:
        try:
            datetime.strptime(raw_start, "%Y-%m-%d")
            datetime.strptime(raw_end, "%Y-%m-%d")
            return raw_start, raw_end
        except ValueError:
            pass  # fall through to preset logic

    preset = args.get("preset", "all")
    if preset in _PRESET_DAYS:
        start = (today - timedelta(days=_PRESET_DAYS[preset])).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        return start, end
    return None, None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name:
        return render_template(
            "register.html", error="Full name is required.", name=name, email=email
        )
    if not email or "@" not in email:
        return render_template(
            "register.html",
            error="A valid email address is required.",
            name=name,
            email=email,
        )
    if len(password) < 8:
        return render_template(
            "register.html",
            error="Password must be at least 8 characters.",
            name=name,
            email=email,
        )

    try:
        register_user(name, email, password)
    except sqlite3.IntegrityError:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name,
            email=email,
        )

    flash("Account created — please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login() -> str | Response:
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "login.html", error="Email and password are required.", email=email
        )

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        )

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/logout")
def logout() -> Response:
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


@app.route("/profile")
@login_required
def profile() -> str:
    user_id: int = session["user_id"]

    db_user = get_user_by_id(user_id)
    if db_user is None:
        session.clear()
        flash("Session invalid — please log in again.")
        return redirect(url_for("login"))

    try:
        member_since = datetime.strptime(
            db_user["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (ValueError, TypeError):
        member_since = "Unknown"

    initials = "".join(w[0].upper() for w in db_user["name"].split()[:2])

    user = {
        "name": db_user["name"],
        "email": db_user["email"],
        "initials": initials,
        "member_since": member_since,
    }
    start_date, end_date = parse_date_filter(request.args)

    # Allowlist the preset so only known values reach the template.
    raw_preset = request.args.get("preset", "all")
    active_preset = raw_preset if raw_preset in _VALID_PRESETS else "all"

    # Format custom date labels as "Month D, YYYY" for display consistency.
    start_label = (
        datetime.strptime(start_date, "%Y-%m-%d").strftime("%B %-d, %Y")
        if start_date and active_preset == "all"
        else None
    )
    end_label = (
        datetime.strptime(end_date, "%Y-%m-%d").strftime("%B %-d, %Y")
        if end_date and active_preset == "all"
        else None
    )

    stats = get_profile_stats(user_id, start=start_date, end=end_date)
    transactions = get_recent_transactions(
        user_id, limit=6, start=start_date, end=end_date
    )
    categories = get_category_breakdown(user_id, start=start_date, end=end_date)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        active_preset=active_preset,
        start_date=start_date,
        end_date=end_date,
        start_label=start_label,
        end_label=end_label,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense() -> str | Response:
    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=_VALID_CATEGORIES,
            today=date.today().isoformat(),
        )

    # --- POST ---
    user_id: int = session["user_id"]
    raw_amount = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    raw_date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    def _err(msg: str) -> str:
        return render_template(
            "add_expense.html",
            categories=_VALID_CATEGORIES,
            error=msg,
            amount=raw_amount,
            category=category,
            date=raw_date,
            description=description,
        )

    # Validate amount
    if not raw_amount:
        return _err("Amount is required.")
    try:
        amount = float(raw_amount)
    except ValueError:
        return _err("Amount must be a valid number.")
    if amount <= 0:
        return _err("Amount must be greater than zero.")

    # Validate category
    if category not in _VALID_CATEGORIES:
        return _err("Please select a valid category.")

    # Validate date
    if not raw_date:
        return _err("Date is required.")
    try:
        datetime.strptime(raw_date, "%Y-%m-%d")
    except ValueError:
        return _err("Please enter a valid date.")

    add_expense_to_db(user_id, amount, category, raw_date, description)
    flash("Expense added successfully.")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id: int) -> str | Response:
    expense = get_expense_by_id(id)
    if expense is None:
        abort(404)
    if expense["user_id"] != session["user_id"]:
        abort(403)

    if request.method == "GET":
        return render_template(
            "edit_expense.html",
            categories=_VALID_CATEGORIES,
            expense=expense,
            amount=expense["amount"],
            category=expense["category"],
            date=expense["date"],
            description=expense["description"] or "",
        )

    # --- POST ---
    raw_amount = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    raw_date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    def _err(msg: str) -> str:
        return render_template(
            "edit_expense.html",
            categories=_VALID_CATEGORIES,
            expense=expense,
            error=msg,
            amount=raw_amount,
            category=category,
            date=raw_date,
            description=description,
        )

    # Validate amount
    if not raw_amount:
        return _err("Amount is required.")
    try:
        amount = float(raw_amount)
    except ValueError:
        return _err("Amount must be a valid number.")
    if amount <= 0:
        return _err("Amount must be greater than zero.")

    # Validate category
    if category not in _VALID_CATEGORIES:
        return _err("Please select a valid category.")

    # Validate date
    if not raw_date:
        return _err("Date is required.")
    try:
        datetime.strptime(raw_date, "%Y-%m-%d")
    except ValueError:
        return _err("Please enter a valid date.")

    update_expense_in_db(id, amount, category, raw_date, description)
    flash("Expense updated successfully.")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
