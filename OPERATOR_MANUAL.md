# Annamacharya University Portal Operator Manual

This document is the day-to-day procedure for running, checking, editing, and deploying the Annamacharya University student/faculty/HOD portal.

## 0. Project Map

Project folder:

```text
/Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
```

Important files:

```text
app.py                         Python backend server
manage.py                      Admin commands for SQLite
annamacharya_portal.sqlite3    SQLite database file
static/index.html              Frontend HTML
static/styles.css              Frontend CSS
static/app.js                  Frontend JavaScript/API calls
static/images/                 Logo and campus images
DEPLOYMENT.md                  Short deployment guide
OPERATOR_MANUAL.md             This full manual
```

The data flow:

```text
Student/Faculty form in browser
        ↓
static/app.js sends API request
        ↓
app.py receives /api/register or /api/login
        ↓
Python sqlite3 opens annamacharya_portal.sqlite3
        ↓
Data is inserted/read from SQLite tables
```

The browser does not talk directly to SQLite. The browser talks to Python. Python talks to SQLite.

## 1. Start The Project Locally

Open Terminal.

Go to the project:

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
```

Prepare the database:

```bash
python3 manage.py init-db
```

Start the backend:

```bash
python3 app.py
```

Open the website:

```text
http://127.0.0.1:8000
```

Important:

Use this command on your Mac:

```bash
python3 app.py
```

Do not use this command on your Mac:

```bash
HOST=0.0.0.0 DATABASE_PATH=/var/data/annamacharya_portal.sqlite3 python3 app.py
```

That is the Render production start command. `/var/data` is a Render persistent-disk path, not your local Mac project path.

Stop the server:

```text
Press Control + C in Terminal
```

## 2. Database Tables You Must Know

`users`

Stores all registered students, faculty, and HOD users.

Important columns:

```text
id              Auto ID
role            student, faculty, or hod
name            Full name
gender          Gender
course          Student course or faculty/HOD department
branch          Student branch
year            Student year
semester        Student semester
roll_number     Student login ID
faculty_code    Faculty/HOD login ID
hod_code        HOD verification code
profile_photo   Uploaded profile photo as text data
password_salt   Password security value
password_hash   Hashed password
created_at      Account creation date
```

Do not manually edit:

```text
password_salt
password_hash
```

If you manually change those, login can break.

`faculty_codes`

Stores valid faculty/staff registration codes.

`hod_codes`

Stores valid HOD verification codes.

`academic_records`

Stores student attendance, marks, CGPA, and performance.

`faculty_attendance`

Stores faculty attendance and performance maintained by HOD accounts.

Important columns:

```text
code        Example: AU-CSE-2026
label       Human note, like CSE faculty registration
active      1 means usable, 0 means disabled
created_at  Created date
```

`sessions`

Stores current login sessions. You normally do not edit this table.

`sqlite_sequence`

Internal SQLite table. Do not edit.

## 3. Open The Database In DataGrip

1. Open **DataGrip**.
2. In the left side, open the **Database** tool window.
3. Click **+**.
4. Click **Data Source**.
5. Click **SQLite**.
6. If DataGrip asks to download driver files, click **Download**.
7. In the SQLite connection window, find **File**.
8. Select:

```text
/Users/tirumalarajavardhan/Downloads/annamacharya-university-portal/annamacharya_portal.sqlite3
```

9. Click **Test Connection**.
10. If it says successful, click **OK** or **Apply**.

Now expand:

```text
SQLite database
  main
    tables
      users
      faculty_codes
      sessions
