from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
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
OTP_RESEND_SECONDS = 60
OTP_HOURLY_LIMIT = 5
RUNNING_ON_RENDER = any(
    os.environ.get(key)
    for key in ("RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL")
)
DEFAULT_SMS_PROVIDER = "textbelt" if RUNNING_ON_RENDER else "demo"
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", DEFAULT_SMS_PROVIDER).strip().lower()
SMS_COUNTRY_CODE = os.environ.get("SMS_COUNTRY_CODE", "+91").strip() or "+91"
SMS_DEMO_MODE = os.environ.get("SMS_DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
SMS_FAILURE_FALLBACK = os.environ.get("SMS_FAILURE_FALLBACK", "true").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_FACULTY_CODES = ("AU-FAC-2026", "AU-STAFF-1001", "AITS-FAC-7788")
DEFAULT_HOD_CODES = ("AU-HOD-CSE-2026", "AU-HOD-MBA-2026", "AU-HOD-ADMIN-2026")
LOCAL_ADMIN_KEY = "AU-ADMIN-2026"
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
                email TEXT,
                address TEXT,
                dob TEXT,
                blood_group TEXT,
                guardian_name TEXT,
                guardian_phone TEXT,
                admission_date TEXT,
                status TEXT DEFAULT 'active',
                designation TEXT,
                specialization TEXT,
                qualification TEXT,
                experience TEXT,
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

            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'info',
                target_role TEXT DEFAULT 'all',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )
        for column, definition in {
            "phone_number": "TEXT",
            "phone_verified": "INTEGER NOT NULL DEFAULT 0",
            "email": "TEXT",
            "address": "TEXT",
            "dob": "TEXT",
            "blood_group": "TEXT",
            "guardian_name": "TEXT",
            "guardian_phone": "TEXT",
            "admission_date": "TEXT",
            "status": "TEXT DEFAULT 'active'",
            "designation": "TEXT",
            "specialization": "TEXT",
            "qualification": "TEXT",
            "experience": "TEXT",
        }.items():
            ensure_column(db, "users", column, definition)
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
        "email": row["email"],
        "address": row["address"],
        "dob": row["dob"],
        "blood_group": row["blood_group"],
        "guardian_name": row["guardian_name"],
        "guardian_phone": row["guardian_phone"],
        "admission_date": row["admission_date"],
        "status": row["status"] or "active",
        "designation": row["designation"],
        "specialization": row["specialization"],
        "qualification": row["qualification"],
        "experience": row["experience"],
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
            if parsed.path == "/api/notices":
                self.notices()
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
            if parsed.path == "/api/admin/export/users.csv":
                self.admin_export_users_csv(parsed.query)
                return
            if parsed.path == "/api/admin/export/academic.csv":
                self.admin_export_academic_csv(parsed.query)
                return
            if parsed.path == "/api/admin/export/faculty.csv":
                self.admin_export_faculty_csv(parsed.query)
                return
            if parsed.path == "/api/admin/export/notices.csv":
                self.admin_export_notices_csv(parsed.query)
                return
            if parsed.path == "/api/admin/export/database.sqlite3":
                self.admin_export_database(parsed.query)
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
            elif parsed.path == "/api/admin/restore/database.sqlite3":
                self.admin_restore_database(parsed.query)
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

        email = clean(data.get("email"))
        address = clean(data.get("address"))
        dob = clean(data.get("dob"))
        blood_group = clean(data.get("blood_group")).upper()
        guardian_name = clean(data.get("guardian_name"))
        guardian_phone = clean_phone(data.get("guardian_phone"))
        designation = clean(data.get("designation"))
        specialization = clean(data.get("specialization"))
        qualification = clean(data.get("qualification"))
        experience = clean(data.get("experience"))
        status = "active"
        admission_date = utc_now().date().isoformat()
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
            phone_number = clean_phone(data.get("phone_number"))
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
                    hod_code, phone_number, phone_verified, email, address, dob, blood_group,
                    guardian_name, guardian_phone, admission_date, status, designation, specialization,
                    qualification, experience, profile_photo, password_salt, password_hash, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    email,
                    address,
                    dob,
                    blood_group,
                    guardian_name,
                    guardian_phone,
                    admission_date,
                    status,
                    designation,
                    specialization,
                    qualification,
                    experience,
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
            enforce_otp_rate_limit(db, phone_number, now)
            db.execute(
                """
                INSERT INTO otp_verifications (
                    phone_number, otp_code, purpose, verified, expires_at, created_at
                )
                VALUES (?, ?, 'student_registration', 0, ?, ?)
                """,
                (phone_number, otp_code, expires.isoformat(), now.isoformat()),
            )
            delivery = send_otp_sms(phone_number, otp_code)
        response = {
            "ok": True,
            "message": delivery["message"],
            "phone_number": phone_number,
            "to": delivery["masked_to"],
            "delivery_mode": delivery["mode"],
            "expires_in_minutes": OTP_TTL_MINUTES,
        }
        if delivery["mode"] in {"demo", "fallback"}:
            response["demo_otp"] = otp_code
        self.send_json(
            response
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

    def notices(self) -> None:
        user = require_user(self.headers, {"student", "faculty", "hod"})
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT id, title, message, type, target_role, created_at
                FROM notices
                WHERE active = 1
                  AND (target_role IN ('all', ?) OR target_role IS NULL OR target_role = '')
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 12
                """,
                (user["role"],),
            ).fetchall()
        self.send_json({"ok": True, "notices": [dict(row) for row in rows]})

    def students(self) -> None:
        user = require_user(self.headers, {"faculty", "hod"})
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT
                    users.id, users.name, users.gender, users.course, users.branch, users.year,
                    users.semester, users.roll_number, users.profile_photo, users.email,
                    users.phone_number, users.status, users.admission_date,
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
                    users.email, users.phone_number, users.designation, users.specialization,
                    users.qualification, users.experience, users.status,
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
                    phone_verified, email, status, course, branch, year, semester, created_at
                FROM users
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 250
                """
            ).fetchall()
            records = db.execute(
                """
                SELECT
                    users.roll_number, users.name, users.course, users.branch, users.year,
                    users.semester, users.status,
                    academic_records.attendance, academic_records.internal_marks,
                    academic_records.external_marks, academic_records.marks,
                    academic_records.cgpa, academic_records.performance,
                    academic_records.updated_at
                FROM users
                LEFT JOIN academic_records ON academic_records.student_id = users.id
                WHERE users.role = 'student'
                ORDER BY users.roll_number
                LIMIT 250
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
            metric_row = db.execute(
                """
                SELECT
                    SUM(CASE WHEN role = 'student' AND COALESCE(status, 'active') = 'active' THEN 1 ELSE 0 END) AS active_students,
                    SUM(CASE WHEN role = 'student' AND phone_verified = 1 THEN 1 ELSE 0 END) AS verified_students,
                    SUM(CASE WHEN date(created_at) = date('now') THEN 1 ELSE 0 END) AS today_registrations
                FROM users
                """
            ).fetchone()
            active_faculty_codes = db.execute(
                "SELECT COUNT(*) AS count FROM faculty_codes WHERE active = 1"
            ).fetchone()["count"]
            active_hod_codes = db.execute(
                "SELECT COUNT(*) AS count FROM hod_codes WHERE active = 1"
            ).fetchone()["count"]
            open_notices = db.execute(
                "SELECT COUNT(*) AS count FROM notices WHERE active = 1"
            ).fetchone()["count"]
            course_rows = db.execute(
                """
                SELECT COALESCE(course, 'Unassigned') AS course,
                       COALESCE(branch, 'General') AS branch,
                       COUNT(*) AS total
                FROM users
                WHERE role = 'student'
                GROUP BY course, branch
                ORDER BY total DESC, course, branch
                LIMIT 8
                """
            ).fetchall()
            notices = db.execute(
                """
                SELECT id, title, message, type, target_role, active, created_at
                FROM notices
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 25
                """
            ).fetchall()
        counts = {"student": 0, "faculty": 0, "hod": 0}
        for row in role_rows:
            counts[row["role"]] = row["total"]
        metrics = dict(metric_row) if metric_row else {}
        self.send_json(
            {
                "ok": True,
                "database_path": str(DB_PATH),
                "counts": counts,
                "metrics": {
                    "active_students": metrics.get("active_students") or 0,
                    "verified_students": metrics.get("verified_students") or 0,
                    "today_registrations": metrics.get("today_registrations") or 0,
                    "active_faculty_codes": active_faculty_codes,
                    "active_hod_codes": active_hod_codes,
                    "open_notices": open_notices,
                },
                "total_users": sum(counts.values()),
                "recent_users": [dict(row) for row in recent_users],
                "student_records": [dict(row) for row in records],
                "codes": [dict(row) for row in codes],
                "course_distribution": [dict(row) for row in course_rows],
                "notices": [dict(row) for row in notices],
                "note": "This shows the database used by the running website instance.",
            }
        )

    def admin_export_users_csv(self, query: str) -> None:
        verify_admin_query_key(query)
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT
                    id, role, name, gender, course, branch, year, semester, roll_number,
                    faculty_code, hod_code, phone_number, phone_verified, email, address,
                    dob, blood_group, guardian_name, guardian_phone, admission_date, status,
                    designation, specialization, qualification, experience, created_at
                FROM users
                ORDER BY datetime(created_at) DESC, id DESC
                """
            ).fetchall()
        self.send_csv_download(
            "annamacharya_live_users.csv",
            [
                "id", "role", "name", "gender", "course", "branch", "year", "semester",
                "roll_number", "faculty_code", "hod_code", "phone_number",
                "phone_verified", "email", "address", "dob", "blood_group", "guardian_name",
                "guardian_phone", "admission_date", "status", "designation", "specialization",
                "qualification", "experience", "created_at",
            ],
            rows,
        )

    def admin_export_academic_csv(self, query: str) -> None:
        verify_admin_query_key(query)
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT
                    users.id AS student_id, users.roll_number, users.name, users.course,
                    users.branch, users.year, users.semester,
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
                ORDER BY users.roll_number
                """
            ).fetchall()
        self.send_csv_download(
            "annamacharya_academic_records.csv",
            [
                "student_id", "roll_number", "name", "course", "branch", "year",
                "semester", "attendance", "internal_marks", "external_marks",
                "marks", "cgpa", "performance", "updated_at",
            ],
            rows,
        )

    def admin_export_faculty_csv(self, query: str) -> None:
        verify_admin_query_key(query)
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT
                    users.id, users.role, users.name, users.gender, users.course AS department,
                    users.faculty_code, users.hod_code, users.phone_number, users.email,
                    users.designation, users.specialization, users.qualification,
                    users.experience, users.status,
                    COALESCE(faculty_attendance.attendance, 0) AS attendance,
                    COALESCE(faculty_attendance.performance, 'Not updated') AS performance,
                    faculty_attendance.updated_at,
                    users.created_at
                FROM users
                LEFT JOIN faculty_attendance ON faculty_attendance.faculty_id = users.id
                WHERE users.role IN ('faculty', 'hod')
                ORDER BY users.role, users.course, users.name
                """
            ).fetchall()
        self.send_csv_download(
            "annamacharya_faculty_report.csv",
            [
                "id", "role", "name", "gender", "department", "faculty_code", "hod_code",
                "phone_number", "email", "designation", "specialization", "qualification",
                "experience", "status", "attendance", "performance", "updated_at", "created_at",
            ],
            rows,
        )

    def admin_export_notices_csv(self, query: str) -> None:
        verify_admin_query_key(query)
        with connect_db() as db:
            rows = db.execute(
                """
                SELECT id, title, message, type, target_role, active, created_at
                FROM notices
                ORDER BY datetime(created_at) DESC, id DESC
                """
            ).fetchall()
        self.send_csv_download(
            "annamacharya_notices_report.csv",
            ["id", "title", "message", "type", "target_role", "active", "created_at"],
            rows,
        )

    def admin_export_database(self, query: str) -> None:
        verify_admin_query_key(query)
        backup_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
                backup_path = Path(tmp.name)
            with connect_db() as source, sqlite3.connect(backup_path) as backup:
                source.backup(backup)
            self.send_file_download(
                backup_path.read_bytes(),
                "application/vnd.sqlite3",
                "annamacharya_live_database.sqlite3",
            )
        finally:
            if backup_path and backup_path.exists():
                backup_path.unlink()

    def admin_restore_database(self, query: str) -> None:
        verify_admin_query_key(query)
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Choose a SQLite backup file to restore.")
        if length > 25_000_000:
            raise ValueError("Backup file is too large for this demo restore limit.")

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        restore_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False, dir=str(DB_PATH.parent)) as tmp:
                restore_path = Path(tmp.name)
                tmp.write(self.rfile.read(length))

            validate_sqlite_backup(restore_path)
            os.replace(restore_path, DB_PATH)
            init_db()

            with connect_db() as db:
                total = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
                role_rows = db.execute(
                    "SELECT role, COUNT(*) AS total FROM users GROUP BY role ORDER BY role"
                ).fetchall()

            self.send_json(
                {
                    "ok": True,
                    "message": f"Database restored successfully. {total} users are now available.",
                    "total_users": total,
                    "counts": {row["role"]: row["total"] for row in role_rows},
                }
            )
        finally:
            if restore_path and restore_path.exists():
                restore_path.unlink()

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

        if action == "create_notice":
            title = clean(data.get("title"))
            message = clean(data.get("message"))
            notice_type = clean(data.get("type")).lower() or "info"
            target_role = clean(data.get("target_role")).lower() or "all"
            if not title or not message:
                raise ValueError("Notice title and message are required.")
            if notice_type not in {"info", "warning", "urgent", "event"}:
                raise ValueError("Choose a valid notice type.")
            if target_role not in {"all", "student", "faculty", "hod"}:
                raise ValueError("Choose a valid notice target.")
            with connect_db() as db:
                db.execute(
                    """
                    INSERT INTO notices (title, message, type, target_role, active, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (title, message, notice_type, target_role, utc_now().isoformat()),
                )
            self.send_json({"ok": True, "message": "Notice published successfully."})
            return

        if action == "deactivate_notice":
            notice_id = parse_positive_int(data.get("notice_id"), "Notice ID")
            with connect_db() as db:
                cursor = db.execute("UPDATE notices SET active = 0 WHERE id = ?", (notice_id,))
            if not cursor.rowcount:
                raise ValueError("Notice not found.")
            self.send_json({"ok": True, "message": f"Notice ID {notice_id} deactivated."})
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

    def send_csv_download(self, filename: str, fieldnames: list[str], rows: list[sqlite3.Row]) -> None:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fieldnames})
        self.send_file_download(buffer.getvalue().encode("utf-8"), "text/csv; charset=utf-8", filename)

    def send_file_download(self, body: bytes, content_type: str, filename: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def clean(value) -> str:
    return str(value or "").strip()


def clean_phone(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def valid_phone(phone_number: str) -> bool:
    return len(phone_number) == 10 and phone_number[0] in "6789"


def enforce_otp_rate_limit(db: sqlite3.Connection, phone_number: str, now: datetime) -> None:
    recent_cutoff = (now - timedelta(seconds=OTP_RESEND_SECONDS)).isoformat()
    recent = db.execute(
        """
        SELECT id
        FROM otp_verifications
        WHERE phone_number = ? AND created_at > ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (phone_number, recent_cutoff),
    ).fetchone()
    if recent:
        raise ValueError(f"Please wait {OTP_RESEND_SECONDS} seconds before requesting another OTP.")

    hourly_cutoff = (now - timedelta(hours=1)).isoformat()
    hourly_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM otp_verifications
        WHERE phone_number = ? AND created_at > ?
        """,
        (phone_number, hourly_cutoff),
    ).fetchone()["count"]
    if hourly_count >= OTP_HOURLY_LIMIT:
        raise ValueError("Too many OTP requests. Try again after one hour.")


def should_use_demo_sms() -> bool:
    if SMS_DEMO_MODE:
        return True
    return SMS_PROVIDER in {"", "demo"} and not RUNNING_ON_RENDER


def format_sms_phone(phone_number: str) -> str:
    country_code = SMS_COUNTRY_CODE if SMS_COUNTRY_CODE.startswith("+") else f"+{SMS_COUNTRY_CODE}"
    return f"{country_code}{phone_number}"


def mask_phone(phone_number: str) -> str:
    formatted = format_sms_phone(phone_number)
    return f"{formatted[:3]}******{formatted[-4:]}"


def otp_sms_body(otp_code: str) -> str:
    return (
        f"Your Annamacharya University portal OTP is {otp_code}. "
        f"It expires in {OTP_TTL_MINUTES} minutes. Do not share it."
    )


def send_otp_sms(phone_number: str, otp_code: str) -> dict:
    if should_use_demo_sms():
        return {
            "mode": "demo",
            "masked_to": mask_phone(phone_number),
            "message": "Demo OTP generated. Configure SMS_PROVIDER=textbelt for free real-SMS testing.",
        }

    message = otp_sms_body(otp_code)
    if SMS_PROVIDER == "textbelt":
        try:
            send_textbelt_sms(phone_number, message)
        except ValueError as exc:
            if SMS_FAILURE_FALLBACK:
                return fallback_otp_delivery(phone_number, str(exc))
            raise
    elif SMS_PROVIDER == "twilio":
        send_twilio_sms(phone_number, message)
    elif SMS_PROVIDER == "webhook":
        send_webhook_sms(phone_number, message, otp_code)
    elif SMS_PROVIDER in {"", "demo"}:
        raise ValueError(
            "Real SMS is not configured. Set SMS_PROVIDER=textbelt for free demo SMS, "
            "SMS_PROVIDER=twilio with Twilio credentials, "
            "or set SMS_DEMO_MODE=true only for testing."
        )
    else:
        raise ValueError(f"Unsupported SMS_PROVIDER: {SMS_PROVIDER}. Use textbelt, twilio or webhook.")

    return {
        "mode": SMS_PROVIDER,
        "masked_to": mask_phone(phone_number),
        "message": f"OTP sent by SMS to {mask_phone(phone_number)}.",
    }


def fallback_otp_delivery(phone_number: str, reason: str) -> dict:
    return {
        "mode": "fallback",
        "masked_to": mask_phone(phone_number),
        "message": (
            "Free SMS delivery is unavailable for this number, so evaluation OTP mode is active. "
            f"Reason: {reason}"
        ),
    }


def send_textbelt_sms(phone_number: str, message: str) -> None:
    key = os.environ.get("TEXTBELT_KEY", "textbelt").strip() or "textbelt"
    body = urllib.parse.urlencode(
        {
            "phone": format_sms_phone(phone_number),
            "message": message,
            "key": key,
        }
    ).encode("utf-8")
    request = urllib.request.Request("https://textbelt.com/text", data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")[:200]
        raise ValueError(f"Textbelt SMS failed: {details or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach Textbelt SMS service: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Textbelt returned an unreadable SMS response.") from exc

    if not payload.get("success"):
        error = payload.get("error") or "Textbelt did not send the SMS."
        quota = payload.get("quotaRemaining")
        suffix = f" Quota remaining: {quota}." if quota is not None else ""
        raise ValueError(f"Textbelt SMS failed: {error}.{suffix}")


def send_twilio_sms(phone_number: str, message: str) -> None:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
    if not account_sid or not auth_token or not from_number:
        raise ValueError("Twilio SMS is not configured. Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER.")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    body = urllib.parse.urlencode(
        {
            "To": format_sms_phone(phone_number),
            "From": from_number,
            "Body": message,
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    request.add_header("Authorization", f"Basic {credentials}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in {200, 201}:
                raise ValueError("Twilio did not accept the SMS request.")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")[:200]
        raise ValueError(f"Twilio SMS failed: {details or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach Twilio SMS service: {exc.reason}") from exc


def send_webhook_sms(phone_number: str, message: str, otp_code: str) -> None:
    webhook_url = os.environ.get("SMS_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise ValueError("SMS webhook is not configured. Add SMS_WEBHOOK_URL.")
    payload = json.dumps(
        {
            "phone_number": phone_number,
            "to": format_sms_phone(phone_number),
            "message": message,
            "otp": otp_code,
            "project": "Annamacharya University Portal",
        }
    ).encode("utf-8")
    request = urllib.request.Request(webhook_url, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    auth_header = os.environ.get("SMS_WEBHOOK_AUTH_HEADER", "").strip()
    auth_value = os.environ.get("SMS_WEBHOOK_AUTH_VALUE", "").strip()
    if auth_header and auth_value:
        request.add_header(auth_header, auth_value)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError("SMS webhook did not accept the request.")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")[:200]
        raise ValueError(f"SMS webhook failed: {details or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach SMS webhook: {exc.reason}") from exc


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


def verify_admin_query_key(query: str) -> None:
    params = parse_qs(query)
    key = (params.get("key") or [""])[0]
    verify_admin_key(key)


def validate_sqlite_backup(path: Path) -> None:
    required_tables = {
        "users",
        "academic_records",
        "faculty_attendance",
        "faculty_codes",
        "hod_codes",
        "otp_verifications",
        "sessions",
    }
    try:
        with sqlite3.connect(path) as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError("SQLite integrity check failed.")
            rows = db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ValueError("Uploaded file is not a valid SQLite database.") from exc

    tables = {row[0] for row in rows}
    missing = sorted(required_tables - tables)
    if missing:
        raise ValueError(f"Backup does not match this portal schema. Missing: {', '.join(missing)}.")


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
