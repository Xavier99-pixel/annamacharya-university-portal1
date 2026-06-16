from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DB_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "annamacharya_portal.sqlite3"))
SESSION_TTL_DAYS = 7
DEFAULT_FACULTY_CODES = ("AU-FAC-2026", "AU-STAFF-1001", "AITS-FAC-7788")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db() -> None:
    with connect_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('student', 'staff')),
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                course TEXT,
                year TEXT,
                semester TEXT,
                roll_number TEXT,
                faculty_code TEXT,
                profile_photo TEXT,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(role, roll_number),
                UNIQUE(role, faculty_code)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS faculty_codes (
                code TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )
        for code in DEFAULT_FACULTY_CODES:
            db.execute(
                """
                INSERT OR IGNORE INTO faculty_codes (code, label, active, created_at)
                VALUES (?, ?, 1, ?)
                """,
                (code, "Demo university faculty code", utc_now().isoformat()),
            )


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        260_000,
    )
    return salt, base64.b64encode(digest).decode("ascii")


def verify_password(password: str, salt: str, expected: str) -> bool:
    _, candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, expected)


def public_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "name": row["name"],
        "gender": row["gender"],
        "course": row["course"],
        "year": row["year"],
        "semester": row["semester"],
        "roll_number": row["roll_number"],
        "faculty_code": row["faculty_code"],
        "profile_photo": row["profile_photo"],
        "created_at": row["created_at"],
    }


def get_session_user(headers) -> dict | None:
    cookie = SimpleCookie(headers.get("Cookie", ""))
    morsel = cookie.get("au_session")
    if not morsel:
        return None

    token = morsel.value
    with connect_db() as db:
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (utc_now().isoformat(),))
        row = db.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ? AND sessions.expires_at > ?
            """,
            (token, utc_now().isoformat()),
        ).fetchone()
    return public_user(row) if row else None


class PortalHandler(SimpleHTTPRequestHandler):
    server_version = "AnnamacharyaPortal/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/me":
            user = get_session_user(self.headers)
            self.send_json({"authenticated": bool(user), "user": user})
            return
        if parsed.path == "/api/faculty-codes":
            with connect_db() as db:
                rows = db.execute(
                    "SELECT code, label FROM faculty_codes WHERE active = 1 ORDER BY code"
                ).fetchall()
            self.send_json({"codes": [dict(row) for row in rows]})
            return
        if parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/register":
                self.register()
            elif parsed.path == "/api/login":
                self.login()
            elif parsed.path == "/api/logout":
                self.logout()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except sqlite3.IntegrityError:
            self.send_json(
                {"ok": False, "message": "An account already exists for this role and ID."},
                HTTPStatus.CONFLICT,
            )

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Missing request body.")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload.") from exc

    def register(self) -> None:
        data = self.read_json()
        role = clean(data.get("role")).lower()
        name = clean(data.get("name"))
        gender = clean(data.get("gender"))
        password = str(data.get("password") or "")

        if role not in {"student", "staff"}:
            raise ValueError("Choose Student or Staff registration.")
        if not name or not gender:
            raise ValueError("Name and gender are required.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")

        course = year = semester = roll_number = faculty_code = None
        if role == "student":
            course = clean(data.get("course"))
            year = clean(data.get("year"))
            semester = clean(data.get("semester"))
            roll_number = clean(data.get("roll_number")).upper()
            required = [course, year, semester, roll_number]
            if not all(required):
                raise ValueError("Student course, year, semester and roll number are required.")
        else:
            faculty_code = clean(data.get("faculty_code")).upper()
            course = clean(data.get("department")) or "Management Staff"
            with connect_db() as db:
                valid_code = db.execute(
                    "SELECT code FROM faculty_codes WHERE code = ? AND active = 1",
                    (faculty_code,),
                ).fetchone()
            if not valid_code:
                raise ValueError("Invalid university faculty code.")

        profile_photo = str(data.get("profile_photo") or "")
        if profile_photo and not profile_photo.startswith("data:image/"):
            raise ValueError("Profile photo must be an image.")
        if len(profile_photo) > 1_200_000:
            raise ValueError("Profile photo is too large. Use an image below about 800 KB.")

        salt, password_hash = hash_password(password)
        created_at = utc_now().isoformat()
        with connect_db() as db:
            cursor = db.execute(
                """
                INSERT INTO users (
                    role, name, gender, course, year, semester, roll_number, faculty_code,
                    profile_photo, password_salt, password_hash, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role,
                    name,
                    gender,
                    course,
                    year,
                    semester,
                    roll_number,
                    faculty_code,
                    profile_photo,
                    salt,
                    password_hash,
                    created_at,
                ),
            )
            user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            token, expires = create_session(db, user["id"])

        self.send_json(
            {"ok": True, "message": "Account created successfully.", "user": public_user(user)},
            cookie=session_cookie(token, expires),
        )

    def login(self) -> None:
        data = self.read_json()
        role = clean(data.get("role")).lower()
        identifier = clean(data.get("identifier")).upper()
        password = str(data.get("password") or "")

        if role not in {"student", "staff"}:
            raise ValueError("Choose a login role.")
        if not identifier or not password:
            raise ValueError("Enter your ID and password.")

        field = "roll_number" if role == "student" else "faculty_code"
        with connect_db() as db:
            user = db.execute(
                f"SELECT * FROM users WHERE role = ? AND {field} = ?",
                (role, identifier),
            ).fetchone()
            if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
                raise ValueError("Invalid credentials for the selected role.")
            token, expires = create_session(db, user["id"])

        self.send_json(
            {"ok": True, "message": "Login successful.", "user": public_user(user)},
            cookie=session_cookie(token, expires),
        )

    def logout(self) -> None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("au_session")
        if morsel:
            with connect_db() as db:
                db.execute("DELETE FROM sessions WHERE token = ?", (morsel.value,))
        self.send_json(
            {"ok": True},
            cookie="au_session=; Path=/; Max-Age=0; SameSite=Lax; HttpOnly",
        )

    def send_json(self, payload: dict, status: int = HTTPStatus.OK, cookie: str | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)


def clean(value) -> str:
    return str(value or "").strip()


def create_session(db: sqlite3.Connection, user_id: int) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    expires = now + timedelta(days=SESSION_TTL_DAYS)
    db.execute(
        "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, user_id, expires.isoformat(), now.isoformat()),
    )
    return token, expires


def session_cookie(token: str, expires: datetime) -> str:
    return (
        f"au_session={token}; Path=/; Expires={expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}; "
        "SameSite=Lax; HttpOnly"
    )


def main() -> None:
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), PortalHandler)
    print(f"Annamacharya University portal running at http://{host}:{port}")
    print(f"SQLite database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
