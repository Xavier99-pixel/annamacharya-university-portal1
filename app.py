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
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DB_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "annamacharya_portal.sqlite3"))
SESSION_TTL_DAYS = 7
OTP_TTL_MINUTES = 10
DEFAULT_FACULTY_CODES = ("AU-FAC-2026", "AU-STAFF-1001", "AITS-FAC-7788")
DEFAULT_HOD_CODES = ("AU-HOD-CSE-2026", "AU-HOD-MBA-2026", "AU-HOD-ADMIN-2026")
LOCAL_ADMIN_KEY = "AU-ADMIN-2026"
RUNNING_ON_RENDER = any(
    os.environ.get(key)
    for key in ("RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL")
)
ADMIN_KEY = os.environ.get("ADMIN_KEY") or ("" if RUNNING_ON_RENDER else LOCAL_ADMIN_KEY)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db() -> None:
    with connect_db() as db:
        migrate_users_table(db)
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('student', 'faculty', 'hod')),
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                course TEXT,
                branch TEXT,
                year TEXT,
                semester TEXT,
                roll_number TEXT,
                faculty_code TEXT,
                hod_code TEXT,
                phone_number TEXT,
                phone_verified INTEGER NOT NULL DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS hod_codes (
                code TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS academic_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                attendance REAL DEFAULT 0,
                internal_marks REAL DEFAULT 0,
                external_marks REAL DEFAULT 0,
                marks REAL DEFAULT 0,
                cgpa REAL DEFAULT 0,
                performance TEXT DEFAULT 'Not updated',
                updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                updated_at TEXT,
                UNIQUE(student_id)
            );

            CREATE TABLE IF NOT EXISTS faculty_attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                attendance REAL DEFAULT 0,
                performance TEXT DEFAULT 'Not updated',
                updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                updated_at TEXT,
                UNIQUE(faculty_id)
            );

            CREATE TABLE IF NOT EXISTS otp_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                purpose TEXT NOT NULL DEFAULT 'student_registration',
                verified INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        ensure_column(db, "users", "phone_number", "TEXT")
        ensure_column(db, "users", "phone_verified", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(db, "academic_records", "internal_marks", "REAL DEFAULT 0")
        ensure_column(db, "academic_records", "external_marks", "REAL DEFAULT 0")
        for code in DEFAULT_FACULTY_CODES:
            db.execute(
                """
                INSERT OR IGNORE INTO faculty_codes (code, label, active, created_at)
                VALUES (?, ?, 1, ?)
                """,
                (code, "Demo university faculty code", utc_now().isoformat()),
            )
        for code in DEFAULT_HOD_CODES:
            db.execute(
                """
                INSERT OR IGNORE INTO hod_codes (code, label, active, created_at)
                VALUES (?, ?, 1, ?)
                """,
                (code, "Demo HOD verification code", utc_now().isoformat()),
            )


def migrate_users_table(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    ).fetchone()
    if not row:
        return
    sql = row["sql"] or ""
    if "'faculty'" in sql and "branch TEXT" in sql and "hod_code TEXT" in sql:
        return

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('student', 'faculty', 'hod')),
            name TEXT NOT NULL,
            gender TEXT NOT NULL,
            course TEXT,
            branch TEXT,
            year TEXT,
            semester TEXT,
            roll_number TEXT,
            faculty_code TEXT,
            hod_code TEXT,
            phone_number TEXT,
            phone_verified INTEGER NOT NULL DEFAULT 0,
            profile_photo TEXT,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(role, roll_number),
            UNIQUE(role, faculty_code)
        );

        INSERT OR IGNORE INTO users_new (
            id, role, name, gender, course, branch, year, semester, roll_number,
            faculty_code, hod_code, phone_number, phone_verified, profile_photo,
            password_salt, password_hash, created_at
        )
        SELECT
            id,
            CASE WHEN role = 'staff' THEN 'faculty' ELSE role END,
            name,
            gender,
            course,
            NULL,
            year,
            semester,
            roll_number,
            faculty_code,
            NULL,
            NULL,
            0,
            profile_photo,
            password_salt,
            password_hash,
            created_at
        FROM users;

        DROP TABLE users;
        ALTER TABLE users_new RENAME TO users;
        """
    )


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
        "branch": row["branch"],
        "year": row["year"],
        "semester": row["semester"],
        "roll_number": row["roll_number"],
        "faculty_code": row["faculty_code"],
        "hod_code": row["hod_code"],
        "phone_number": row["phone_number"],
        "phone_verified": bool(row["phone_verified"]),
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
        if not row:
            return None
        user = public_user(row)
        if user["role"] == "student":
            record = db.execute(
                """
                SELECT attendance, internal_marks, external_marks, marks, cgpa, performance, updated_at
                FROM academic_records
                WHERE student_id = ?
                """,
                (user["id"],),
            ).fetchone()
            user["academic_record"] = dict(record) if record else {
                "attendance": 0,
                "internal_marks": 0,
                "external_marks": 0,
                "marks": 0,
                "cgpa": 0,
                "performance": "Not updated",
                "updated_at": None,
            }
    return user


class PortalHandler(SimpleHTTPRequestHandler):
    server_version = "AnnamacharyaPortal/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/healthz":
                self.send_json({"ok": True})
                return
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
            if parsed.path == "/api/hod-codes":
                with connect_db() as db:
                    rows = db.execute(
                        "SELECT code, label FROM hod_codes WHERE active = 1 ORDER BY code"
                    ).fetchall()
                self.send_json({"codes": [dict(row) for row in rows]})
                return
            if parsed.path == "/api/admin/overview":
                self.admin_overview(parsed.query)
                return
            if parsed.path == "/api/students":
                self.students()
                return
            if parsed.path == "/api/faculty":
                self.faculty()
                return
            if parsed.path.startswith("/api/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if parsed.path in {"/", "/admin"}:
                self.path = "/index.html"
            return super().do_GET()
        except ValueError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.FORBIDDEN)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/register":
                self.register()
            elif parsed.path == "/api/request-otp":
                self.request_otp()
            elif parsed.path == "/api/verify-otp":
                self.verify_otp()
            elif parsed.path == "/api/login":
                self.login()
            elif parsed.path == "/api/logout":
                self.logout()
            elif parsed.path == "/api/student-record":
                self.update_student_record()
            elif parsed.path == "/api/faculty-attendance":
                self.update_faculty_attendance()
            elif parsed.path == "/api/admin/action":
                self.admin_action()
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

        if role == "staff":
            role = "hod" if bool(data.get("is_hod")) else "faculty"
        if role not in {"student", "faculty", "hod"}:
            raise ValueError("Choose Student, Faculty or HOD registration.")
        if not name or not gender:
            raise ValueError("Name and gender are required.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")

        course = branch = year = semester = roll_number = faculty_code = hod_code = None
        phone_number = clean_phone(data.get("phone_number"))
        phone_verified = 0
        if role == "student":
            course = clean(data.get("course"))
            branch = clean(data.get("branch"))
            year = clean(data.get("year"))
            semester = clean(data.get("semester"))
            roll_number = clean(data.get("roll_number")).upper()
            required = [course, branch, year, semester, roll_number, phone_number]
            if not all(required):
                raise ValueError("Student course, branch, year, semester, roll number and phone number are required.")
            if not is_phone_verified(phone_number):
                raise ValueError("Phone number must be verified with OTP before student registration.")
            phone_verified = 1
        else:
            course = clean(data.get("department")) or "Management Staff"
            if role == "hod":
                hod_code = clean(data.get("hod_code")).upper()
                if not hod_code:
                    raise ValueError("HOD verification code is required.")
                faculty_code = hod_code
                validate_staff_codes(role, None, hod_code)
            else:
                faculty_code = clean(data.get("faculty_code")).upper()
                if not faculty_code:
                    raise ValueError("Faculty code is required.")
                validate_staff_codes(role, faculty_code, None)

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
                    role, name, gender, course, branch, year, semester, roll_number, faculty_code,
                    hod_code, phone_number, phone_verified, profile_photo, password_salt, password_hash, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role,
                    name,
                    gender,
                    course,
                    branch,
                    year,
                    semester,
                    roll_number,
                    faculty_code,
                    hod_code,
                    phone_number,
                    phone_verified,
                    profile_photo,
                    salt,
                    password_hash,
                    created_at,
                ),
            )
            user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            if role == "student":
                db.execute(
                    """
                    INSERT OR IGNORE INTO academic_records (student_id, updated_at)
                    VALUES (?, ?)
                    """,
                    (user["id"], created_at),
                )
            if role in {"faculty", "hod"}:
                db.execute(
                    """
                    INSERT OR IGNORE INTO faculty_attendance (faculty_id, updated_at)
                    VALUES (?, ?)
                    """,
                    (user["id"], created_at),
                )
            token, expires = create_session(db, user["id"])

        self.send_json(
            {"ok": True, "message": "Account created successfully.", "user": public_user(user)},
            cookie=session_cookie(token, expires),
        )

    def request_otp(self) -> None:
        data = self.read_json()
        phone_number = clean_phone(data.get("phone_number"))
        if not valid_phone(phone_number):
            raise ValueError("Enter a valid 10 digit phone number.")
        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        now = utc_now()
        expires = now + timedelta(minutes=OTP_TTL_MINUTES)
        with connect_db() as db:
            db.execute(
                """
                INSERT INTO otp_verifications (
                    phone_number, otp_code, purpose, verified, expires_at, created_at
                )
                VALUES (?, ?, 'student_registration', 0, ?, ?)
                """,
                (phone_number, otp_code, expires.isoformat(), now.isoformat()),
            )
        self.send_json(
            {
                "ok": True,
                "message": "OTP generated. Demo mode shows OTP on screen; connect SMS provider for real sending.",
                "phone_number": phone_number,
                "demo_otp": otp_code,
                "expires_in_minutes": OTP_TTL_MINUTES,
            }
        )

    def verify_otp(self) -> None:
        data = self.read_json()
        phone_number = clean_phone(data.get("phone_number"))
        otp_code = clean(data.get("otp_code"))
        if not valid_phone(phone_number):
            raise ValueError("Enter a valid 10 digit phone number.")
        if not otp_code:
            raise ValueError("Enter OTP.")
        with connect_db() as db:
            row = db.execute(
                """
                SELECT id, otp_code
                FROM otp_verifications
                WHERE phone_number = ?
                  AND purpose = 'student_registration'
                  AND verified = 0
                  AND expires_at > ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (phone_number, utc_now().isoformat()),
            ).fetchone()
            if not row or not hmac.compare_digest(row["otp_code"], otp_code):
                raise ValueError("Invalid or expired OTP.")
            db.execute("UPDATE otp_verifications SET verified = 1 WHERE id = ?", (row["id"],))
        self.send_json({"ok": True, "message": "Phone number verified successfully."})

    def login(self) -> None:
        data = self.read_json()
        role = clean(data.get("role")).lower()
        identifier = clean(data.get("identifier")).upper()
        password = str(data.get("password") or "")

        if role == "staff":
            role = "faculty"
        if role not in {"student", "faculty", "hod"}:
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

    def students(self) -> None:
        user = require_user(self.headers, {"faculty", "hod"})
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT
                    users.id, users.name, users.gender, users.course, users.branch, users.year,
                    users.semester, users.roll_number, users.profile_photo,
                    COALESCE(academic_records.attendance, 0) AS attendance,
                    COALESCE(academic_records.internal_marks, 0) AS internal_marks,
                    COALESCE(academic_records.external_marks, 0) AS external_marks,
                    COALESCE(academic_records.marks, 0) AS marks,
                    COALESCE(academic_records.cgpa, 0) AS cgpa,
                    COALESCE(academic_records.performance, 'Not updated') AS performance,
                    academic_records.updated_at
                FROM users
                LEFT JOIN academic_records ON academic_records.student_id = users.id
                WHERE users.role = 'student'
                ORDER BY users.course, users.branch, users.year, users.semester, users.roll_number
                """
            ).fetchall()
        self.send_json({"ok": True, "viewer": user, "students": [dict(row) for row in rows]})

    def update_student_record(self) -> None:
        user = require_user(self.headers, {"faculty", "hod"})
        data = self.read_json()
        roll_number = clean(data.get("roll_number")).upper()
        if not roll_number:
            raise ValueError("Student roll number is required.")
        attendance = parse_score(data.get("attendance"), "Attendance", 0, 100)
        internal_marks = parse_score(data.get("internal_marks"), "Internal marks", 0, 100)
        external_marks = parse_score(data.get("external_marks"), "External marks", 0, 100)
        marks = round((internal_marks + external_marks) / 2, 2)
        cgpa = parse_score(data.get("cgpa"), "CGPA", 0, 10)
        performance = clean(data.get("performance")) or "Not updated"

        with connect_db() as db:
            student = db.execute(
                "SELECT id FROM users WHERE role = 'student' AND roll_number = ?",
                (roll_number,),
            ).fetchone()
            if not student:
                raise ValueError("No student found for that roll number.")
            db.execute(
                """
                INSERT INTO academic_records (
                    student_id, attendance, internal_marks, external_marks, marks, cgpa, performance, updated_by, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    attendance = excluded.attendance,
                    internal_marks = excluded.internal_marks,
                    external_marks = excluded.external_marks,
                    marks = excluded.marks,
                    cgpa = excluded.cgpa,
                    performance = excluded.performance,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (
                    student["id"],
                    attendance,
                    internal_marks,
                    external_marks,
                    marks,
                    cgpa,
                    performance,
                    user["id"],
                    utc_now().isoformat(),
                ),
            )
        self.send_json({"ok": True, "message": "Student academic record updated."})

    def faculty(self) -> None:
        user = require_user(self.headers, {"hod"})
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT
                    users.id, users.name, users.gender, users.course, users.faculty_code,
                    users.profile_photo, users.created_at,
                    COALESCE(faculty_attendance.attendance, 0) AS attendance,
                    COALESCE(faculty_attendance.performance, 'Not updated') AS performance,
                    faculty_attendance.updated_at
                FROM users
                LEFT JOIN faculty_attendance ON faculty_attendance.faculty_id = users.id
                WHERE users.role IN ('faculty', 'hod')
                ORDER BY users.course, users.name
                """
            ).fetchall()
        self.send_json({"ok": True, "viewer": user, "faculty": [dict(row) for row in rows]})

    def update_faculty_attendance(self) -> None:
        user = require_user(self.headers, {"hod"})
        data = self.read_json()
        faculty_code = clean(data.get("faculty_code")).upper()
        if not faculty_code:
            raise ValueError("Faculty code is required.")
        attendance = parse_score(data.get("attendance"), "Attendance", 0, 100)
        performance = clean(data.get("performance")) or "Not updated"
        with connect_db() as db:
            faculty = db.execute(
                "SELECT id FROM users WHERE role IN ('faculty', 'hod') AND faculty_code = ?",
                (faculty_code,),
            ).fetchone()
            if not faculty:
                raise ValueError("No faculty member found for that faculty code.")
            db.execute(
                """
                INSERT INTO faculty_attendance (
                    faculty_id, attendance, performance, updated_by, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(faculty_id) DO UPDATE SET
                    attendance = excluded.attendance,
                    performance = excluded.performance,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (faculty["id"], attendance, performance, user["id"], utc_now().isoformat()),
            )
        self.send_json({"ok": True, "message": "Faculty attendance updated."})

    def admin_overview(self, query: str) -> None:
        params = parse_qs(query)
        key = (params.get("key") or [""])[0]
        verify_admin_key(key)
        with connect_db() as db:
            role_rows = db.execute(
                """
                SELECT role, COUNT(*) AS total
                FROM users
                GROUP BY role
                ORDER BY role
                """
            ).fetchall()
            recent_users = db.execute(
                """
                SELECT
                    id, role, name, roll_number, faculty_code, hod_code, phone_number,
                    phone_verified, course, branch, year, semester, created_at
                FROM users
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 50
                """
            ).fetchall()
            records = db.execute(
                """
                SELECT
                    users.roll_number, users.name, users.course, users.branch,
                    academic_records.attendance, academic_records.internal_marks,
                    academic_records.external_marks, academic_records.marks,
                    academic_records.cgpa, academic_records.performance,
                    academic_records.updated_at
                FROM users
                LEFT JOIN academic_records ON academic_records.student_id = users.id
                WHERE users.role = 'student'
                ORDER BY users.roll_number
                LIMIT 50
                """
            ).fetchall()
            codes = db.execute(
                """
                SELECT 'faculty' AS code_type, code, label, active, created_at
                FROM faculty_codes
                UNION ALL
                SELECT 'hod' AS code_type, code, label, active, created_at
                FROM hod_codes
                ORDER BY code_type, code
                """
            ).fetchall()
        counts = {"student": 0, "faculty": 0, "hod": 0}
        for row in role_rows:
            counts[row["role"]] = row["total"]
        self.send_json(
            {
                "ok": True,
                "database_path": str(DB_PATH),
                "counts": counts,
                "total_users": sum(counts.values()),
                "recent_users": [dict(row) for row in recent_users],
                "student_records": [dict(row) for row in records],
                "codes": [dict(row) for row in codes],
                "note": "This shows the database used by the running website instance.",
            }
        )

    def admin_action(self) -> None:
        data = self.read_json()
        verify_admin_key(data.get("admin_key"))
        action = clean(data.get("action"))

        if action == "delete_user":
            user_id = parse_positive_int(data.get("user_id"), "User ID")
            with connect_db() as db:
                db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                db.execute("DELETE FROM academic_records WHERE student_id = ?", (user_id,))
                db.execute("DELETE FROM faculty_attendance WHERE faculty_id = ?", (user_id,))
                cursor = db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if not cursor.rowcount:
                raise ValueError("No user found with that ID.")
            self.send_json({"ok": True, "message": f"Deleted user ID {user_id}."})
            return

        if action in {"create_code", "deactivate_code"}:
            code_type = clean(data.get("code_type")).lower()
            code = clean(data.get("code")).upper()
            label = clean(data.get("label")) or "Admin managed code"
            if code_type not in {"faculty", "hod"}:
                raise ValueError("Choose faculty or HOD code type.")
            if not code:
                raise ValueError("Code is required.")
            table = "faculty_codes" if code_type == "faculty" else "hod_codes"
            with connect_db() as db:
                if action == "create_code":
                    db.execute(
                        f"""
                        INSERT INTO {table} (code, label, active, created_at)
                        VALUES (?, ?, 1, ?)
                        ON CONFLICT(code) DO UPDATE SET label = excluded.label, active = 1
                        """,
                        (code, label, utc_now().isoformat()),
                    )
                    message = f"{code_type.title()} code active: {code}."
                else:
                    cursor = db.execute(f"UPDATE {table} SET active = 0 WHERE code = ?", (code,))
                    if not cursor.rowcount:
                        raise ValueError("Code not found.")
                    message = f"{code_type.title()} code deactivated: {code}."
            self.send_json({"ok": True, "message": message})
            return

        if action == "update_student_record":
            roll_number = clean(data.get("roll_number")).upper()
            if not roll_number:
                raise ValueError("Student roll number is required.")
            attendance = parse_score(data.get("attendance"), "Attendance", 0, 100)
            internal_marks = parse_score(data.get("internal_marks"), "Internal marks", 0, 100)
            external_marks = parse_score(data.get("external_marks"), "External marks", 0, 100)
            marks = round((internal_marks + external_marks) / 2, 2)
            cgpa = parse_score(data.get("cgpa"), "CGPA", 0, 10)
            performance = clean(data.get("performance")) or "Not updated"
            with connect_db() as db:
                student = db.execute(
                    "SELECT id, name FROM users WHERE role = 'student' AND roll_number = ?",
                    (roll_number,),
                ).fetchone()
                if not student:
                    raise ValueError("No student found for that roll number.")
                db.execute(
                    """
                    INSERT INTO academic_records (
                        student_id, attendance, internal_marks, external_marks, marks, cgpa, performance, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id) DO UPDATE SET
                        attendance = excluded.attendance,
                        internal_marks = excluded.internal_marks,
                        external_marks = excluded.external_marks,
                        marks = excluded.marks,
                        cgpa = excluded.cgpa,
                        performance = excluded.performance,
                        updated_at = excluded.updated_at
                    """,
                    (
                        student["id"],
                        attendance,
                        internal_marks,
                        external_marks,
                        marks,
                        cgpa,
                        performance,
                        utc_now().isoformat(),
                    ),
                )
            self.send_json({"ok": True, "message": f"Updated record for {student['name']}."})
            return

        raise ValueError("Unknown admin action.")

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


