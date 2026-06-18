const state = {
  photos: {
    student: "",
    staff: "",
  },
  user: null,
  students: [],
  faculty: [],
  notices: [],
  adminData: null,
  otpVerifiedPhone: "",
  adminUnlocked: false,
};

const views = Array.from(document.querySelectorAll(".view"));
const toast = document.getElementById("toast");
const splash = document.getElementById("splash");
const app = document.getElementById("app");
const isHod = document.getElementById("isHod");
const facultyCodeField = document.getElementById("facultyCodeField");
const hodCodeField = document.getElementById("hodCodeField");
const sendOtpBtn = document.getElementById("sendOtpBtn");
const verifyOtpBtn = document.getElementById("verifyOtpBtn");
const otpStatus = document.getElementById("otpStatus");
const adminKeyForm = document.getElementById("adminKeyForm");
const refreshAdminBtn = document.getElementById("refreshAdminBtn");
const adminDeleteUserForm = document.getElementById("adminDeleteUserForm");
const adminCodeForm = document.getElementById("adminCodeForm");
const adminRecordForm = document.getElementById("adminRecordForm");
const adminNoticeForm = document.getElementById("adminNoticeForm");
const adminDeactivateNoticeForm = document.getElementById("adminDeactivateNoticeForm");
const adminUserSearch = document.getElementById("adminUserSearch");
const adminRoleFilter = document.getElementById("adminRoleFilter");
const adminStatusFilter = document.getElementById("adminStatusFilter");
const downloadUsersCsv = document.getElementById("downloadUsersCsv");
const downloadAcademicCsv = document.getElementById("downloadAcademicCsv");
const downloadFacultyCsv = document.getElementById("downloadFacultyCsv");
const downloadNoticesCsv = document.getElementById("downloadNoticesCsv");
const downloadSqliteBackup = document.getElementById("downloadSqliteBackup");
const restoreDatabaseForm = document.getElementById("restoreDatabaseForm");
const restoreDatabaseFile = document.getElementById("restoreDatabaseFile");
const chatbotToggle = document.getElementById("chatbotToggle");
const chatbotPanel = document.getElementById("chatbotPanel");
const chatbotClose = document.getElementById("chatbotClose");
const chatbotForm = document.getElementById("chatbotForm");
const chatbotInput = document.getElementById("chatbotInput");
const chatbotMessages = document.getElementById("chatbotMessages");

document.getElementById("enterPortal").addEventListener("click", () => {
  splash.style.transition = "opacity 520ms ease, transform 520ms ease";
  splash.style.opacity = "0";
  splash.style.transform = "scale(1.025)";
  setTimeout(() => {
    revealPortal(state.user ? dashboardForRole(state.user.role) : isAdminRoute() ? "admin-monitor" : "roles");
  }, 540);
});

document.querySelectorAll("[data-view]").forEach((element) => {
  element.addEventListener("click", () => showView(element.dataset.view));
});

document.querySelectorAll(".logout-action").forEach((button) => {
  button.addEventListener("click", logout);
});

document.getElementById("logoutBtn").addEventListener("click", logout);

sendOtpBtn.addEventListener("click", requestStudentOtp);
verifyOtpBtn.addEventListener("click", verifyStudentOtp);

isHod.addEventListener("change", () => {
  syncHodRegistrationFields();
});
syncHodRegistrationFields();

document.querySelectorAll("[data-photo]").forEach((input) => {
  input.addEventListener("change", async () => {
    const role = input.dataset.photo;
    const file = input.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      notify("Please choose an image file.", "error");
      return;
    }
    if (file.size > 850_000) {
      notify("Use an image smaller than 850 KB for this local demo.", "error");
      input.value = "";
      return;
    }
    const dataUrl = await readFileAsDataUrl(file);
    state.photos[role] = dataUrl;
    document.querySelector(`[data-preview="${role}"]`).src = dataUrl;
  });
});

