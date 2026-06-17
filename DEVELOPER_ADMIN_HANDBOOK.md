# Annamacharya University Portal Developer/Admin Handbook

This document explains your exact role as the creator, developer, database admin, and maintainer of this project.

You are not only the person who made the website. In this system, you are the **Portal Administrator**.

Your job is to:

- Keep the website running
- Control faculty and HOD registration codes
- Monitor registered users
- Verify that students, faculty, and HODs are entering correct data
- Maintain the SQLite database
- Deploy updates
- Fix wrong records
- Protect role-based access
- Explain the architecture during your college project review

## 1. System Roles

There are four human roles in this project:

```text
1. Student
2. Faculty
3. HOD
4. You, the Portal Administrator / Developer
```

## 2. Student Role

A student can:

- Register with profile photo
- Enter name, gender, course, branch, year, semester, roll number
- Create password
- Login using roll number and password
- See only their own dashboard
- See attendance, marks, CGPA, and performance after faculty updates them

A student cannot:

- See all students
- Edit marks
- Edit attendance
- Access faculty dashboard
- Access HOD dashboard
- Create faculty codes
- Create HOD codes

Backend protection:

```text
Student role = student
Login ID = roll_number
Allowed dashboard = student-dashboard
Blocked from = /api/students, /api/faculty, /api/student-record, /api/faculty-attendance
```

## 3. Faculty Role

A faculty member can:

- Register with faculty code
- Login using faculty code and password
- See faculty dashboard
- View registered students
- Search/filter students
- Update student attendance
- Update student marks
- Update student CGPA
- Update student performance

A faculty member cannot:

- Access HOD dashboard
- Update faculty attendance
- Create HOD users
- Create codes
- Delete users
- Modify raw database directly

Backend protection:

```text
Faculty role = faculty
Login ID = faculty_code
Allowed dashboard = faculty-dashboard
Allowed API = /api/students, /api/student-record
Blocked from = /api/faculty, /api/faculty-attendance
```

## 4. HOD Role

An HOD can:

- Register using faculty code + HOD code
- Login using faculty code and password
- See HOD dashboard
- View faculty directory
- Update faculty attendance
- Update faculty performance
- View student academic overview

An HOD cannot:

- Directly change passwords
- Create new faculty/HOD codes from website
- Delete users from website

Backend protection:

```text
HOD role = hod
Login ID = faculty_code
Extra verification at registration = hod_code
Allowed dashboard = hod-dashboard
Allowed API = /api/faculty, /api/faculty-attendance, /api/students, /api/student-record
```

## 5. Your Role As Portal Administrator

You are the highest authority in this project.

Your responsibilities:

```text
1. Run the project locally
2. Deploy the project online
3. Create faculty codes
4. Create HOD codes
5. Monitor student registrations
6. Monitor faculty registrations
7. Monitor HOD registrations
8. Correct wrong data
9. Remove fake/test users
10. Backup the database
11. Maintain GitHub commits
12. Deploy latest changes
13. Explain the architecture
```

You are the only person who should directly manage:

```text
manage.py
DataGrip
GitHub
Render deployment
SQLite database
```

## 6. What Happens When A Student Registers

Student fills form:

```text
name
gender
course
branch
year
semester
roll_number
password
profile_photo
```

Frontend sends:

```text
POST /api/register
```

Backend does:

```text
Checks role = student
Checks required fields
Hashes password
Stores account in users table
Creates empty academic_records row
Creates login session
Redirects to student dashboard
```

Database tables affected:

```text
users
academic_records
sessions
```

Your monitoring work:

```sql
SELECT id, name, course, branch, year, semester, roll_number, created_at
FROM users
WHERE role = 'student'
ORDER BY id DESC;
```

What you check:

```text
Is the roll number real?
Is the student name correct?
Is course/branch/year/semester correct?
Is there duplicate/fake account?
```

## 7. What Happens When Faculty Registers

Faculty fills form:

```text
name
gender
department
faculty_code
password
profile_photo
```

Frontend sends:

```text
POST /api/register
```

Backend does:

```text
Checks role = faculty
Checks faculty_code exists in faculty_codes table
Hashes password
Stores account in users table
Creates empty faculty_attendance row
Creates login session
Redirects to faculty dashboard
```

Database tables affected:

```text
users
faculty_attendance
sessions
```

Your monitoring query:

