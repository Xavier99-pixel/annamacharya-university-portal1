# Annamacharya University Portal

Student, faculty, and HOD login hub with local Python, SQLite authentication, profile photos, role-based dashboards, database-managed verification codes, and academic record management.

## Run Locally

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
python3 app.py
```

Open `http://127.0.0.1:8000`.

## How SQLite Connects

The frontend calls backend API URLs such as `/api/register` and `/api/login`.

`app.py` receives those requests, opens `annamacharya_portal.sqlite3` with Python's built-in `sqlite3` module, then inserts or reads rows from these tables:

- `users`: student, faculty, and HOD accounts
- `sessions`: browser login sessions
- `faculty_codes`: allowed staff registration codes
- `hod_codes`: allowed HOD verification codes
- `academic_records`: student attendance, marks, CGPA, and performance
- `faculty_attendance`: faculty attendance and performance managed by HOD

You do not manually connect the frontend to SQLite. The browser talks to Python; Python talks to SQLite.

## Faculty Codes

Default demo codes are inserted automatically:

- `AU-FAC-2026`
- `AU-STAFF-1001`
- `AITS-FAC-7788`

Create a new faculty code:

```bash
python3 manage.py add-code AU-CSE-2026 --label "CSE faculty registration"
```

Show all faculty codes:

```bash
python3 manage.py list-codes
```

Create a new HOD code:

```bash
python3 manage.py add-hod-code AU-HOD-CSE-2026 --label "CSE HOD verification"
```

Show all HOD codes:

```bash
python3 manage.py list-hod-codes
```

Disable a faculty code:

```bash
python3 manage.py deactivate-code AU-CSE-2026
```

Show registered users:

```bash
python3 manage.py list-users
```

Show student academic records:

```bash
python3 manage.py list-records
```

Show database tables:

```bash
python3 manage.py tables
```

## Notes

The database is created automatically as `annamacharya_portal.sqlite3`. This local Python backend will not run on a plain Netlify static deploy; for Netlify you can deploy the frontend and later move the API into Netlify Functions or another backend service.