document.getElementById("studentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  if (data.password !== data.confirm_password) {
    notify("Passwords do not match.", "error");
    return;
  }
  const phone = cleanPhone(data.phone_number);
  if (state.otpVerifiedPhone !== phone) {
    notify("Verify phone number with OTP before creating student account.", "error");
    return;
  }
  const result = await postJson("/api/register", {
    role: "student",
    name: data.name,
    gender: data.gender,
    course: data.course,
    branch: data.branch,
    year: data.year,
    semester: data.semester,
    roll_number: data.roll_number,
    phone_number: phone,
    email: data.email,
    dob: data.dob,
    blood_group: data.blood_group,
    guardian_name: data.guardian_name,
    guardian_phone: data.guardian_phone,
    address: data.address,
    password: data.password,
    profile_photo: state.photos.student,
  });
  handleAuthResult(result, form);
});

document.getElementById("staffForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  if (data.password !== data.confirm_password) {
    notify("Passwords do not match.", "error");
    return;
  }
  const result = await postJson("/api/register", {
    role: "staff",
    is_hod: data.is_hod === "on",
    name: data.name,
    gender: data.gender,
    department: data.department,
    email: data.email,
    phone_number: data.phone_number,
    designation: data.designation,
    specialization: data.specialization,
    qualification: data.qualification,
    experience: data.experience,
    faculty_code: data.is_hod === "on" ? "" : data.faculty_code,
    hod_code: data.hod_code,
    password: data.password,
    profile_photo: state.photos.staff,
  });
  handleAuthResult(result, form);
});

document.getElementById("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  const result = await postJson("/api/login", {
    role: data.role,
    identifier: data.identifier,
    password: data.password,
  });
  handleAuthResult(result, form);
});

document.getElementById("recordForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  const result = await postJson("/api/student-record", data);
  if (!result.ok) {
    notify(result.message || "Could not update student record.", "error");
    return;
  }
  notify(result.message, "success");
  form.reset();
  await loadStudents();
});

document.getElementById("facultyAttendanceForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  const result = await postJson("/api/faculty-attendance", data);
  if (!result.ok) {
    notify(result.message || "Could not update faculty attendance.", "error");
    return;
  }
  notify(result.message, "success");
  form.reset();
  await loadFaculty();
});

document.getElementById("studentSearch").addEventListener("input", renderStudentsTable);
document.getElementById("facultySearch").addEventListener("input", renderFacultyTable);
adminKeyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadAdminOverview();
});
refreshAdminBtn.addEventListener("click", loadAdminOverview);
adminDeleteUserForm.addEventListener("submit", handleAdminDeleteUser);
adminCodeForm.addEventListener("submit", handleAdminCode);
adminRecordForm.addEventListener("submit", handleAdminRecord);
adminNoticeForm.addEventListener("submit", handleAdminNotice);
adminDeactivateNoticeForm.addEventListener("submit", handleAdminDeactivateNotice);
adminUserSearch.addEventListener("input", renderAdminUsersTable);
adminRoleFilter.addEventListener("change", renderAdminUsersTable);
adminStatusFilter.addEventListener("change", renderAdminUsersTable);
downloadUsersCsv.addEventListener("click", () => downloadAdminExport("users.csv"));
downloadAcademicCsv.addEventListener("click", () => downloadAdminExport("academic.csv"));
downloadFacultyCsv.addEventListener("click", () => downloadAdminExport("faculty.csv"));
downloadNoticesCsv.addEventListener("click", () => downloadAdminExport("notices.csv"));
downloadSqliteBackup.addEventListener("click", () => downloadAdminExport("database.sqlite3"));
restoreDatabaseForm.addEventListener("submit", handleRestoreDatabase);
chatbotToggle.addEventListener("click", toggleChatbot);
chatbotClose.addEventListener("click", closeChatbot);
chatbotForm.addEventListener("submit", handleChatbotSubmit);
document.querySelectorAll("[data-chat-prompt]").forEach((button) => {
  button.addEventListener("click", () => askChatbot(button.dataset.chatPrompt));
});
window.addEventListener("hashchange", () => {
  if (isAdminRoute()) {
    revealPortal("admin-monitor");
  }
});

