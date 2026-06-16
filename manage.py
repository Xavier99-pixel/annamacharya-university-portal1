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


def deactivate_code(args: argparse.Namespace) -> None:
    init_db()
    code = args.code.strip().upper()
    with connect_db() as db:
        cursor = db.execute("UPDATE faculty_codes SET active = 0 WHERE code = ?", (code,))
    if cursor.rowcount:
        print(f"Faculty code deactivated: {code}")
    else:
        print(f"Faculty code not found: {code}")


def list_users(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT id, role, name, roll_number, faculty_code, course, created_at
            FROM users
            ORDER BY id
            """
        ).fetchall()
    if not rows:
        print("No registered users yet.")
        return
    for row in rows:
        login_id = row["roll_number"] or row["faculty_code"]
        print(f"{row['id']} | {row['role']} | {row['name']} | {login_id} | {row['course']}")


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

    add = sub.add_parser("add-code", help="Create or reactivate a faculty code.")
    add.add_argument("code", help="Example: AU-CSE-2026")
    add.add_argument("--label", default="University faculty code", help="Small note for this code.")
    add.set_defaults(func=add_code)

    deactivate = sub.add_parser("deactivate-code", help="Disable a faculty code.")
    deactivate.add_argument("code")
    deactivate.set_defaults(func=deactivate_code)

    users = sub.add_parser("list-users", help="Show registered users.")
    users.set_defaults(func=list_users)

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
    except sqlite3.Error as exc:
        parser.exit(1, f"Database error: {exc}\n")


if __name__ == "__main__":
    main()