def clean_phone(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def valid_phone(phone_number: str) -> bool:
    return len(phone_number) == 10 and phone_number[0] in "6789"


def is_phone_verified(phone_number: str) -> bool:
    with connect_db() as db:
        row = db.execute(
            """
            SELECT id
            FROM otp_verifications
            WHERE phone_number = ?
              AND purpose = 'student_registration'
              AND verified = 1
              AND expires_at > ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (phone_number, utc_now().isoformat()),
        ).fetchone()
    return bool(row)


def validate_staff_codes(role: str, faculty_code: str | None, hod_code: str | None) -> None:
    with connect_db() as db:
        if role == "hod":
            valid_hod_code = db.execute(
                "SELECT code FROM hod_codes WHERE code = ? AND active = 1",
                (hod_code,),
            ).fetchone()
            if not valid_hod_code:
                raise ValueError("Invalid HOD verification code.")
            return
        valid_code = db.execute(
            "SELECT code FROM faculty_codes WHERE code = ? AND active = 1",
            (faculty_code,),
        ).fetchone()
        if not valid_code:
            raise ValueError("Invalid university faculty code.")


def verify_admin_key(value) -> None:
    candidate = clean(value)
    if not ADMIN_KEY or not candidate or not hmac.compare_digest(candidate, ADMIN_KEY):
        raise ValueError("Valid admin key is required.")


def parse_positive_int(value, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if number <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return number


def parse_score(value, label: str, minimum: float, maximum: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if score < minimum or score > maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}.")
    return score


def require_user(headers, allowed_roles: set[str]) -> dict:
    user = get_session_user(headers)
    if not user:
        raise ValueError("Login is required.")
    if user["role"] not in allowed_roles:
        raise ValueError("You do not have permission to access this workspace.")
    return user


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