async function hydrate() {
  try {
    const response = await fetch("/api/me");
    const result = await response.json();
    if (result.authenticated) {
      state.user = result.user;
    }
  } catch {
    notify("Could not check existing login session.", "error");
  }
  if (isAdminRoute()) {
    revealPortal("admin-monitor");
    return;
  }
  if (state.user) {
    await renderWorkspace(state.user);
  }
}

function revealPortal(id) {
  splash.classList.add("is-hidden");
  app.classList.remove("is-hidden");
  showView(id);
}

function isAdminRoute() {
  const path = window.location.pathname.replace(/\/$/, "");
  return path === "/admin" || window.location.hash === "#admin";
}

function showView(id) {
  if (id.endsWith("dashboard") && !state.user) {
    id = "login";
  }
  views.forEach((view) => view.classList.toggle("is-hidden", view.id !== id));
  document.querySelectorAll(".landing-only").forEach((section) => {
    section.classList.toggle("is-hidden", id !== "roles");
  });
  document.querySelectorAll(".topbar nav button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === id);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  result.status = response.status;
  return result;
}

async function handleAuthResult(result, form) {
  if (!result.ok) {
    notify(result.message || "Request failed.", "error");
    return;
  }
  state.user = result.user;
  form.reset();
  state.photos.student = "";
  state.photos.staff = "";
  isHod.checked = false;
  syncHodRegistrationFields();
  notify(result.message || "Success.", "success");
  await renderWorkspace(result.user);
}

function syncHodRegistrationFields() {
  const facultyInput = facultyCodeField.querySelector("input");
  const hodInput = hodCodeField.querySelector("input");
  const hodMode = isHod.checked;

  hodCodeField.classList.toggle("is-hidden", !hodMode);
  facultyCodeField.classList.toggle("disabled-field", hodMode);
  facultyInput.required = !hodMode;
  facultyInput.disabled = hodMode;
  hodInput.required = hodMode;

  if (hodMode) {
    facultyInput.value = "";
    hodInput.placeholder = "HOD login code, e.g. AU-HOD-CSE-2026";
  } else {
    hodInput.value = "";
    hodInput.placeholder = "Example: AU-HOD-CSE-2026";
  }
}

async function renderWorkspace(user) {
  if (user.role === "student") {
    await Promise.all([renderStudentDashboard(user), loadNotices()]);
    showView("student-dashboard");
    return;
  }
  if (user.role === "faculty") {
    renderStaffHeading(user);
    await Promise.all([loadStudents(), loadNotices()]);
    showView("faculty-dashboard");
    return;
  }
  if (user.role === "hod") {
    renderStaffHeading(user);
    await Promise.all([loadStudents(), loadFaculty(), loadNotices()]);
    showView("hod-dashboard");
  }
}

async function loadAdminOverview() {
  const key = adminKey();
  if (!key) {
    notify("Enter admin key to open live monitor.", "error");
    return;
  }
  const response = await fetch(`/api/admin/overview?key=${encodeURIComponent(key)}`);
  const result = await response.json();
  if (!result.ok) {
    notify(result.message || "Could not load admin monitor.", "error");
    return;
  }
  renderAdminOverview(result);
  notify("Live database monitor refreshed.", "success");
}

function renderAdminOverview(result) {
  setAdminUnlocked(true);
  state.adminData = result;
  const counts = result.counts || {};
  document.getElementById("adminDbPath").textContent = `Active database: ${result.database_path}`;
  document.getElementById("adminCounts").innerHTML = [
    ["Students", counts.student || 0],
    ["Faculty", counts.faculty || 0],
    ["HODs", counts.hod || 0],
    ["Total", result.total_users || 0],
  ].map(([label, value]) => `<div><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");

  renderAdminMetrics(result);
  renderAdminUsersTable();

  document.getElementById("adminRecordsTable").innerHTML = (result.student_records || []).map((record) => `
    <tr>
      <td>${escapeHtml(record.roll_number)}</td>
      <td>${escapeHtml(record.name)}</td>
      <td>${escapeHtml([record.course, record.branch, record.year, record.semester].filter(Boolean).join(" · "))}</td>
      <td>${escapeHtml(record.attendance || 0)}%</td>
      <td>${escapeHtml(record.internal_marks || 0)}</td>
      <td>${escapeHtml(record.external_marks || 0)}</td>
      <td>${escapeHtml(record.marks || 0)}</td>
      <td>${escapeHtml(record.cgpa || 0)}</td>
      <td>${escapeHtml(record.performance || "Not updated")}</td>
    </tr>
  `).join("") || emptyRow(9, "No student academic records found.");

  document.getElementById("adminCodesTable").innerHTML = (result.codes || []).map((code) => `
    <tr>
      <td>${escapeHtml(code.code_type === "hod" ? "HOD" : "Faculty")}</td>
      <td>${escapeHtml(code.code)}</td>
      <td>${escapeHtml(code.label)}</td>
      <td><span class="${code.active ? "status-pill active" : "status-pill inactive"}">${code.active ? "Active" : "Inactive"}</span></td>
      <td>${escapeHtml(formatDate(code.created_at))}</td>
    </tr>
  `).join("") || emptyRow(5, "No faculty or HOD codes found.");

  renderAdminNotices(result.notices || []);
}

function renderAdminMetrics(result) {
  const metrics = result.metrics || {};
  document.getElementById("adminMetrics").innerHTML = [
    ["Active Students", metrics.active_students || 0],
    ["Phone Verified", metrics.verified_students || 0],
    ["Joined Today", metrics.today_registrations || 0],
    ["Faculty Codes", metrics.active_faculty_codes || 0],
    ["HOD Codes", metrics.active_hod_codes || 0],
    ["Open Notices", metrics.open_notices || 0],
  ].map(([label, value]) => `<div><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");

  document.getElementById("adminDistribution").innerHTML = (result.course_distribution || []).map((item) => `
    <div>
      <span>${escapeHtml([item.course, item.branch].filter(Boolean).join(" · "))}</span>
      <strong>${escapeHtml(item.total)}</strong>
    </div>
  `).join("") || "<p class=\"admin-note\">No course distribution data yet.</p>";
}

function renderAdminUsersTable() {
  const result = state.adminData || {};
  const query = adminUserSearch.value.trim().toLowerCase();
  const role = adminRoleFilter.value;
  const status = adminStatusFilter.value;
  const users = (result.recent_users || []).filter((user) => {
    const matchesRole = role === "all" || user.role === role;
    const matchesStatus = status === "all"
      || (status === "active" && (user.status || "active") === "active")
      || (status === "verified" && user.phone_verified);
    const haystack = searchable(user);
    return matchesRole && matchesStatus && (!query || haystack.includes(query));
  });
  document.getElementById("adminUsersTable").innerHTML = users.map((user) => {
    const loginId = user.roll_number || user.faculty_code || user.hod_code || "";
    const course = [user.course, user.branch, user.year, user.semester].filter(Boolean).join(" · ");
    return `
      <tr>
        <td>${escapeHtml(user.id)}</td>
        <td>${escapeHtml(roleLabel(user.role))}</td>
        <td>${escapeHtml(user.name)}</td>
        <td>${escapeHtml(loginId)}</td>
        <td>${escapeHtml(user.phone_number || "-")}${user.phone_verified ? " · verified" : ""}</td>
        <td>${escapeHtml(user.email || "-")}</td>
        <td>${escapeHtml(course || "-")}</td>
        <td><span class="status-pill active">${escapeHtml(user.status || "active")}</span></td>
        <td>${escapeHtml(formatDate(user.created_at))}</td>
      </tr>
    `;
  }).join("") || emptyRow(9, "No users match the current filters.");
}

function renderAdminNotices(notices) {
  document.getElementById("adminNoticesTable").innerHTML = notices.map((notice) => `
    <tr>
      <td>${escapeHtml(notice.id)}</td>
      <td><span class="notice-badge ${escapeHtml(notice.type)}">${escapeHtml(notice.type)}</span></td>
      <td>${escapeHtml(notice.target_role || "all")}</td>
      <td>${escapeHtml(notice.title)}</td>
      <td><span class="${notice.active ? "status-pill active" : "status-pill inactive"}">${notice.active ? "Active" : "Inactive"}</span></td>
      <td>${escapeHtml(formatDate(notice.created_at))}</td>
    </tr>
  `).join("") || emptyRow(6, "No notices published yet.");
}

function setAdminUnlocked(unlocked) {
  state.adminUnlocked = unlocked;
  document.querySelectorAll(".admin-secure").forEach((section) => {
    section.classList.toggle("is-hidden", !unlocked);
  });
}

async function handleAdminDeleteUser(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const result = await postJson("/api/admin/action", {
    admin_key: adminKey(),
    action: "delete_user",
    user_id: data.user_id,
  });
  await handleAdminActionResult(result, event.currentTarget);
}

async function handleAdminCode(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const result = await postJson("/api/admin/action", {
    admin_key: adminKey(),
    action: data.code_action === "deactivate" ? "deactivate_code" : "create_code",
    code_type: data.code_type,
    code: data.code,
    label: data.label,
  });
  await handleAdminActionResult(result, event.currentTarget);
}

async function handleAdminRecord(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const result = await postJson("/api/admin/action", {
    admin_key: adminKey(),
    action: "update_student_record",
    roll_number: data.roll_number,
    attendance: data.attendance,
    internal_marks: data.internal_marks,
    external_marks: data.external_marks,
    cgpa: data.cgpa,
    performance: data.performance,
  });
  await handleAdminActionResult(result, event.currentTarget);
}

async function handleAdminNotice(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const result = await postJson("/api/admin/action", {
    admin_key: adminKey(),
    action: "create_notice",
    title: data.title,
    message: data.message,
    type: data.type,
    target_role: data.target_role,
  });
  await handleAdminActionResult(result, event.currentTarget);
}

async function handleAdminDeactivateNotice(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const result = await postJson("/api/admin/action", {
    admin_key: adminKey(),
    action: "deactivate_notice",
    notice_id: data.notice_id,
  });
  await handleAdminActionResult(result, event.currentTarget);
}

async function handleAdminActionResult(result, form) {
  if (!result.ok) {
    notify(result.message || "Admin action failed.", "error");
    return;
  }
  notify(result.message || "Admin action completed.", "success");
  form.reset();
  await loadAdminOverview();
}

function downloadAdminExport(filename) {
  const key = adminKey();
  if (!key) {
    notify("Enter admin key before downloading live data.", "error");
    return;
  }
  window.location.href = `/api/admin/export/${filename}?key=${encodeURIComponent(key)}`;
  notify("Preparing secure download from the live database.", "success");
}

async function handleRestoreDatabase(event) {
  event.preventDefault();
  const key = adminKey();
  const [file] = restoreDatabaseFile.files;
  if (!key) {
    notify("Enter admin key before restoring live data.", "error");
    return;
  }
  if (!file) {
    notify("Choose a SQLite backup file first.", "error");
    return;
  }
  const confirmed = window.confirm("Restore this backup to the live database? This replaces the current live data.");
  if (!confirmed) return;

  const response = await fetch(`/api/admin/restore/database.sqlite3?key=${encodeURIComponent(key)}`, {
    method: "POST",
    headers: { "Content-Type": "application/vnd.sqlite3" },
    body: file,
  });
  const result = await response.json();
  if (!result.ok) {
    notify(result.message || "Could not restore database.", "error");
    return;
  }
  restoreDatabaseForm.reset();
  notify(result.message, "success");
  await loadAdminOverview();
}

function adminKey() {
  return document.getElementById("adminKey").value.trim();
}

async function renderStudentDashboard(user) {
  document.getElementById("dashName").textContent = `Welcome, ${user.name}`;
  document.getElementById("dashMeta").textContent = `Roll Number: ${user.roll_number} · ${user.course} ${user.branch || ""}`;
  document.getElementById("dashProfile").textContent = `${user.course}, ${user.branch}, ${user.year}, ${user.semester}. Gender: ${user.gender}.`;
  document.getElementById("dashPhoto").src = user.profile_photo || "/images/au1.jpeg";
  renderSavedDetails(user);

  const response = await fetch("/api/me");
  const result = await response.json();
  const record = result.user?.academic_record || {};
  renderMetricList("studentAcademicRecord", [
    ["Attendance", `${record.attendance || 0}%`],
    ["Internal Marks", `${record.internal_marks || 0}/100`],
    ["External Marks", `${record.external_marks || 0}/100`],
    ["Total Marks", `${record.marks || 0}/100`],
    ["CGPA", `${record.cgpa || 0}/10`],
    ["Performance", record.performance || "Not updated"],
  ]);
}

function renderStaffHeading(user) {
  document.getElementById("facultyName").textContent = `Welcome, ${user.name}`;
  document.getElementById("hodName").textContent = `Welcome, ${user.name}`;
}

async function loadStudents() {
  const response = await fetch("/api/students");
  const result = await response.json();
  if (!result.ok) {
    notify(result.message || "Could not load students.", "error");
    return;
  }
  state.students = result.students || [];
  renderStudentsTable();
  renderHodStudentsTable();
}

async function loadFaculty() {
  const response = await fetch("/api/faculty");
  const result = await response.json();
  if (!result.ok) {
    notify(result.message || "Could not load faculty.", "error");
    return;
  }
  state.faculty = result.faculty || [];
  renderFacultyTable();
}

async function loadNotices() {
  const response = await fetch("/api/notices");
  const result = await response.json();
  if (!result.ok) {
    state.notices = [];
    return;
  }
  state.notices = result.notices || [];
  renderRoleNotices();
}

function renderRoleNotices() {
  const html = state.notices.map((notice) => `
    <article class="notice-item ${escapeHtml(notice.type)}">
      <div>
        <strong>${escapeHtml(notice.title)}</strong>
        <span>${escapeHtml(formatDate(notice.created_at))} · ${escapeHtml(notice.type)}</span>
      </div>
      <p>${escapeHtml(notice.message)}</p>
    </article>
  `).join("") || "<p class=\"admin-note\">No active notices for your role.</p>";
  ["studentNotices", "facultyNotices", "hodNotices"].forEach((id) => {
    const node = document.getElementById(id);
    if (node) node.innerHTML = html;
  });
}

function renderStudentsTable() {
  const query = document.getElementById("studentSearch")?.value?.toLowerCase() || "";
  const students = state.students.filter((student) => searchable(student).includes(query));
  document.getElementById("studentsTable").innerHTML = studentRows(students);
}

function renderHodStudentsTable() {
  const table = document.getElementById("hodStudentsTable");
  if (table) table.innerHTML = studentRows(state.students);
}

function renderFacultyTable() {
  const query = document.getElementById("facultySearch")?.value?.toLowerCase() || "";
  const faculty = state.faculty.filter((member) => searchable(member).includes(query));
  document.getElementById("facultyTable").innerHTML = faculty.map((member) => `
    <tr>
      <td>${escapeHtml(member.faculty_code)}</td>
      <td>${escapeHtml(member.name)}</td>
      <td>${escapeHtml(member.course || "")}</td>
      <td>${escapeHtml(member.attendance || 0)}%</td>
      <td>${escapeHtml(member.performance || "Not updated")}</td>
    </tr>
  `).join("") || emptyRow(5, "No faculty records found.");
}

function studentRows(students) {
  return students.map((student) => `
    <tr>
      <td>${escapeHtml(student.roll_number)}</td>
      <td>${escapeHtml(student.name)}</td>
      <td>${escapeHtml([student.course, student.branch, student.year, student.semester].filter(Boolean).join(" · "))}</td>
      <td>${escapeHtml(student.attendance || 0)}%</td>
      <td>${escapeHtml(student.internal_marks || 0)}</td>
      <td>${escapeHtml(student.external_marks || 0)}</td>
      <td>${escapeHtml(student.marks || 0)}</td>
      <td>${escapeHtml(student.cgpa || 0)}</td>
      <td>${escapeHtml(student.performance || "Not updated")}</td>
    </tr>
  `).join("") || emptyRow(9, "No student records found.");
}

function emptyRow(columns, message) {
  return `<tr><td colspan="${columns}">${escapeHtml(message)}</td></tr>`;
}

async function logout() {
  await postJson("/api/logout", {});
  state.user = null;
  notify("Logged out successfully.", "success");
  showView("roles");
}

function dashboardForRole(role) {
  if (role === "student") return "student-dashboard";
  if (role === "faculty") return "faculty-dashboard";
  if (role === "hod") return "hod-dashboard";
  return "roles";
}

function renderSavedDetails(user) {
  const rows = [
    ["Role", roleLabel(user.role)],
    ["Full Name", user.name],
    [user.role === "student" ? "Roll Number" : "Faculty Code", user.role === "student" ? user.roll_number : user.faculty_code],
    [user.role === "student" ? "Course" : "Department", user.course],
    ["Gender", user.gender],
  ];

  if (user.role === "student") {
    rows.splice(
      4,
      0,
      ["Branch", user.branch],
      ["Year", user.year],
      ["Semester", user.semester],
      ["Phone", user.phone_number],
      ["Email", user.email],
      ["DOB", user.dob],
      ["Blood Group", user.blood_group],
      ["Guardian", user.guardian_name],
      ["Guardian Phone", user.guardian_phone],
      ["Status", user.status]
    );
  } else {
    rows.splice(
      4,
      0,
      ["Email", user.email],
      ["Phone", user.phone_number],
      ["Designation", user.designation],
      ["Specialization", user.specialization],
      ["Qualification", user.qualification],
      ["Experience", user.experience],
      ["Status", user.status]
    );
  }

  rows.push(["Registered", formatDate(user.created_at)]);
  document.getElementById("dashDetails").innerHTML = rows
    .filter(([, value]) => value)
    .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

function renderMetricList(id, rows) {
  document.getElementById(id).innerHTML = rows
    .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

function notify(message, type = "") {
  toast.textContent = message;
  toast.className = `toast show ${type}`;
  clearTimeout(notify.timeout);
  notify.timeout = setTimeout(() => {
    toast.className = "toast";
  }, 3200);
}

async function requestStudentOtp() {
  const phone = cleanPhone(document.getElementById("studentPhone").value);
  if (!validPhone(phone)) {
    notify("Enter a valid 10 digit mobile number.", "error");
    return;
  }
  const result = await postJson("/api/request-otp", { phone_number: phone });
  if (!result.ok) {
    notify(result.message || "Could not generate OTP.", "error");
    return;
  }
  otpStatus.textContent = `Demo OTP: ${result.demo_otp}. Enter it below and verify.`;
  otpStatus.className = "otp-demo";
  notify("OTP generated for demo verification.", "success");
}

async function verifyStudentOtp() {
  const phone = cleanPhone(document.getElementById("studentPhone").value);
  const otp = document.getElementById("studentOtp").value.trim();
  const result = await postJson("/api/verify-otp", { phone_number: phone, otp_code: otp });
  if (!result.ok) {
    state.otpVerifiedPhone = "";
    otpStatus.textContent = result.message || "OTP verification failed.";
    otpStatus.className = "otp-error";
    notify(otpStatus.textContent, "error");
    return;
  }
  state.otpVerifiedPhone = phone;
  otpStatus.textContent = "Phone number verified. You can create the student account.";
  otpStatus.className = "otp-success";
  notify("Phone verified successfully.", "success");
}

function cleanPhone(value) {
  return String(value || "").replace(/\D/g, "");
}

function validPhone(phone) {
  return /^[6-9]\d{9}$/.test(phone);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function roleLabel(role) {
  if (role === "hod") return "Head of Department";
  if (role === "faculty") return "Faculty";
  return "Student";
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function searchable(item) {
  return Object.values(item).join(" ").toLowerCase();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toggleChatbot() {
  const open = chatbotPanel.classList.toggle("is-hidden");
  chatbotToggle.setAttribute("aria-expanded", String(!open));
  if (!open) chatbotInput.focus();
}

function closeChatbot() {
  chatbotPanel.classList.add("is-hidden");
  chatbotToggle.setAttribute("aria-expanded", "false");
}

function handleChatbotSubmit(event) {
  event.preventDefault();
  askChatbot(chatbotInput.value);
  chatbotInput.value = "";
}

function askChatbot(question) {
  const cleanQuestion = String(question || "").trim();
  if (!cleanQuestion) return;
  appendChatMessage(cleanQuestion, "user-message");
  appendChatMessage(answerChatbot(cleanQuestion), "bot-message");
}

function appendChatMessage(message, className) {
  const row = document.createElement("div");
  row.className = className;
  row.textContent = message;
  chatbotMessages.appendChild(row);
  chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function answerChatbot(question) {
  const q = question.toLowerCase();
  if (q.includes("student") || q.includes("register") || q.includes("roll")) {
    return "Student flow: click Student Registration, add profile/photo/course/branch/year/semester/roll number plus optional email, DOB, blood group and guardian details, verify phone OTP, create password, then login with roll number.";
  }
  if (q.includes("faculty") || q.includes("marks") || q.includes("attendance")) {
    return "Faculty flow: register with a university faculty code, login as Faculty with that code, then use the Faculty Workspace to update student attendance, internal marks, external marks, CGPA and performance by roll number.";
  }
  if (q.includes("hod") || q.includes("head")) {
    return "HOD flow: check Register as HOD, use only the HOD code, create password, then login as HOD using the HOD code. HODs can monitor faculty attendance and student academic records.";
  }
  if (q.includes("admin") || q.includes("monitor") || q.includes("database")) {
    return "Admin flow: open /admin, enter ADMIN_KEY, load live users, filter users by role/status/search, publish notices, manage codes, update records, export CSV reports, and download/restore SQLite backups.";
  }
  if (q.includes("datagrip") || q.includes("sqlite")) {
    return "DataGrip reads only the SQLite file you open. For live Render registrations, open /admin, download SQLite Backup, then open it in DataGrip. To put data back after redeploy, upload the same backup with Restore Live Database.";
  }
  if (q.includes("notice") || q.includes("notification") || q.includes("announcement")) {
    return "Notice module: admin opens /admin, publishes a notice with type info/warning/urgent/event and target all/student/faculty/HOD. Each logged-in role sees only relevant notices in its dashboard.";
  }
  if (q.includes("report") || q.includes("csv") || q.includes("export")) {
    return "Reports: admin can export Users CSV, Academic CSV, Faculty CSV, Notices CSV, or full SQLite Backup. CSV is for review sheets; SQLite backup is for DataGrip and restore.";
  }
  if (q.includes("profile") || q.includes("guardian") || q.includes("blood")) {
    return "Profiles now store richer details: student email, DOB, blood group, guardian contact, address and status; faculty profiles include designation, specialization, qualification and experience.";
  }
  if (q.includes("architecture") || q.includes("backend") || q.includes("frontend") || q.includes("api")) {
    return "Architecture: HTML/CSS/JavaScript frontend sends JSON with fetch() to Python app.py API routes. Python validates roles, hashes passwords, manages sessions, and reads/writes SQLite tables.";
  }
  if (q.includes("otp") || q.includes("phone")) {
    return "OTP flow: student enters phone, clicks Send OTP, backend stores a 6 digit demo OTP, student verifies it, then registration is allowed. A real production app would connect an SMS provider.";
  }
  if (q.includes("deploy") || q.includes("render")) {
    return "Deployment: push latest GitHub main branch, then deploy on Render. Free Render uses temporary SQLite at /tmp, so data can reset on redeploy. For permanent data, use a persistent disk or cloud database.";
  }
  if (q.includes("security") || q.includes("password") || q.includes("jwt")) {
    return "Security: this portal uses PBKDF2-HMAC password hashing and HttpOnly session cookies. It does not use JWT currently. Admin actions require ADMIN_KEY.";
  }
  return "I can help with student registration, faculty/HOD login, notices, reports, admin filters, DataGrip backup/restore, OTP, deployment, richer profiles, and the portal architecture. Try asking: How do reports work?";
}

hydrate();
