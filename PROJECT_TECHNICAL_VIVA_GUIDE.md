# Annamacharya University Portal - Technical Viva And Database Guide

Prepared for: Student project review / HOD demonstration

Project folder:

```text
/Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
```

Main database file:

```text
/Users/tirumalarajavardhan/Downloads/annamacharya-university-portal/annamacharya_portal.sqlite3
```

## 1. Project Summary

The Annamacharya University Portal is a role-based academic web application. It supports three account types:

- Student
- Faculty
- HOD

Each role has a different login identity, dashboard, and permission boundary.

Students register with roll number, academic details, phone number, OTP verification, profile photo, and password. After login, students can see only their own profile and academic record.

Faculty register with a university-issued faculty code. After login, faculty can view registered students and update attendance, internal marks, external marks, CGPA, and performance by roll number.

HOD users register with a HOD code only. After login, HOD users can supervise faculty attendance/performance and also access student academic overview.

The project uses:

- HTML, CSS, JavaScript for frontend
- Python standard library HTTP server for backend
- SQLite for local database
- Cookie-based session token authentication
- PBKDF2-HMAC password hashing
- Role-based authorization checks in backend API routes

## 2. Important Correction: JWT Is Not Used Here

This project does not currently use JWT keys.

It uses a simpler and secure-for-demo mechanism:

```text
Login success -> backend creates random session token -> token stored in SQLite sessions table -> browser receives HttpOnly cookie named au_session -> every protected API request sends that cookie automatically -> backend checks token and role.
```

So if an examiner asks "where is the JWT key?", the correct answer is:

```text
This implementation does not use JWT. It uses server-side session tokens stored in SQLite and delivered through an HttpOnly cookie. This is a stateful authentication design.
```

JWT is a stateless token system. This portal is stateful.

## 3. Authentication Mechanism In This Project

Authentication means verifying who the user is.

In this portal, authentication happens through:

1. User submits login form.
2. Frontend sends ID number, selected role, and password to `/api/login`.
3. Backend checks the selected role.
4. Backend decides which database field to search:
   - Student: `roll_number`
   - Faculty: `faculty_code`
   - HOD: `faculty_code`, where the HOD code is stored as the HOD login ID
5. Backend compares password using PBKDF2-HMAC hash verification.
6. If correct, backend creates a random session token.
7. Backend stores the token in `sessions`.
8. Backend sends the token to browser as an HttpOnly cookie.

Main code mechanisms:

```text
login()              Handles login request
verify_password()    Verifies entered password
create_session()     Creates random session token
session_cookie()     Sends cookie to browser
get_session_user()   Reads cookie and identifies current user
require_user()       Checks whether logged-in user has allowed role
```

## 4. Authorization Mechanism: Role-Based Authentication

The better term is role-based authorization. Authentication proves identity. Authorization decides what the identity can access.

This portal has strict backend role checks.

Student permissions:

```text
Can access: own student dashboard
Cannot access: faculty dashboard, HOD dashboard, student list API, record update API
```

Faculty permissions:

```text
Can access: faculty dashboard, registered students, student record update API
Cannot access: HOD faculty-attendance API
```

HOD permissions:

```text
Can access: HOD dashboard, faculty list, faculty attendance update, student overview, student record update
```

Backend route protection:

```text
/api/students             require_user(..., {"faculty", "hod"})
/api/student-record       require_user(..., {"faculty", "hod"})
/api/faculty              require_user(..., {"hod"})
/api/faculty-attendance   require_user(..., {"hod"})
```

This means even if a student tries to open a protected API manually, backend blocks them.

## 5. Frontend To Backend Connection

The frontend does not connect directly to SQLite.

Correct flow:

```text
HTML form -> JavaScript event listener -> fetch() API call -> Python app.py route -> SQLite query -> JSON response -> JavaScript updates page
```

Example: student registration

```text
studentForm submit
-> static/app.js collects form values
-> fetch("/api/register", JSON data)
-> app.py register()
-> validates role and required fields
-> checks OTP verification
-> hashes password
-> inserts row into users
-> creates academic_records row
-> creates session token
-> sends JSON + cookie
-> frontend redirects to student dashboard
```

Example: faculty updating marks

```text
recordForm submit
-> static/app.js sends /api/student-record
-> app.py update_student_record()
-> require_user allows faculty or HOD only
-> backend finds student by roll number
-> updates academic_records
-> frontend reloads student table
```

## 6. Page And Dashboard Redirection Mechanism

This project is a single-page application style frontend.

All major screens exist inside `static/index.html` as sections:

```text
splash
roles
student-register
staff-register
login
student-dashboard
faculty-dashboard
hod-dashboard
```

JavaScript does not load a new HTML file for every page. Instead, it shows one section and hides the others.

