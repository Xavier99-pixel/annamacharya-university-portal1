from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone

from app import connect_db, init_db


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_code(args: argparse.Namespace) -> None:
    init_db()
    code = args.code.strip().upper()
    label = args.label.strip()
    with connect_db() as db:
        db.execute(
            """
            INSERT INTO faculty_codes (code, label, active, created_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(code) DO UPDATE SET label = excluded.label, active = 1
            """,
            (code, label, utc_now()),
        )
    print(f"Faculty code active: {code}")


def add_hod_code(args: argparse.Namespace) -> None:
    init_db()
    code = args.code.strip().upper()
    label = args.label.strip()
    with connect_db() as db:
        db.execute(
            """
            INSERT INTO hod_codes (code, label, active, created_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(code) DO UPDATE SET label = excluded.label, active = 1
            """,
            (code, label, utc_now()),
        )
    print(f"HOD code active: {code}")


def list_codes(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        rows = db.execute(
            "SELECT code, label, active, created_at FROM faculty_codes ORDER BY code"
        ).fetchall()
    if not rows:
        print("No faculty codes found.")
        return
    for row in rows:
        status = "active" if row["active"] else "inactive"
        print(f"{row['code']} | {status} | {row['label']}")


def list_hod_codes(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        rows = db.execute(
            "SELECT code, label, active, created_at FROM hod_codes ORDER BY code"
        ).fetchall()
    if not rows:
        print("No HOD codes found.")
        return
    for row in rows:
        status = "active" if row["active"] else "inactive"
        print(f"{row['code']} | {status} | {row['label']}")


def deactivate_code(args: argparse.Namespace) -> None:
    init_db()
    code = args.code.strip().upper()
    with connect_db() as db:
        cursor = db.execute("UPDATE faculty_codes SET active = 0 WHERE code = ?", (code,))
    if cursor.rowcount:
        print(f"Faculty code deactivated: {code}")
    else:
        print(f"Faculty code not found: {code}")


def deactivate_hod_code(args: argparse.Namespace) -> None:
    init_db()
    code = args.code.strip().upper()
    with connect_db() as db:
        cursor = db.execute("UPDATE hod_codes SET active = 0 WHERE code = ?", (code,))
    if cursor.rowcount:
        print(f"HOD code deactivated: {code}")
    else:
        print(f"HOD code not found: {code}")


def list_users(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT id, role, name, roll_number, faculty_code, phone_number, phone_verified,
                   course, branch, year, semester, created_at
            FROM users
            ORDER BY id
            """
        ).fetchall()
    if not rows:
        print("No registered users yet.")
        return
    for row in rows:
        login_id = row["roll_number"] or row["faculty_code"]
        academic = " ".join(
            value for value in [row["course"], row["branch"], row["year"], row["semester"]] if value
        )
        phone = row["phone_number"] or "-"
        verified = "verified" if row["phone_verified"] else "not verified"
        print(f"{row['id']} | {row['role']} | {row['name']} | {login_id} | {phone} ({verified}) | {academic}")


def user_stats(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        total = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        rows = db.execute(
            """
            SELECT role, COUNT(*) AS count
            FROM users
            GROUP BY role
            ORDER BY role
            """
        ).fetchall()
    counts = {row["role"]: row["count"] for row in rows}
    print(f"total | {total}")
    for role in ["student", "faculty", "hod"]:
        print(f"{role} | {counts.get(role, 0)}")


def recent_users(args: argparse.Namespace) -> None:
    init_db()
    limit = max(1, min(args.limit, 100))
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT id, role, name, roll_number, faculty_code, phone_number,
                   phone_verified, course, branch, year, semester, created_at
            FROM users
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    if not rows:
        print("No registered users yet.")
        return
    for row in rows:
        login_id = row["roll_number"] or row["faculty_code"]
        academic = " ".join(
            value for value in [row["course"], row["branch"], row["year"], row["semester"]] if value
        )
        phone = row["phone_number"] or "-"
        verified = "verified" if row["phone_verified"] else "not verified"
        print(
            f"{row['id']} | {row['created_at']} | {row['role']} | {row['name']} | "
            f"{login_id} | {phone} ({verified}) | {academic}"
        )


def list_records(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT
                users.roll_number, users.name, users.course, users.branch, users.year,
                users.semester, academic_records.attendance, academic_records.internal_marks,
                academic_records.external_marks, academic_records.marks, academic_records.cgpa,
                academic_records.performance, academic_records.updated_at
            FROM users
            LEFT JOIN academic_records ON academic_records.student_id = users.id
            WHERE users.role = 'student'
            ORDER BY users.roll_number
            """
        ).fetchall()
    if not rows:
        print("No student records found.")
        return
    for row in rows:
        academic = " ".join(
            value for value in [row["course"], row["branch"], row["year"], row["semester"]] if value
        )
        print(
            f"{row['roll_number']} | {row['name']} | {academic} | attendance={row['attendance'] or 0} "
            f"internal={row['internal_marks'] or 0} external={row['external_marks'] or 0} "
            f"total={row['marks'] or 0} cgpa={row['cgpa'] or 0} | {row['performance'] or 'Not updated'}"
        )


def bounded_score(value: float, minimum: float, maximum: float, label: str) -> float:
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}.")
    return round(value, 2)


def update_record(args: argparse.Namespace) -> None:
    init_db()
    roll_number = args.roll_number.strip().upper()
    attendance = bounded_score(args.attendance, 0, 100, "Attendance")
    internal_marks = bounded_score(args.internal, 0, 100, "Internal marks")
    external_marks = bounded_score(args.external, 0, 100, "External marks")
    cgpa = bounded_score(args.cgpa, 0, 10, "CGPA")
    marks = round((internal_marks + external_marks) / 2, 2)
    performance = args.performance.strip() or "Updated by admin"
    now = utc_now()

    with connect_db() as db:
        student = db.execute(
            "SELECT id, name FROM users WHERE role = 'student' AND roll_number = ?",
            (roll_number,),
        ).fetchone()
        if not student:
            print(f"No student found with roll number: {roll_number}")
            return
        db.execute(
            """
            INSERT INTO academic_records
                (student_id, attendance, internal_marks, external_marks, marks, cgpa, performance, updated_at)
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
            (student["id"], attendance, internal_marks, external_marks, marks, cgpa, performance, now),
        )
    print(f"Updated academic record for {student['name']} ({roll_number}).")


def delete_user(args: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        db.execute("DELETE FROM sessions WHERE user_id = ?", (args.user_id,))
        cursor = db.execute("DELETE FROM users WHERE id = ?", (args.user_id,))
    if cursor.rowcount:
        print(f"Deleted user id: {args.user_id}")
    else:
        print(f"User id not found: {args.user_id}")


def show_tables(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        rows = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
    print("Tables:")
    for row in rows:
        print(f"- {row['name']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Annamacharya University portal database.")
    sub = parser.add_subparsers(required=True)

    init = sub.add_parser("init-db", help="Create database tables.")
    init.set_defaults(func=lambda _: (init_db(), print("Database ready.")))

    codes = sub.add_parser("list-codes", help="Show faculty codes.")
    codes.set_defaults(func=list_codes)

    hod_codes = sub.add_parser("list-hod-codes", help="Show HOD verification codes.")
    hod_codes.set_defaults(func=list_hod_codes)

    add = sub.add_parser("add-code", help="Create or reactivate a faculty code.")
    add.add_argument("code", help="Example: AU-CSE-2026")
    add.add_argument("--label", default="University faculty code", help="Small note for this code.")
    add.set_defaults(func=add_code)

    add_hod = sub.add_parser("add-hod-code", help="Create or reactivate a HOD code.")
    add_hod.add_argument("code", help="Example: AU-HOD-CSE-2026")
    add_hod.add_argument("--label", default="University HOD code", help="Small note for this code.")
    add_hod.set_defaults(func=add_hod_code)

    deactivate = sub.add_parser("deactivate-code", help="Disable a faculty code.")
    deactivate.add_argument("code")
    deactivate.set_defaults(func=deactivate_code)

    deactivate_hod = sub.add_parser("deactivate-hod-code", help="Disable a HOD code.")
    deactivate_hod.add_argument("code")
    deactivate_hod.set_defaults(func=deactivate_hod_code)

    users = sub.add_parser("list-users", help="Show registered users.")
    users.set_defaults(func=list_users)

    stats = sub.add_parser("stats", help="Show total users and counts by role.")
    stats.set_defaults(func=user_stats)

    recent = sub.add_parser("recent-users", help="Show latest registered users.")
    recent.add_argument("--limit", type=int, default=10, help="How many latest users to show. Maximum 100.")
    recent.set_defaults(func=recent_users)

    records = sub.add_parser("list-records", help="Show student academic records.")
    records.set_defaults(func=list_records)

    update = sub.add_parser("update-record", help="Update a student's academic record by roll number.")
    update.add_argument("roll_number")
    update.add_argument("--attendance", type=float, required=True)
    update.add_argument("--internal", type=float, required=True)
    update.add_argument("--external", type=float, required=True)
    update.add_argument("--cgpa", type=float, required=True)
    update.add_argument("--performance", default="Good")
    update.set_defaults(func=update_record)

    delete = sub.add_parser("delete-user", help="Delete a registered user by id.")
    delete.add_argument("user_id", type=int)
    delete.set_defaults(func=delete_user)

    tables = sub.add_parser("tables", help="Show database tables.")
    tables.set_defaults(func=show_tables)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        parser.exit(1, f"Input error: {exc}\n")
    except sqlite3.Error as exc:
        parser.exit(1, f"Database error: {exc}\n")


if __name__ == "__main__":
    main()
