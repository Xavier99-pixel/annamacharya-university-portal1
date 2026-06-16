const state = {
  photos: {
    student: "",
    staff: "",
  },
  user: null,
};

const views = Array.from(document.querySelectorAll(".view"));
const toast = document.getElementById("toast");
const splash = document.getElementById("splash");
const app = document.getElementById("app");

document.getElementById("enterPortal").addEventListener("click", () => {
  splash.style.transition = "opacity 520ms ease, transform 520ms ease";
  splash.style.opacity = "0";
  splash.style.transform = "scale(1.025)";
  setTimeout(() => {
    splash.classList.add("is-hidden");
    app.classList.remove("is-hidden");
    showView(state.user ? "dashboard" : "roles");
  }, 540);
});

document.querySelectorAll("[data-view]").forEach((element) => {
  element.addEventListener("click", () => showView(element.dataset.view));
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
  const payload = {
    role: "student",
    name: data.name,
    gender: data.gender,
    course: data.course,
    year: data.year,
    semester: data.semester,
    roll_number: data.roll_number,
    password: data.password,
    profile_photo: state.photos.student,
  };
  const result = await postJson("/api/register", payload);
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
  const payload = {
    role: "staff",
    name: data.name,
    gender: data.gender,
    department: data.department,
    faculty_code: data.faculty_code,
    password: data.password,
    profile_photo: state.photos.staff,
  };
  const result = await postJson("/api/register", payload);
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

document.getElementById("logoutBtn").addEventListener("click", async () => {
  await postJson("/api/logout", {});
  state.user = null;
  notify("Logged out successfully.", "success");
  showView("roles");
});

async function hydrate() {
  try {
    const response = await fetch("/api/me");
    const result = await response.json();
    if (result.authenticated) {
      state.user = result.user;
      renderDashboard(result.user);
    }
  } catch {
    notify("Could not check existing login session.", "error");
  }
}

function showView(id) {
  if (id === "dashboard" && !state.user) {
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

function handleAuthResult(result, form) {
  if (!result.ok) {
    notify(result.message || "Request failed.", "error");
    return;
  }
  state.user = result.user;
  renderDashboard(result.user);
  form.reset();
  notify(result.message || "Success.", "success");
  showView("dashboard");
}

function renderDashboard(user) {
  document.getElementById("dashName").textContent = `Welcome, ${user.name}`;
  const idLabel = user.role === "student" ? `Roll Number: ${user.roll_number}` : `Faculty Code: ${user.faculty_code}`;
  document.getElementById("dashMeta").textContent = `${titleCase(user.role)} account active · ${idLabel}`;
  const details = user.role === "student"
    ? `${user.course}, ${user.year}, ${user.semester}. Gender: ${user.gender}.`
    : `${user.course}. Gender: ${user.gender}.`;
  document.getElementById("dashProfile").textContent = details;
}

function notify(message, type = "") {
  toast.textContent = message;
  toast.className = `toast show ${type}`;
  clearTimeout(notify.timeout);
  notify.timeout = setTimeout(() => {
    toast.className = "toast";
  }, 3200);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

hydrate();
