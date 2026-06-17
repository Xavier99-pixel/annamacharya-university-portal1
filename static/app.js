const state = {
  photos: {
    student: "",
    staff: "",
  },
  user: null,
  students: [],
  faculty: [],
  otpVerifiedPhone: "",
};

const views = Array.from(document.querySelectorAll(".view"));
const toast = document.getElementById("toast");
const splash = document.getElementById("splash");
const app = document.getElementById("app");
const isHod = document.getElementById("isHod");
const hodCodeField = document.getElementById("hodCodeField");
const sendOtpBtn = document.getElementById("sendOtpBtn");
const verifyOtpBtn = document.getElementById("verifyOtpBtn");
const otpStatus = document.getElementById("otpStatus");

document.getElementById("enterPortal").addEventListener("click", () => {
  splash.style.transition = "opacity 520ms ease, transform 520ms ease";
  splash.style.opacity = "0";
  splash.style.transform = "scale(1.025)";
  setTimeout(() => {
    splash.classList.add("is-hidden");
    app.classList.remove("is-hidden");
    showView(state.user ? dashboardForRole(state.user.role) : "roles");
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
  hodCodeField.classList.toggle("is-hidden", !isHod.checked);
  hodCodeField.querySelector("input").required = isHod.checked;
});

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
    faculty_code: data.faculty_code,
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

async function hydrate() {
  try {
    const response = await fetch("/api/me");
    const result = await response.json();
    if (result.authenticated) {
      state.user = result.user;
      await renderWorkspace(result.user);
    }
  } catch {
    notify("Could not check existing login session.", "error");
  }
}

function showView(id) {
  if (id.endsWith("dashboard") && !state.user) {
    id = "login";
  }
  views.forEach((view) => view.classList.toggle("is-hidden", view.id !== id));
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
  hodCodeField.classList.add("is-hidden");
  notify(result.message || "Success.", "success");
  await renderWorkspace(result.user);
}

async function renderWorkspace(user) {
  if (user.role === "student") {
    await renderStudentDashboard(user);
    showView("student-dashboard");
    return;
  }
  if (user.role === "faculty") {
    renderStaffHeading(user);
    await loadStudents();
    showView("faculty-dashboard");
    return;
  }
  if (user.role === "hod") {
    renderStaffHeading(user);
    await Promise.all([loadStudents(), loadFaculty()]);
    showView("hod-dashboard");
  }
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
    rows.splice(4, 0, ["Branch", user.branch], ["Year", user.year], ["Semester", user.semester], ["Phone", user.phone_number]);
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

hydrate();