```

## 4. See If Student Or Faculty Registered Through Portal

### Option A: DataGrip Click Method

1. Open DataGrip.
2. Expand the SQLite database.
3. Expand `main`.
4. Expand `tables`.
5. Double-click `users`.
6. Look at the `role` column:

```text
student = student account
faculty = faculty account
hod     = Head of Department account
```

Student identification:

```text
role = student
roll_number has value
faculty_code is empty
```

Faculty identification:

```text
role = faculty
faculty_code has value
roll_number is empty
```

HOD identification:

```text
role = hod
faculty_code has value
hod_code has value
roll_number is empty
```

### Option B: DataGrip SQL Query

Open a SQL console in DataGrip and run:

```sql
SELECT id, role, name, gender, course, branch, year, semester, roll_number, faculty_code, hod_code, created_at
FROM users
ORDER BY id DESC;
```

Only students:

```sql
SELECT id, name, course, year, semester, roll_number, created_at
FROM users
WHERE role = 'student'
ORDER BY id DESC;
```

Only faculty:

```sql
SELECT id, name, course AS department, faculty_code, created_at
FROM users
WHERE role = 'faculty'
ORDER BY id DESC;
```

Only HOD:

```sql
SELECT id, name, course AS department, faculty_code, hod_code, created_at
FROM users
WHERE role = 'hod'
ORDER BY id DESC;
```

### Option C: Terminal Method

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
python3 manage.py list-users
```

## 5. Remove Or Modify Student Data In DataGrip

Before editing, make a backup:

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
cp annamacharya_portal.sqlite3 backup-before-edit.sqlite3
```

### Modify Student Name, Course, Year, Semester

1. Open DataGrip.
2. Double-click `users`.
3. Find the student row.
4. Edit simple fields only:

```text
name
gender
course
year
semester
roll_number
```

5. Click **Submit**, **Commit**, or the green checkmark depending on your DataGrip view.
6. Refresh your webpage.
7. Log out and log in again if dashboard data does not update immediately.

Safe SQL example:

```sql
UPDATE users
SET name = 'New Student Name',
    course = 'B.Tech',
    year = '2nd Year',
    semester = 'Semester 3'
WHERE id = 1
  AND role = 'student';
```

### Change Roll Number

```sql
UPDATE users
SET roll_number = 'AU24CSE001'
WHERE id = 1
  AND role = 'student';
```

After changing roll number, the student must log in with the new roll number.

### Delete A Student

First remove sessions:

```sql
DELETE FROM sessions
WHERE user_id = 1;
```

Then remove user:

```sql
DELETE FROM users
WHERE id = 1
  AND role = 'student';
```

Safer terminal method:

```bash
python3 manage.py delete-user 1
```

### Reflect Changes In Webpage

If your change is in SQLite:

1. Click **Submit/Commit** in DataGrip.
2. Refresh the browser.
3. Log out.
4. Log in again.

Why login again? The dashboard loads the logged-in user through `/api/me`. A fresh login/session makes sure you see the newest database row.

## 6. Create Faculty Codes And Give Them To Faculty

Faculty codes are not passwords. They are registration permission codes.

The flow:

```text
Admin creates faculty code
        ↓
Admin gives code to real faculty member
        ↓
Faculty opens Faculty/HOD Registration
        ↓
Faculty enters code and password
        ↓
Portal creates faculty account
        ↓
Faculty later logs in using faculty code + password
```

### Recommended Code Format

Use readable, controlled codes:

```text
AU-CSE-2026
AU-MBA-2026
AU-EEE-2026
AU-MECH-2026
AU-ADMIN-2026
```

### Create Faculty Code Using Terminal

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
python3 manage.py add-code AU-CSE-2026 --label "CSE faculty registration"
```

Check active codes:

```bash
python3 manage.py list-codes
```

Create a HOD verification code:

```bash
python3 manage.py add-hod-code AU-HOD-CSE-2026 --label "CSE HOD verification"
```

Check active HOD codes:

```bash
python3 manage.py list-hod-codes
```

For HOD registration, give both codes:

```text
Faculty Code: AU-CSE-2026
HOD Code: AU-HOD-CSE-2026
```

Give the code to the faculty member:

```text
Faculty Registration Code: AU-CSE-2026
Portal URL: http://127.0.0.1:8000
```

