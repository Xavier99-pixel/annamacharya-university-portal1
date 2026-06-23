# Deployment Guide

This project has two parts:

- Frontend: `static/index.html`, `static/styles.css`, `static/app.js`, images
- Backend/database: `app.py` plus SQLite database file
- Workspaces: student dashboard, faculty workspace, and HOD workspace

The frontend does not connect directly to SQLite. The flow is:

```text
Browser form -> /api/register or /api/login -> Python app.py -> SQLite database
```

## Local Database Operation

Go to the project folder:

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
```

Create/update database tables:

```bash
python3 manage.py init-db
```

Run the app:

```bash
python3 app.py
```

Open:

```text
http://127.0.0.1:8000
```

Do not use the Render start command on your Mac:

```bash
HOST=0.0.0.0 DATABASE_PATH=/tmp/annamacharya_portal.sqlite3 python3 app.py
```

That command is only for the hosted Render environment. On your Mac, use `python3 app.py`.

## SQLite Tables

`users`

Stores student, faculty, and HOD accounts. Student accounts use `roll_number`; faculty and HOD accounts use `faculty_code`.

`sessions`

Stores login sessions, so the browser can remain logged in.

`faculty_codes`

Stores valid university staff/faculty registration codes.

`hod_codes`

Stores valid HOD verification codes.

`academic_records`

Stores student attendance, marks, CGPA, and performance.

`exam_marks`

Stores semester-wise subject marks: mid exams, assignments, lab internals, external theory/lab marks, final grade, and status.

`faculty_attendance`

Stores faculty attendance and performance controlled by HOD accounts.

## Faculty Code Commands

List codes:

```bash
python3 manage.py list-codes
```

Create a new code:

```bash
python3 manage.py add-code AU-CSE-2026 --label "CSE faculty registration"
```

Use that code in the Staff Registration form.

Create a HOD verification code:

```bash
python3 manage.py add-hod-code AU-HOD-CSE-2026 --label "CSE HOD verification"
```

Use only the HOD code in the HOD registration flow. The HOD also logs in with that HOD code.

Disable a code:

```bash
python3 manage.py deactivate-code AU-CSE-2026
```

List registered users:

```bash
python3 manage.py list-users
```

Delete a user:

```bash
python3 manage.py delete-user 1
```

## Free Deployment: Render Web Service

This is the simplest free path for the current Python + SQLite project.

Important free-mode limitation without cloud backup:

```text
SQLite data on Render free mode is temporary.
If the service restarts or redeploys, registered users and marks can reset.
```

The portal now supports an optional free cloud-backup layer. The website still uses SQLite, but after registrations, marks, notices, codes, or admin changes, it uploads the live SQLite file to Supabase Storage. On Render restart, if `/tmp/annamacharya_portal.sqlite3` is empty, the app downloads the latest backup first.

1. Create a GitHub repository.
2. Upload/push this project folder to GitHub.
3. Go to Render and create a new Web Service from the GitHub repository.
4. Use these settings:

```text
Runtime: Python
Build Command: python3 manage.py init-db
Start Command: HOST=0.0.0.0 DATABASE_PATH=/tmp/annamacharya_portal.sqlite3 python3 app.py
```

5. Do not add a disk if you want free deployment.
6. Deploy the service.
7. Open the Render URL.

Optional but recommended for the Admin Monitor:

```text
Environment Variable: ADMIN_KEY
Value: choose-your-private-admin-key
```

On Render, set `ADMIN_KEY`. If you do not set it, deployed admin actions are blocked.

## Free Persistent Backup With Supabase Storage

Use this when you want free Render hosting but do not want student/faculty/HOD data to vanish after restart.

1. Create a free Supabase project.
2. Go to Supabase Project Settings.
3. Copy the Project URL.
4. Copy the service role key. Keep this private. Do not paste it in frontend code.
5. In Render, open your web service.
6. Go to Environment.
7. Add these variables:

```text
CLOUD_BACKUP_PROVIDER=supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_BUCKET=annamacharya-portal-backups
SUPABASE_OBJECT_PATH=annamacharya_live_database.sqlite3
```

8. Redeploy the Render service.

How it works:

```text
Student/faculty/HOD/admin change -> SQLite writes data -> app uploads SQLite backup to Supabase Storage
Render restart -> local /tmp database is empty -> app downloads SQLite backup -> users appear again
```

You can still use the Admin Monitor SQLite Backup button. Supabase backup is an automatic safety copy, while Admin Monitor backup is your manual download.

For free real-SMS demo OTP, the portal automatically uses Textbelt on Render when `SMS_PROVIDER` is not set. You can also add it manually:

```text
SMS_PROVIDER=textbelt
SMS_COUNTRY_CODE=+91
TEXTBELT_KEY=textbelt
```

Textbelt free demo SMS is limited, so use it for evaluation/testing only.

If you later use Twilio trial or paid SMS, add:

```text
SMS_PROVIDER=twilio
SMS_COUNTRY_CODE=+91
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_FROM_NUMBER=+1xxxxxxxxxx
```

Local testing can use demo OTP mode, but do not expose demo OTPs on a public college demo unless you intentionally set `SMS_DEMO_MODE=true`.

For permanent production data later, upgrade to a persistent disk or use a cloud database.

## Netlify Option

Netlify is perfect for the static frontend, but this exact Python + SQLite backend will not run as a normal Netlify static site.

You have two choices:

1. Frontend-only demo on Netlify

Drag the `static` folder to Netlify Drop. The page will open, but registration/login will fail unless the Python backend is hosted somewhere else.

2. Full Netlify backend rebuild

Rewrite `/api/register`, `/api/login`, and `/api/logout` as Netlify Functions and use Netlify Database or another cloud database instead of the local SQLite file.

For this project right now, use Render for full backend + SQLite deployment.
