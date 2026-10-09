"""OpportunityHub backend: Flask + MongoDB (PyMongo).

Run with:  python app.py
"""
import hmac
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, current_app, g, jsonify, render_template, request, session
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config

CATEGORIES = ["Internships", "Scholarships", "Hackathons", "Competitions", "Courses", "Jobs"]
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
MAX_TITLE = 120
MAX_DESCRIPTION = 2000
MAX_URL = 500
MAX_SEARCH = 100

# Used so a wrong username takes about as long to reject as a wrong password.
DUMMY_HASH = generate_password_hash("not-a-real-password")

logger = logging.getLogger("opportunityhub")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
class ApiError(Exception):
    """Raised anywhere in a route to send a clean JSON error to the browser."""

    def __init__(self, message, status=400, code=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def json_ok(message, status=200, **extra):
    return jsonify({"success": True, "message": message, **extra}), status


def json_error(message, status, code=None):
    body = {"success": False, "message": message}
    if code:
        body["code"] = code
    return jsonify(body), status


def utcnow():
    """Current UTC time, cut to whole milliseconds (the precision MongoDB stores)."""
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def as_utc(value):
    """Make sure a datetime read from MongoDB is timezone-aware (UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso(value):
    return as_utc(value).isoformat(timespec="milliseconds")


def get_json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be valid JSON.", 400)
    return data


def clean_text(value, label, max_len):
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"{label} is required.", 400)
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(f"{label} must be {max_len} characters or fewer.", 400)
    return value


def parse_object_id(value, label="ID"):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise ApiError(f"Invalid {label}.", 400)


def validate_url(value):
    url = clean_text(value, "Application link", MAX_URL)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or re.search(r"\s", url):
        raise ApiError("Application link must be a valid http:// or https:// URL.", 400)
    return url


def validate_deadline(value):
    value = clean_text(value, "Deadline", 10)
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ApiError("Deadline must be a valid date (YYYY-MM-DD).", 400)
    return value


def validate_opportunity_fields(data, partial=False):
    """Validate the editable opportunity fields. Unknown keys are ignored,
    so protected fields (author, timestamps, status) can never be changed."""
    validators = {
        "title": lambda v: clean_text(v, "Title", MAX_TITLE),
        "category": lambda v: v if v in CATEGORIES else _bad_category(),
        "description": lambda v: clean_text(v, "Description", MAX_DESCRIPTION),
        "deadline": validate_deadline,
        "application_url": validate_url,
    }
    result = {}
    for field, check in validators.items():
        if field in data:
            result[field] = check(data[field])
        elif not partial:
            label = "Application link" if field == "application_url" else field.capitalize()
            raise ApiError(f"{label} is required.", 400)
    if partial and not result:
        raise ApiError("No editable fields were provided.", 400)
    return result


def _bad_category():
    raise ApiError("Please choose a valid category.", 400)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def ensure_indexes(db):
    """Create indexes. Safe to run many times (existing indexes are left alone)."""
    db["users"].create_index("username_normalized", unique=True, name="uniq_username")
    opps = db["opportunities"]
    opps.create_index([("created_at", DESCENDING)], name="created_at_desc")
    opps.create_index([("expires_at", ASCENDING)], name="expires_at_asc")
    opps.create_index([("category", ASCENDING)], name="category_asc")
    opps.create_index([("author_id", ASCENDING)], name="author_id_asc")


def get_db():
    """Return the shared database object. Indexes are created on first use."""
    db = current_app.extensions["db"]
    if not current_app.extensions["indexes_ready"]:
        ensure_indexes(db)
        current_app.extensions["indexes_ready"] = True
    return db


def check_database_on_startup(app):
    """Print a clear message in the terminal about the MongoDB connection."""
    try:
        app.extensions["mongo_client"].admin.command("ping")
        ensure_indexes(app.extensions["db"])
        app.extensions["indexes_ready"] = True
        print(f"[OpportunityHub] Connected to MongoDB database '{app.config['MONGO_DB_NAME']}'.")
    except PyMongoError as exc:
        print("\n" + "=" * 70)
        print("[OpportunityHub] WARNING: Could not connect to MongoDB.")
        print("  - Is MongoDB running (local) or is your Atlas IP address allowed?")
        print("  - Check MONGO_URI in your .env file.")
        print(f"  Details: {type(exc).__name__}")
        print("The website will start, but API calls will return 503 until MongoDB is reachable.")
        print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Opportunity helpers
# ---------------------------------------------------------------------------
def refresh_expired_statuses(db, now):
    """Save status = 'Expired' for listings whose time is up. Nothing is deleted."""
    db["opportunities"].update_many(
        {"status": "Active", "expires_at": {"$lte": now}},
        {"$set": {"status": "Expired"}},
    )


def compute_status(doc, now):
    """The status is always derived from the timestamps, so it can't be wrong."""
    return "Expired" if as_utc(doc["expires_at"]) <= now else "Active"


def serialize_opportunity(doc, now):
    status = compute_status(doc, now)
    expired = status == "Expired"
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "category": doc["category"],
        "description": doc["description"],
        "deadline": doc["deadline"],
        # The link is withheld once the listing has expired.
        "application_url": None if expired else doc["application_url"],
        "author_id": str(doc["author_id"]),
        "author_username": doc["author_username"],
        "created_at": iso(doc["created_at"]),
        "expires_at": iso(doc["expires_at"]),
        "status": status,
        "expired_message": (
            "This opportunity has expired and is no longer accepting applications through OpportunityHub."
            if expired
            else None
        ),
    }