For deployed site, replace the URL with your real hosted URL.

### Create Faculty Code In DataGrip

Open `faculty_codes`.

Insert a row:

```text
code: AU-CSE-2026
label: CSE faculty registration
active: 1
created_at: 2026-06-16T00:00:00+00:00
```

Then click **Submit/Commit**.

SQL method:

```sql
INSERT INTO faculty_codes (code, label, active, created_at)
VALUES ('AU-CSE-2026', 'CSE faculty registration', 1, datetime('now'));
```

Disable a code:

```sql
UPDATE faculty_codes
SET active = 0
WHERE code = 'AU-CSE-2026';
```

## 7. Localhost, API, SSH Key, And Real Hosting

### What Localhost Means

```text
http://127.0.0.1:8000
```

This means the website is running only on your laptop.

Other devices cannot use your localhost unless they are specially connected to your machine. For a real website, deploy the project to a hosting provider.

### What API Means In This Project

Your API routes are inside `app.py`:

```text
/api/register
/api/login
/api/logout
/api/me
/api/faculty-codes
```

The frontend calls these routes from `static/app.js`.

You do not need to create a separate API key for this project right now.

### What SSH Key Means

An SSH key is usually for connecting your laptop to GitHub or a server securely.

For GitHub, generate an SSH key:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

GitHub officially recommends generating an SSH key locally, then adding the public key to your GitHub account for SSH Git operations.

Add it to macOS keychain:

```bash
eval "$(ssh-agent -s)"
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

Show public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy that output and add it in GitHub:

```text
GitHub → Settings → SSH and GPG keys → New SSH key
```

## 8. Deployment Recommendation

For this exact project, use **Render Web Service**.

Reason:

```text
This project uses Python backend + SQLite database file.
```

Render can host dynamic web apps and gives every web service an `onrender.com` public URL. Render web services must bind to host `0.0.0.0` to receive public internet traffic.

SQLite needs persistent storage. Render says services have an ephemeral filesystem by default, and without a persistent disk local file changes are lost after redeploys/restarts. So use a persistent disk mounted at `/var/data`.

## 9. Prepare Project For GitHub

Open Terminal:

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
```

Initialize Git:

```bash
git init
```

Check files:

```bash
git status
```

Add files:

```bash
git add .
```

Commit:

```bash
git commit -m "Initial Annamacharya University portal"
```

Create a new repository on GitHub:

1. Go to GitHub.
2. Click **New repository**.
3. Repository name:

```text
annamacharya-university-portal
```

4. Keep it public or private.
5. Do not add README from GitHub because this project already has README.
6. Click **Create repository**.

GitHub will show commands. Use SSH style if your SSH key is ready:

```bash
git remote add origin git@github.com:YOUR_USERNAME/annamacharya-university-portal.git
git branch -M main
git push -u origin main
```

If SSH is not ready, use HTTPS:

```bash
git remote add origin https://github.com/YOUR_USERNAME/annamacharya-university-portal.git
git branch -M main
git push -u origin main
```

Important: `.gitignore` prevents the local SQLite file from being pushed. That is correct.

## 10. Deploy On Render

1. Go to Render.
2. Sign in.
3. Click **New**.
4. Click **Web Service**.
5. Connect your GitHub repository.
6. Select:

```text
Repository: annamacharya-university-portal
Branch: main
Runtime/Language: Python
```

7. Set build command:

```bash
python3 manage.py init-db
```

8. Set start command:

```bash
HOST=0.0.0.0 DATABASE_PATH=/var/data/annamacharya_portal.sqlite3 python3 app.py
```

This command belongs only inside Render's **Start Command** field. Do not run it locally on your Mac.

9. Open **Advanced**.
10. Add persistent disk:

```text
Mount path: /var/data
Size: smallest available size
```

11. Click **Create Web Service**.
12. Wait for deploy to finish.
13. Open your Render URL:

```text
https://your-service-name.onrender.com
```

That URL can be opened from other devices.

## 11. Optional Custom Domain

After Render works:

1. Buy or use a domain.
2. In Render service, open **Settings**.
3. Open **Custom Domains**.
4. Add your domain, for example:

```text
portal.annamacharyauniversity.example
```

5. Render will show DNS records.
6. Go to your domain provider.
7. Add the DNS records Render gives you.
8. Wait for DNS verification.

## 12. Small Change Procedure

Use this for text, CSS, button labels, images, or small frontend changes.

1. Edit files in VS Code.
2. Run locally:

```bash
python3 app.py
```

3. Open:

```text
http://127.0.0.1:8000
```

4. Test the changed page.
5. Stop server with Control + C.
6. Commit:

```bash
git status
git add .
git commit -m "Update portal frontend"
git push
```

7. Render auto-deploys after push if auto-deploy is enabled.

## 13. Large Change Procedure

Use this for database schema changes, backend logic changes, registration/login changes, or deployment config changes.

1. Backup local database:

```bash
cp annamacharya_portal.sqlite3 backup-before-large-change.sqlite3
```

2. Edit code.
3. Rebuild/check database:

```bash
python3 manage.py init-db
```

4. Run syntax check:

```bash
python3 -m py_compile app.py manage.py
```

5. Run local server:

```bash
python3 app.py
```

6. Test:

```text
Student registration
Student login
Staff registration with valid faculty code
Staff registration with invalid faculty code
Staff login
Logout
```

7. Check database:

```bash
python3 manage.py list-users
python3 manage.py list-codes
```

8. Commit and push:

```bash
git status
git add .
git commit -m "Update backend and database flow"
git push
```

9. Watch Render deploy logs.
10. Test the Render URL.

## 14. Production Database Management After Deployment

For a deployed Render app with SQLite on `/var/data`, do not expect DataGrip on your laptop to automatically see the server database. Your laptop database and deployed database are different files.

Local database:

```text
/Users/tirumalarajavardhan/Downloads/annamacharya-university-portal/annamacharya_portal.sqlite3
```

Render database:

```text
/var/data/annamacharya_portal.sqlite3
```

To manage production data:

Option A:

Use Render Shell, then run:

```bash
python3 manage.py list-users
python3 manage.py list-codes
python3 manage.py add-code AU-CSE-2026 --label "CSE faculty registration"
```

Option B:

Download the production database file, edit carefully, then upload it back. This is riskier.

## 15. Safety Rules

Do:

```text
Backup database before big edits
Use manage.py for faculty codes
Refresh and log in again after database edits
Keep faculty codes private
Use active = 0 to disable old faculty codes
```

Do not:

```text
Do not edit password_hash manually
Do not edit password_salt manually
Do not edit sqlite_sequence
Do not share database file publicly
Do not push annamacharya_portal.sqlite3 to GitHub
Do not deploy SQLite without persistent disk
```

## 16. Most Common Commands

Start app:

```bash
python3 app.py
```

Prepare database:

```bash
python3 manage.py init-db
```

List users:

```bash
python3 manage.py list-users
```

List faculty codes:

```bash
python3 manage.py list-codes
```

Add faculty code:

```bash
python3 manage.py add-code AU-CSE-2026 --label "CSE faculty registration"
```

Disable faculty code:

```bash
python3 manage.py deactivate-code AU-CSE-2026
```

Delete user:

```bash
python3 manage.py delete-user 1
```

Check Python:

```bash
python3 -m py_compile app.py manage.py
```

Git deploy cycle:

```bash
git status
git add .
git commit -m "Describe change"
git push
```

## 17. Final Mental Model

Use the portal for normal registration.

Use DataGrip for seeing and carefully editing data.

Use `manage.py` for admin operations.

Use GitHub to store code.

Use Render to make it a public website.

Use a persistent disk so the SQLite database survives deploys.