Main function:

```text
showView(id)
```

How redirect works after login:

```text
handleAuthResult()
-> saves result.user in frontend state
-> renderWorkspace(result.user)
-> dashboardForRole(role)
-> showView("student-dashboard" / "faculty-dashboard" / "hod-dashboard")
```

Role to dashboard mapping:

```text
student -> student-dashboard
faculty -> faculty-dashboard
hod     -> hod-dashboard
```

Session restore:

```text
hydrate()
-> fetch("/api/me")
-> if session cookie is valid, backend returns current user
-> frontend opens correct dashboard automatically
```

## 7. Database Schema

Main tables:

```text
users
sessions
faculty_codes
hod_codes
academic_records
faculty_attendance
otp_verifications
```

### users

Stores student, faculty, and HOD accounts.

Important columns:

```text
id
role
name
gender
course
branch
year
semester
roll_number
faculty_code
hod_code
phone_number
phone_verified
profile_photo
password_salt
password_hash
created_at
```

Student login identity:

```text
roll_number
```

Faculty login identity:

```text
faculty_code
```

HOD login identity:

```text
HOD code stored in faculty_code column
```

### sessions

Stores active login sessions.

```text
token
user_id
expires_at
created_at
```

### faculty_codes

Stores valid codes that allow faculty registration.

### hod_codes

Stores valid codes that allow HOD registration.

### academic_records

Stores student attendance, marks, CGPA, and performance.

### faculty_attendance

Stores faculty attendance and performance updated by HOD.

### otp_verifications

Stores generated OTPs and verification status for student phone verification.

## 8. DataGrip SQL Console Commands

Open DataGrip, connect to:

```text
annamacharya_portal.sqlite3
```

Then open a SQL console for that SQLite data source.

### See all tables

```sql
SELECT name
FROM sqlite_master
WHERE type = 'table'
ORDER BY name;
```

### Count all users by role

```sql
SELECT role, COUNT(*) AS total_users
FROM users
GROUP BY role
ORDER BY role;
```

### Count students, faculty, and HODs in one row

```sql
SELECT
  SUM(CASE WHEN role = 'student' THEN 1 ELSE 0 END) AS students,
  SUM(CASE WHEN role = 'faculty' THEN 1 ELSE 0 END) AS faculty,
  SUM(CASE WHEN role = 'hod' THEN 1 ELSE 0 END) AS hods,
  COUNT(*) AS total_users
FROM users;
```

### See newest registered users

```sql
SELECT
  id,
  role,
  name,
  roll_number,
  faculty_code,
  phone_number,
  phone_verified,
  course,
  branch,
  year,
  semester,
  created_at
FROM users
ORDER BY datetime(created_at) DESC, id DESC
LIMIT 20;
```

### See only students

```sql
SELECT
  id,
  name,
  roll_number,
  phone_number,
  phone_verified,
  course,
  branch,
  year,
  semester,
  created_at
FROM users
WHERE role = 'student'
ORDER BY datetime(created_at) DESC;
```

### See only faculty

```sql
SELECT
  id,
  name,
  faculty_code,
  course AS department,
  created_at
FROM users
WHERE role = 'faculty'
ORDER BY datetime(created_at) DESC;
```

### See only HODs

```sql
SELECT
  id,
  name,
  faculty_code AS hod_login_code,
  hod_code,
  course AS department,
  created_at
FROM users
WHERE role = 'hod'
ORDER BY datetime(created_at) DESC;
```

### See student academic records

```sql
SELECT
  u.roll_number,
  u.name,
  u.course,
  u.branch,
  u.year,
  u.semester,
  ar.attendance,
  ar.internal_marks,
  ar.external_marks,
  ar.marks AS total_marks,
  ar.cgpa,
  ar.performance,
  ar.updated_at
FROM users u
LEFT JOIN academic_records ar ON ar.student_id = u.id
WHERE u.role = 'student'
ORDER BY u.roll_number;
```

### Create a faculty code

```sql
INSERT INTO faculty_codes (code, label, active, created_at)
VALUES ('AU-CSE-FAC-001', 'CSE Faculty 001', 1, datetime('now'))
ON CONFLICT(code) DO UPDATE SET
  label = excluded.label,
  active = 1;
```

### Create a HOD code

```sql
INSERT INTO hod_codes (code, label, active, created_at)
VALUES ('AU-HOD-CSE-2026', 'CSE HOD', 1, datetime('now'))
ON CONFLICT(code) DO UPDATE SET
  label = excluded.label,
  active = 1;
```

### Disable a leaked faculty code

```sql
UPDATE faculty_codes
SET active = 0
WHERE code = 'AU-CSE-FAC-001';
```

### Disable a leaked HOD code