def serialize_user(user):
    return {"id": str(user["_id"]), "name": user["name"], "username": user["username"]}


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------
def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def start_session(user):
    """Log the user in. Only the user's ID is stored in the session."""
    session.clear()
    session["user_id"] = str(user["_id"])
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = True


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        oid = parse_object_id(user_id, "session")
    except ApiError:
        session.clear()
        return None
    user = get_db()["users"].find_one({"_id": oid})
    if user is None:
        session.clear()
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            raise ApiError("Please log in to continue.", 401)
        g.user = user
        return view(*args, **kwargs)

    return wrapper


def int_arg(name, default, minimum, maximum):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(f"'{name}' must be a whole number.", 400)
    return max(minimum, min(maximum, value))


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is missing. Copy .env.example to .env and set SECRET_KEY.")

    # One MongoDB client for the whole app. It is created here once and reused by every route.
    client = MongoClient(
        app.config["MONGO_URI"],
        serverSelectionTimeoutMS=app.config["MONGO_TIMEOUT_MS"],
        tz_aware=True,
    )
    app.extensions["mongo_client"] = client
    app.extensions["db"] = client[app.config["MONGO_DB_NAME"]]
    app.extensions["indexes_ready"] = False

    if not app.config.get("TESTING"):
        check_database_on_startup(app)

    register_hooks(app)
    register_error_handlers(app)
    register_routes(app)
    return app