```sql
SELECT id, name, course AS department, faculty_code, created_at
FROM users
WHERE role = 'faculty'
ORDER BY id DESC;
```

What you check:

```text
Is the faculty code valid?
Is the faculty member real?
Is department correct?
Was faculty code leaked to a wrong person?
```

## 8. What Happens When HOD Registers

HOD fills same staff form but checks:

```text
Register as HOD
```

HOD must enter:

```text
faculty_code
hod_code
```

Backend does:

```text
Checks faculty_code exists in faculty_codes
Checks hod_code exists in hod_codes
Creates role = hod
Stores account in users table
Creates faculty_attendance row
Creates login session
Redirects to HOD dashboard
```

Database tables affected:

```text
users
faculty_attendance
sessions
```

Your monitoring query:

```sql
SELECT id, name, course AS department, faculty_code, hod_code, created_at
FROM users
WHERE role = 'hod'
ORDER BY id DESC;
```

What you check:

```text
Is this person really HOD?
Was HOD code given only to authorized person?
Should the HOD code be disabled after use?
```

## 9. Your Code Management Responsibility

Faculty codes and HOD codes are controlled by you.

### Create Faculty Code

```bash
cd /Users/tirumalarajavardhan/Downloads/annamacharya-university-portal
python3 manage.py add-code AU-CSE-2026 --label "CSE faculty registration"
```

Give to faculty:

```text
Faculty Registration Code: AU-CSE-2026
```

### Create HOD Code

```bash
python3 manage.py add-hod-code AU-HOD-CSE-2026 --label "CSE HOD verification"
```

Give to HOD:

```text
Faculty Code: AU-CSE-2026
HOD Code: AU-HOD-CSE-2026
```

### List Faculty Codes

```bash
python3 manage.py list-codes
```

### List HOD Codes

```bash
python3 manage.py list-hod-codes
```

### Disable Faculty Code

```bash
python3 manage.py deactivate-code AU-CSE-2026
```

### Disable HOD Code

```bash
python3 manage.py deactivate-hod-code AU-HOD-CSE-2026
```

Best practice:

```text
Create one faculty code per department or faculty member.
Create HOD codes only for HOD accounts.
Disable codes if they are leaked or no longer needed.
```

## 10. DataGrip Monitoring Routine

Open DataGrip:

```text
DataGrip → SQLite data source → annamacharya_portal.sqlite3
```

Open these tables:

```text
users
faculty_codes
hod_codes
academic_records
faculty_attendance
sessions
```

Daily check queries:

```sql
SELECT id, role, name, course, branch, year, semester, roll_number, faculty_code, hod_code, created_at
FROM users
ORDER BY id DESC;
```

Student academic records:

```sql
SELECT
  u.roll_number,
  u.name,
  u.course,
  u.branch,
  u.year,
  u.semester,
  a.attendance,
  a.marks,
  a.cgpa,
  a.performance,
  a.updated_at
FROM users u
LEFT JOIN academic_records a ON a.student_id = u.id
WHERE u.role = 'student'
ORDER BY u.roll_number;
```

Faculty attendance:

```sql
SELECT
  u.faculty_code,
  u.name,
  u.course AS department,
  f.attendance,
  f.performance,
  f.updated_at
FROM users u
LEFT JOIN faculty_attendance f ON f.faculty_id = u.id
WHERE u.role IN ('faculty', 'hod')
ORDER BY u.course, u.name;
```

Active faculty codes:

```sql
SELECT * FROM faculty_codes
WHERE active = 1
ORDER BY code;
```

Active HOD codes:

```sql
SELECT * FROM hod_codes
WHERE active = 1
ORDER BY code;
```

## 11. What You Can Safely Edit In DataGrip

Safe to edit:

```text
users.name
users.gender
users.course
users.branch
users.year
users.semester
users.roll_number
users.faculty_code
faculty_codes.active
hod_codes.active
academic_records.attendance
academic_records.marks
academic_records.cgpa
academic_records.performance
faculty_attendance.attendance
faculty_attendance.performance
```

Do not manually edit:

```text
users.password_hash
users.password_salt
sessions.token
sqlite_sequence
```

If a password is wrong, the clean solution is:

```text
Delete user account and ask user to register again
```

## 12. Delete Fake Or Test Users

Use `manage.py` if possible:

```bash
python3 manage.py list-users
python3 manage.py delete-user USER_ID
```

Example:

```bash
python3 manage.py delete-user 7
```

Manual SQL method:

```sql
DELETE FROM sessions WHERE user_id = 7;
DELETE FROM academic_records WHERE student_id = 7;
DELETE FROM faculty_attendance WHERE faculty_id = 7;
DELETE FROM users WHERE id = 7;
```

Always delete dependent records first.

## 13. Faculty Updating Student Records

Faculty enters:

```text
roll_number
attendance
marks
cgpa
performance
```

Frontend sends:

```text
POST /api/student-record
```

Backend checks:

```text
Is logged-in user faculty or HOD?
Does student roll number exist?
Are attendance/marks/CGPA valid numbers?
```

Database updated:

```text
academic_records
```

Student dashboard then shows:

```text
Attendance
Marks
CGPA
Performance
```

## 14. HOD Updating Faculty Attendance

HOD enters:

```text
faculty_code
attendance
performance
```

Frontend sends:

```text
POST /api/faculty-attendance
```

Backend checks:

```text
Is logged-in user HOD?
Does faculty_code exist?
Is attendance valid?
```

Database updated:

```text
faculty_attendance
```

## 15. Permission Mechanism

The important backend function:

```text
require_user(headers, allowed_roles)
```

This checks:

```text
1. Is user logged in?
2. Is user role allowed for this API?
```

Examples:

```text
/api/students allows faculty and hod
/api/student-record allows faculty and hod
/api/faculty allows hod only
/api/faculty-attendance allows hod only
```

If wrong role tries access:

```text
HTTP 403 Forbidden
```

This is what makes your project role-based and professional.

## 16. Your Maintenance Schedule

### Every Time Before Demo

Run:

```bash
python3 manage.py init-db
python3 manage.py list-users
python3 manage.py list-codes
python3 manage.py list-hod-codes
python3 manage.py list-records
python3 app.py
```

Open:

```text
http://127.0.0.1:8000
```

Test:

```text
Student login
Faculty login
HOD login
Faculty updates student
HOD updates faculty
```

### Weekly Maintenance

```text
1. Backup database
2. Check fake users
3. Disable leaked codes
4. Check student marks and attendance records
5. Commit code changes
6. Push to GitHub
7. Deploy latest commit
```

Backup:

```bash
cp annamacharya_portal.sqlite3 backup-$(date +%Y%m%d).sqlite3
```

## 17. Deployment Responsibility

Free Render deployment uses:

```text
DATABASE_PATH=/tmp/annamacharya_portal.sqlite3
```

This is free but temporary.

Your free-hosted data can reset.

Your job before demo:

```text
1. Open deployed URL
2. Register demo student/faculty/HOD again if data reset
3. Add marks/attendance for demo
4. Show role-based dashboards
```

If you need permanent online data:

```text
Upgrade to paid persistent disk or move database to cloud database.
```

## 18. GitHub Responsibility

Every project update should be committed.

Commands:

```bash
git status
git add .
git commit -m "Describe the update"
git push origin main
```

Render deploys from GitHub.

If Render says repository is empty:

```text
Wrong repo connected OR no commit pushed
```

Correct repo:

```text
Xavier99-pixel/annamacharya-university-portal1
```

Correct branch:

```text
main
```

## 19. Your Explanation In Project Review

Say this:

```text
This project is a role-based academic portal for Annamacharya University.
Students register using roll number and can view only their own academic profile.
Faculty register using university faculty codes and can update student academic records by roll number.
HODs register using both faculty code and HOD verification code, and they can monitor faculty attendance and performance.
The backend is written in Python using SQLite.
Passwords are hashed before storage.
Access control is enforced by backend role checks, not only frontend hiding.
The database contains users, sessions, faculty codes, HOD codes, student academic records, and faculty attendance records.
The project is deployed on Render in free mode using temporary SQLite storage for demonstration.
```

## 20. Final Mental Model

Student:

```text
Register → Login → See personal dashboard
```

Faculty:

```text
Receive faculty code from admin → Register → Login → Update students by roll number
```

HOD:

```text
Receive faculty code + HOD code from admin → Register → Login → Monitor faculty
```

You:

```text
Create codes → Monitor database → Fix records → Maintain GitHub → Deploy updates
```

That is your exact role as developer and administrator of this project.