```sql
UPDATE hod_codes
SET active = 0
WHERE code = 'AU-HOD-CSE-2026';
```

### Update a student's academic record by roll number

```sql
INSERT INTO academic_records (
  student_id,
  attendance,
  internal_marks,
  external_marks,
  marks,
  cgpa,
  performance,
  updated_at
)
SELECT
  id,
  92,
  80,
  88,
  ROUND((80 + 88) / 2.0, 2),
  8.4,
  'Excellent classroom performance',
  datetime('now')
FROM users
WHERE role = 'student'
  AND roll_number = '24AFAID153'
ON CONFLICT(student_id) DO UPDATE SET
  attendance = excluded.attendance,
  internal_marks = excluded.internal_marks,
  external_marks = excluded.external_marks,
  marks = excluded.marks,
  cgpa = excluded.cgpa,
  performance = excluded.performance,
  updated_at = excluded.updated_at;
```

### Delete a fake or test user safely

Replace `7` with the actual user id.

```sql
DELETE FROM sessions
WHERE user_id = 7;

DELETE FROM academic_records
WHERE student_id = 7;

DELETE FROM faculty_attendance
WHERE faculty_id = 7;

DELETE FROM users
WHERE id = 7;
```

### Inspect active sessions

```sql
SELECT
  s.token,
  s.user_id,
  u.role,
  u.name,
  s.created_at,
  s.expires_at
FROM sessions s
JOIN users u ON u.id = s.user_id
ORDER BY datetime(s.created_at) DESC;
```

### Clear expired sessions

```sql
DELETE FROM sessions
WHERE expires_at <= datetime('now');
```

### Check OTP verification records

```sql
SELECT
  phone_number,
  otp_code,
  verified,
  expires_at,
  created_at
FROM otp_verifications
ORDER BY id DESC
LIMIT 20;
```

## 9. app.py Imported Modules And Purpose

```text
base64
Used to encode password hash bytes into database-safe ASCII text.

hashlib
Used for PBKDF2-HMAC SHA-256 password hashing.

hmac
Used for constant-time comparison of password hashes and OTP codes.

json
Used to read JSON request bodies and send JSON responses.

os
Used to read environment variables such as DATABASE_PATH, HOST, and PORT.

secrets
Used to generate secure random salts, OTP numbers, and session tokens.

sqlite3
Used to connect Python backend to the SQLite database file.

datetime, timedelta, timezone
Used for UTC timestamps, OTP expiry, and session expiry.

HTTPStatus
Used for readable HTTP status codes such as OK, BAD_REQUEST, CONFLICT.

SimpleCookie
Used to read and write browser cookies such as au_session.

SimpleHTTPRequestHandler
Base class used to serve static frontend files and custom API routes.

ThreadingHTTPServer
Runs the local/backend web server and handles requests.

Path
Used for project paths like ROOT, STATIC_DIR, and DB_PATH.

urlparse
Used to separate request path from query string.
```

## 10. Password Security

Passwords are not stored as plain text.

When a user registers:

```text
password -> PBKDF2-HMAC SHA-256 -> password_hash
random salt -> password_salt
```

The database stores:

```text
password_salt
password_hash
```

It does not store:

```text
actual password
```

PBKDF2 iterations used:

```text
260,000
```

Why this matters:

```text
Even if someone opens the users table, they cannot directly read user passwords.
```

## 11. Session Token Security

The portal creates a random session token using:

```text
secrets.token_urlsafe(32)
```

The token is stored in:

```text
sessions.token
```

The browser stores it as:

```text
au_session cookie
```

Cookie properties:

```text
Path=/
Expires=<7 days>
SameSite=Lax
HttpOnly
```

HttpOnly means JavaScript cannot read the cookie directly. This reduces risk from frontend script attacks.

## 12. JWT, API Key, Anonymous Key, SSH Key - General Explanation

### JWT

JWT means JSON Web Token.

It is usually a signed token containing user information and expiry time. A server can verify the token using a secret key or public/private key.

This project does not use JWT.

Current project mechanism:

```text
Random session token + sessions table + HttpOnly cookie
```

### API Key

An API key is a secret string used to identify and authorize software calling an external service.

Examples:

```text
SMS provider API key
Payment gateway API key
Google Maps API key
OpenAI API key
```

This project currently does not need an API key because OTP is demo-mode and shown on screen.

Future real OTP would require an SMS provider API key.

### Anonymous Key

An anon key is commonly used in platforms such as Supabase or Firebase to allow limited public frontend access. It is not a full admin secret.

This project does not use anon keys.

### SSH Key

An SSH key is used to securely connect your computer to a remote server or GitHub without typing a password.

This project does not use SSH in runtime.

