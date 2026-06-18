# Annamacharya University Portal

Student, faculty, and HOD login hub with local Python, SQLite authentication, profile photos, role-based dashboards, database-managed verification codes, and academic record management.

Student registration includes phone number + OTP verification. In free demo mode, the backend generates an OTP and shows it on screen; connect an SMS provider later for real delivery.

## Run Locally

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
python3 app.py
```

Open `http://127.0.0.1:8000`.

## Main Documents

- `DEVELOPER_ADMIN_HANDBOOK.md`: your role as developer/admin, monitoring routine, database management, and review explanation
- `OPERATOR_MANUAL.md`: full operating procedure
- `DEPLOYMENT.md`: local and Render deployment procedure

## How SQLite Connects

The frontend calls backend API URLs such as `/api/register` and `/api/login`.

`app.py` receives those requests, opens `annamacharya_portal.sqlite3` with Python's built-in `sqlite3` module, then inserts or reads rows from these tables:

- `users`: student, faculty, and HOD accounts
- `sessions`: browser login sessions
- `faculty_codes`: allowed staff registration codes
- `hod_codes`: allowed HOD verification codes
- `academic_records`: student attendance, marks, CGPA, and performance
- `faculty_attendance`: faculty attendance and performance managed by HOD
- `otp_verifications`: phone OTP generation and verification for student registration

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

HOD registration uses only the HOD code. The HOD also logs in with that HOD code as the ID number.

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

Show total users and counts by role:

```bash
python3 manage.py stats
```

Show latest registered users:

```bash
python3 manage.py recent-users --limit 20
```

Show student academic records:

```bash
python3 manage.py list-records
```

Update one student's record by roll number:

```bash
python3 manage.py update-record 24AFAID153 --attendance 92 --internal 80 --external 88 --cgpa 8.4 --performance "Excellent classroom performance"
```

Show database tables:

```bash
python3 manage.py tables
```

## Notes

The database is created automatically as `annamacharya_portal.sqlite3`. Local DataGrip sees only your local database file. Free Render deployment uses a separate temporary SQLite file on the hosted server, so users registered on the Render URL will not automatically appear in your local DataGrip.

## Live Database Monitor

If you register users on the deployed Render website, open the hidden creator console to see the users in that running website database.

Admin console URL:

```text
https://your-render-url.onrender.com/admin
```

The normal public navigation does not show this page. Share it only with yourself or project evaluators who need creator access.

Local-only demo admin key:

```text
AU-ADMIN-2026
```

On Render, set a private environment variable. Without this, the deployed admin actions are blocked on Render-style hosting:

```text
ADMIN_KEY=your-private-key
```

Then use that private key in the Admin Monitor. Do not place the real key in HTML, screenshots, GitHub, or public documentation. DataGrip is still useful for your local Mac database, but the deployed website has its own database file.

### Admin Monitor Manipulations

Inside the website, open `/admin`, enter your admin key, then use:

- `Load Live Users`: refresh counts, recent users, and student records from the active website database
- `Delete Fake/Test User`: enter a user ID from the recent users table, then delete that account
- `Manage Faculty/HOD Codes`: create/reactivate or deactivate faculty and HOD registration codes
- `Update Student Record`: enter a student roll number and update attendance, internal marks, external marks, CGPA, and performance

Every manipulation requires the admin key. After each successful action, the monitor refreshes automatically so you can immediately see the database change.

Use DataGrip when:

- You are running the project locally on your Mac
- You opened `annamacharya_portal.sqlite3` from this project folder
- You want manual SQL inspection of your local data

Use Admin Monitor when:

- You are viewing the deployed Render website
- You want users who registered on the live website
- You want live code/user/record changes without downloading the hosted database

### Seeing Live Render Users In DataGrip

DataGrip can query only the database file or database server you open. It cannot automatically see users who registered on Render while you are connected to your Mac's local `annamacharya_portal.sqlite3` file.

To inspect live Render registrations in DataGrip:

1. Open the deployed admin URL: `https://your-render-url.onrender.com/admin`
2. Enter your private `ADMIN_KEY`
3. Click `Load Live Users`
4. Click `SQLite Backup` in `Live Data Export for DataGrip`
5. Open the downloaded `annamacharya_live_database.sqlite3` file in DataGrip
6. Run SQL commands against that downloaded live backup

For quick spreadsheet-style review, use `Users CSV` or `Academic CSV`. For full DBMS inspection with tables, joins, and SQL commands, use `SQLite Backup`. Keep SQLite backups private because they include the full database, including account/security tables.

### Restoring Students After A Free Render Redeploy

Opening a downloaded backup in DataGrip does not automatically restore the live website. DataGrip only shows your local copy. To bring the users back to the deployed website, upload the backup through the hidden admin console.

Recommended free-hosting routine:

1. Before redeploying, open `/admin`
2. Enter your `ADMIN_KEY`
3. Click `SQLite Backup` and save `annamacharya_live_database.sqlite3`
4. Redeploy the website
5. Open `/admin` again
6. Enter your `ADMIN_KEY`
7. Choose the saved `.sqlite3` file in `Restore SQLite Backup`
8. Click `Restore Live Database`
9. Click `Load Live Users` and confirm the students/faculty/HODs returned

Restore replaces the current live database with the uploaded backup. If new users registered after the backup was downloaded, export a fresh backup before restoring so you do not overwrite newer data.

Example SQL after opening the downloaded backup in DataGrip:

```sql
SELECT id, role, name, roll_number, faculty_code, phone_number, phone_verified, course, branch, year, semester, created_at
FROM users
ORDER BY id DESC;
```

```sql
SELECT role, COUNT(*) AS total
FROM users
GROUP BY role;
```
