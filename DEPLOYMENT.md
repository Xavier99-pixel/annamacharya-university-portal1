# Deployment Guide

This project has two parts:

- Frontend: `static/index.html`, `static/styles.css`, `static/app.js`, images
- Backend/database: `app.py` plus SQLite database file

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

Do not use the Render production start command on your Mac:

```bash
HOST=0.0.0.0 DATABASE_PATH=/var/data/annamacharya_portal.sqlite3 python3 app.py
```

That command is only for Render after you add a persistent disk mounted at `/var/data`. On your Mac, `/var/data` usually does not exist and your user may not have permission to create it.

## SQLite Tables

`users`

Stores student and staff accounts. Student accounts use `roll_number`; staff accounts use `faculty_code`.

`sessions`

Stores login sessions, so the browser can remain logged in.

`faculty_codes`

Stores valid university staff/faculty registration codes.

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

## Recommended Full Deployment: Render Web Service

This is the simplest path for the current Python + SQLite project.

1. Create a GitHub repository.
2. Upload/push this project folder to GitHub.
3. Go to Render and create a new Web Service from the GitHub repository.
4. Use these settings:

```text
Runtime: Python
Build Command: python3 manage.py init-db
Start Command: HOST=0.0.0.0 DATABASE_PATH=/var/data/annamacharya_portal.sqlite3 python3 app.py
```

5. Add a persistent disk:

```text
Mount path: /var/data
Size: smallest available for your plan
```

6. Deploy the service.
7. Open the Render URL.

Important: without a persistent disk, your SQLite database can disappear after redeploy/restart on many hosting platforms.

## Netlify Option

Netlify is perfect for the static frontend, but this exact Python + SQLite backend will not run as a normal Netlify static site.

You have two choices:

1. Frontend-only demo on Netlify

Drag the `static` folder to Netlify Drop. The page will open, but registration/login will fail unless the Python backend is hosted somewhere else.

2. Full Netlify backend rebuild

Rewrite `/api/register`, `/api/login`, and `/api/logout` as Netlify Functions and use Netlify Database or another cloud database instead of the local SQLite file.

For this project right now, use Render for full backend + SQLite deployment.