def register_hooks(app):
    @app.before_request
    def csrf_protect():
        """State-changing API calls must send the X-CSRF-Token header."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/"):
            sent = request.headers.get("X-CSRF-Token", "")
            expected = session.get("csrf_token", "")
            if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
                raise ApiError("Your session has expired. Please try again.", 403, code="csrf_failed")

    @app.after_request
    def no_cache_for_api(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return json_error(err.message, err.status, err.code)

    @app.errorhandler(ConnectionFailure)  # includes ServerSelectionTimeoutError
    def handle_db_down(err):
        logger.error("MongoDB unavailable: %s", type(err).__name__)
        return json_error("The database is currently unavailable. Please try again later.", 503)

    @app.errorhandler(PyMongoError)
    def handle_db_error(err):
        logger.exception("Database error")
        return json_error("A database error occurred. Please try again.", 500)

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        if request.path.startswith("/api/"):
            return json_error(err.description or err.name, err.code)
        return err

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        logger.exception("Unexpected error")
        if request.path.startswith("/api/"):
            return json_error("Something went wrong on the server.", 500)
        return "Internal Server Error", 500


def register_routes(app):
    # ----- Pages and health ------------------------------------------------
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        try:
            current_app.extensions["mongo_client"].admin.command("ping")
            return jsonify({"success": True, "app": "ok", "database": "connected"}), 200
        except PyMongoError:
            return jsonify({"success": False, "app": "ok", "database": "unavailable"}), 503

    @app.get("/api/csrf-token")
    def csrf_token():
        return jsonify({"success": True, "csrf_token": get_csrf_token()})

    # ----- Authentication --------------------------------------------------
    @app.post("/api/auth/register")
    def register():
        data = get_json_body()
        name = clean_text(data.get("name"), "Full name", 60)
        username = clean_text(data.get("username"), "Username", 30)
        if not USERNAME_RE.match(username):
            raise ApiError("Username must be 3-30 characters: letters, numbers and underscores only.", 400)
        password = data.get("password")
        if not isinstance(password, str) or not password:
            raise ApiError("Password is required.", 400)
        if not 6 <= len(password) <= 128:
            raise ApiError("Password must be between 6 and 128 characters.", 400)

        user = {
            "name": name,
            "username": username,
            "username_normalized": username.lower(),
            "password_hash": generate_password_hash(password),
            "created_at": utcnow(),
        }
        try:
            result = get_db()["users"].insert_one(user)
        except DuplicateKeyError:
            raise ApiError("That username is already taken. Please choose another.", 409)
        user["_id"] = result.inserted_id

        start_session(user)
        return json_ok("Account created successfully.", 201,
                       user=serialize_user(user), csrf_token=session["csrf_token"])

    @app.post("/api/auth/login")
    def login():
        data = get_json_body()
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not isinstance(password, str) or not username.strip() or not password:
            raise ApiError("Username and password are required.", 400)

        user = get_db()["users"].find_one({"username_normalized": username.strip().lower()})
        password_ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)
        if user is None or not password_ok:
            raise ApiError("Invalid username or password.", 401)

        start_session(user)
        return json_ok("Logged in successfully.", user=serialize_user(user), csrf_token=session["csrf_token"])

    @app.get("/api/auth/me")
    def me():
        user = current_user()
        if user is None:
            raise ApiError("Please log in to continue.", 401)
        return jsonify({"success": True, "user": serialize_user(user)})

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return json_ok("Logged out.", csrf_token=get_csrf_token())

    # ----- Opportunities ---------------------------------------------------
    @app.post("/api/opportunities")
    @login_required
    def create_opportunity():
        fields = validate_opportunity_fields(get_json_body())
        now = utcnow()
        doc = {
            **fields,
            "author_id": g.user["_id"],            # taken from the session, never from the browser
            "author_username": g.user["username"],
            "created_at": now,
            "expires_at": now + timedelta(days=current_app.config["OPPORTUNITY_LIFETIME_DAYS"]),
            "status": "Active",
        }
        result = get_db()["opportunities"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return json_ok("Opportunity created successfully", 201, opportunity=serialize_opportunity(doc, now))

    @app.get("/api/opportunities")
    def list_opportunities():
        db = get_db()
        now = utcnow()
        refresh_expired_statuses(db, now)

        clauses = []
        search = (request.args.get("search") or "").strip()[:MAX_SEARCH]
        if search:
            pattern = {"$regex": re.escape(search), "$options": "i"}
            clauses.append({"$or": [{f: pattern} for f in
                                    ("title", "description", "category", "author_username")]})

        category = request.args.get("category")
        if category and category != "All":
            if category not in CATEGORIES:
                raise ApiError("Unknown category.", 400)
            clauses.append({"category": category})

        status = (request.args.get("status") or "").strip().lower()
        if status in ("active",):
            clauses.append({"expires_at": {"$gt": now}})
        elif status in ("expired",):
            clauses.append({"expires_at": {"$lte": now}})
        elif status not in ("", "all"):
            raise ApiError("Status must be Active or Expired.", 400)

        sort_name = request.args.get("sort", "newest")
        sorts = {
            "newest": [("created_at", DESCENDING), ("_id", DESCENDING)],
            "oldest": [("created_at", ASCENDING), ("_id", ASCENDING)],
            "expiring": [("expires_at", ASCENDING), ("_id", ASCENDING)],
        }
        if sort_name not in sorts:
            raise ApiError("Sort must be newest, oldest or expiring.", 400)

        page = int_arg("page", 1, 1, 100000)
        limit = int_arg("limit", 50, 1, 100)

        query = {"$and": clauses} if clauses else {}
        collection = db["opportunities"]
        total = collection.count_documents(query)
        docs = collection.find(query).sort(sorts[sort_name]).skip((page - 1) * limit).limit(limit)

        return jsonify({
            "success": True,
            "opportunities": [serialize_opportunity(d, now) for d in docs],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": max(1, -(-total // limit)),
        })

    def load_opportunity_or_404(opp_id):
        oid = parse_object_id(opp_id, "opportunity ID")
        doc = get_db()["opportunities"].find_one({"_id": oid})
        if doc is None:
            raise ApiError("Opportunity not found.", 404)
        return doc

    @app.get("/api/opportunities/<opp_id>")
    def get_opportunity(opp_id):
        now = utcnow()
        refresh_expired_statuses(get_db(), now)
        doc = load_opportunity_or_404(opp_id)
        return jsonify({"success": True, "opportunity": serialize_opportunity(doc, now)})

    @app.put("/api/opportunities/<opp_id>")
    @login_required
    def update_opportunity(opp_id):
        doc = load_opportunity_or_404(opp_id)
        if doc["author_id"] != g.user["_id"]:
            raise ApiError("You can only edit your own opportunities.", 403)
        fields = validate_opportunity_fields(get_json_body(), partial=True)
        fields["updated_at"] = utcnow()
        get_db()["opportunities"].update_one({"_id": doc["_id"]}, {"$set": fields})
        doc.update(fields)
        return json_ok("Opportunity updated successfully", opportunity=serialize_opportunity(doc, utcnow()))

    @app.delete("/api/opportunities/<opp_id>")
    @login_required
    def delete_opportunity(opp_id):
        doc = load_opportunity_or_404(opp_id)
        if doc["author_id"] != g.user["_id"]:
            raise ApiError("You can only delete your own opportunities.", 403)
        get_db()["opportunities"].delete_one({"_id": doc["_id"]})
        return json_ok("Opportunity deleted.")


app = None
if __name__ == "__main__":
    import os

    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