You may use SSH only for GitHub push or server maintenance if you configure Git that way.

Runtime authentication for this project is not SSH. It is web login plus session cookie.

## 13. End-To-End Encryption Reality

True end-to-end encryption means data is encrypted on the sender device and only decrypted on the final receiver device. The server cannot read the data.

This project does not implement true end-to-end encryption.

Current security layers:

```text
Passwords: hashed with PBKDF2-HMAC
Login sessions: random tokens in HttpOnly cookies
Frontend/backend transport on Render: HTTPS protects data in transit
Role checks: backend blocks unauthorized dashboards and APIs
SQLite database: not encrypted by default
```

So the correct answer is:

```text
This portal uses HTTPS transport encryption when deployed, secure password hashing, and server-side role-based session control. It does not implement true E2EE or encrypted SQLite at rest in the current free demo version.
```

Production upgrades:

```text
Use HTTPS only
Set Secure flag on cookies
Use SQLCipher or managed encrypted database
Add CSRF protection
Use real SMS OTP provider
Add audit logs
Add admin approval flow
Add password reset flow
Use persistent cloud database
```

## 14. OTP Mechanism

Current demo OTP flow:

```text
Student enters phone number
Clicks Send OTP
Frontend calls /api/request-otp
Backend generates 6 digit OTP
Backend stores OTP in otp_verifications
Backend returns demo_otp to frontend
Student enters OTP
Frontend calls /api/verify-otp
Backend checks latest unverified non-expired OTP
Backend marks OTP verified
Student can register
```

In production:

```text
Backend would send OTP through SMS provider.
Frontend would not display demo_otp.
```

Possible SMS providers:

```text
Twilio
Fast2SMS
MSG91
Firebase Auth
```

## 15. Deployment Mechanism

Current free deployment target:

```text
Render Web Service
```

The project has `render.yaml`:

```text
runtime: python
buildCommand: python3 manage.py init-db
startCommand: HOST=0.0.0.0 DATABASE_PATH=/tmp/annamacharya_portal.sqlite3 python3 app.py
healthCheckPath: /healthz
```

Important:

```text
DATABASE_PATH=/tmp/annamacharya_portal.sqlite3
```

This is free but temporary. On Render free deployment, data can reset when the service restarts or redeploys.

For a college demo, this is acceptable. For real production, use:

```text
Render persistent disk
PostgreSQL
Supabase
Neon
Railway
AWS RDS
```

## 16. What To Say During Demonstration

Short technical explanation:

```text
This is a role-based academic portal for students, faculty, and HODs. The frontend is built with HTML, CSS, and JavaScript. JavaScript sends JSON requests to Python API endpoints. Python validates input, applies role checks, hashes passwords, manages session cookies, and stores data in SQLite. Students can see only their own dashboard. Faculty can update student academic records. HOD can supervise faculty attendance. The system uses server-side session tokens rather than JWT.
```

Security explanation:

```text
Passwords are not stored directly. They are hashed using PBKDF2-HMAC SHA-256 with a random salt. Login creates a secure random token stored in the sessions table and sent to browser as an HttpOnly cookie. Protected API routes call require_user() to allow only correct roles.
```

Database explanation:

```text
The main table is users. Student records connect to academic_records. Faculty and HOD codes are controlled through faculty_codes and hod_codes tables. Sessions are stored separately in sessions. OTP verification is stored in otp_verifications.
```

Deployment explanation:

```text
The project is deployed as a Python web service. Render runs the build command to initialize the SQLite schema, then starts app.py with host 0.0.0.0. Free deployment uses a temporary SQLite file, so production would require persistent storage or a cloud database.
```

## 17. Limitations And Future Scope

Current limitations:

```text
SQLite on free Render is temporary
OTP is demo-mode and shown on screen
No admin dashboard yet
No password reset
No audit log table
No true E2EE
No encrypted database at rest
No email/SMS provider key configured
```

Future improvements:

```text
Admin dashboard for you
Approval workflow for faculty/HOD accounts
Real SMS OTP
Persistent PostgreSQL database
Audit logs for every faculty/HOD update
CSV export for student records
Password reset with email OTP
Secure cookie flag in production
CSRF protection
Rate limiting for login attempts
```

## 18. Final Architecture In One Flow

```text
User opens website
-> splash intro page
-> role selection
-> registration or login form
-> JavaScript fetch() sends JSON
-> Python app.py receives API request
-> validates role and inputs
-> checks faculty/HOD codes or OTP
-> hashes/verifies password
-> reads/writes SQLite tables
-> creates session cookie on login/register
-> frontend receives JSON response
-> frontend opens role-specific dashboard
-> protected dashboard APIs check session and role every time
```

This is the core mechanism of the Annamacharya University Portal.
