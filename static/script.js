// SAMPLE INITIAL DATA
const SAMPLE_OPPORTUNITIES = [
  {
    id: "sample_1",
    title: "Software Engineering Internship 2025",
    category: "Internships",
    description: "3-month remote software engineering internship for undergraduate computer science students. Gain hands-on experience building scalable web applications with industry mentors.",
    postedBy: "chaman_cs",
    deadline: "2025-11-30",
    link: "https://example.com/apply/swe-intern"
  },
  {
    id: "sample_2",
    title: "Global Undergraduate STEM Scholarship",
    category: "Scholarships",
    description: "Financial grant providing assistance to meritorious students pursuing undergraduate degrees in Science, Technology, Engineering, or Mathematics.",
    postedBy: "ananya_m",
    deadline: "2025-12-15",
    link: "https://example.com/scholarships/stem"
  },
  {
    id: "sample_3",
    title: "National Student Innovation Hackathon",
    category: "Hackathons",
    description: "48-hour online hackathon to solve real-world sustainability and technology challenges. Open to student teams of 2 to 4 members. Prizes worth $5,000.",
    postedBy: "dev_club",
    deadline: "2025-10-25",
    link: "https://example.com/hackathons/nsih2025"
  },
  {
    id: "sample_4",
    title: "Web Development Certification Course",
    category: "Courses",
    description: "Free comprehensive self-paced course covering modern HTML, CSS, JavaScript, and Web Performance principles with hands-on projects.",
    postedBy: "code_mentor",
    deadline: "2025-10-31",
    link: "https://example.com/courses/web-dev"
  },
  {
    id: "sample_5",
    title: "Junior Data Analyst Competition",
    category: "Competitions",
    description: "Analyze real-world dataset samples and create insightful data visualizations. Certificates of merit for top 10 student finalists.",
    postedBy: "data_hub",
    deadline: "2025-11-10",
    link: "https://example.com/competitions/data-analyst"
  },
  {
    id: "sample_6",
    title: "Junior Frontend Developer (Entry Level)",
    category: "Jobs",
    description: "Full-time junior frontend developer role for recent graduates. Build clean, accessible user interfaces using HTML, CSS, and vanilla JS.",
    postedBy: "hr_team",
    deadline: "2025-11-20",
    link: "https://example.com/jobs/junior-frontend"
  }
];

const SAMPLE_USERS = [
  { name: "Chaman Kumar", username: "chaman_cs", password: "123" }
];

// LOCAL STORAGE HELPERS
function getStoredOpportunities() {
  const data = localStorage.getItem("opportunities");
  if (!data) {
    localStorage.setItem("opportunities", JSON.stringify(SAMPLE_OPPORTUNITIES));
    return SAMPLE_OPPORTUNITIES;
  }
  return JSON.parse(data);
}

function saveOpportunity(opp) {
  const opps = getStoredOpportunities();
  opps.unshift(opp);
  localStorage.setItem("opportunities", JSON.stringify(opps));
}

function getStoredUsers() {
  const data = localStorage.getItem("users");
  if (!data) {
    localStorage.setItem("users", JSON.stringify(SAMPLE_USERS));
    return SAMPLE_USERS;
  }
  return JSON.parse(data);
}

function saveUser(user) {
  const users = getStoredUsers();
  users.push(user);
  localStorage.setItem("users", JSON.stringify(users));
}

function getCurrentUser() {
  const data = localStorage.getItem("currentUser");
  return data ? JSON.parse(data) : null;
}

function setCurrentUser(user) {
  if (user) {
    localStorage.setItem("currentUser", JSON.stringify(user));
  } else {
    localStorage.removeItem("currentUser");
  }
}

// DOM ELEMENTS
const navToggle = document.getElementById("navToggle");
const navMenu = document.getElementById("navMenu");
const authContainer = document.getElementById("authContainer");
const openAuthBtn = document.getElementById("openAuthBtn");
const postHeroBtn = document.getElementById("postHeroBtn");

// Filter Elements
const searchInput = document.getElementById("searchInput");
const categorySelect = document.getElementById("categorySelect");
const opportunitiesGrid = document.getElementById("opportunitiesGrid");
const noResultsMsg = document.getElementById("noResultsMsg");

// Auth Modal Elements
const authModal = document.getElementById("authModal");
const closeAuthModalBtn = document.getElementById("closeAuthModalBtn");
const tabLoginBtn = document.getElementById("tabLoginBtn");
const tabSignupBtn = document.getElementById("tabSignupBtn");
const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const loginAlert = document.getElementById("loginAlert");
const signupAlert = document.getElementById("signupAlert");

// Post Modal Elements
const postModal = document.getElementById("postModal");
const closePostModalBtn = document.getElementById("closePostModalBtn");
const postForm = document.getElementById("postForm");
const postAlert = document.getElementById("postAlert");

// View Modal Elements
const viewModal = document.getElementById("viewModal");
const closeViewModalBtn = document.getElementById("closeViewModalBtn");
const viewTitle = document.getElementById("viewTitle");
const viewCategory = document.getElementById("viewCategory");
const viewPostedBy = document.getElementById("viewPostedBy");
const viewDeadline = document.getElementById("viewDeadline");
const viewDescription = document.getElementById("viewDescription");
const viewLink = document.getElementById("viewLink");

// INITIALIZATION
document.addEventListener("DOMContentLoaded", () => {
  renderAuthUI();
  renderOpportunities();
  setupEventListeners();
});

// UI RENDERING FUNCTIONS
function renderAuthUI() {
  const user = getCurrentUser();
  authContainer.innerHTML = "";

  if (user) {
    const userTag = document.createElement("span");
    userTag.className = "user-tag";
    userTag.textContent = `@${user.username}`;

    const logoutBtn = document.createElement("button");
    logoutBtn.className = "btn btn-secondary btn-sm";
    logoutBtn.textContent = "Logout";
    logoutBtn.addEventListener("click", handleLogout);

    authContainer.appendChild(userTag);
    authContainer.appendChild(logoutBtn);
  } else {
    const loginBtn = document.createElement("button");
    loginBtn.className = "btn btn-outline";
    loginBtn.textContent = "Login / Sign Up";
    loginBtn.addEventListener("click", () => openModal(authModal));

    authContainer.appendChild(loginBtn);
  }
}

function renderOpportunities() {
  const opportunities = getStoredOpportunities();
  const searchTerm = searchInput.value.trim().toLowerCase();
  const selectedCategory = categorySelect.value;

  const filtered = opportunities.filter((opp) => {
    const matchesSearch =
      opp.title.toLowerCase().includes(searchTerm) ||
      opp.description.toLowerCase().includes(searchTerm) ||
      opp.postedBy.toLowerCase().includes(searchTerm) ||
      opp.category.toLowerCase().includes(searchTerm);

    const matchesCategory =
      selectedCategory === "All" || opp.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  opportunitiesGrid.innerHTML = "";

  if (filtered.length === 0) {
    noResultsMsg.classList.remove("hidden");
  } else {
    noResultsMsg.classList.add("hidden");
    filtered.forEach((opp) => {
      const card = createOpportunityCard(opp);
      opportunitiesGrid.appendChild(card);
    });
  }
}

function createOpportunityCard(opp) {
  const card = document.createElement("div");
  card.className = "card";

  card.innerHTML = `
    <div class="card-top">
      <div class="card-header-flex">
        <span class="badge">${escapeHTML(opp.category)}</span>
        <span class="posted-by">Posted by: @${escapeHTML(opp.postedBy)}</span>
      </div>
      <h3 class="card-title">${escapeHTML(opp.title)}</h3>
      <p class="card-description">${escapeHTML(opp.description)}</p>
    </div>
    <div>
      <p class="card-deadline"><strong>Deadline:</strong> ${escapeHTML(opp.deadline)}</p>
      <button class="btn btn-outline card-btn view-btn">View Opportunity</button>
    </div>
  `;

  const viewBtn = card.querySelector(".view-btn");
  viewBtn.addEventListener("click", () => openViewModal(opp));

  return card;
}

// EVENT LISTENERS SETUP
function setupEventListeners() {
  // Mobile Nav Toggle
  navToggle.addEventListener("click", () => {
    navMenu.classList.toggle("open");
  });

  // Search & Filter Events
  searchInput.addEventListener("input", renderOpportunities);
  categorySelect.addEventListener("change", renderOpportunities);

  // Hero Buttons
  postHeroBtn.addEventListener("click", handlePostButtonClick);

  // Auth Tabs Toggle
  tabLoginBtn.addEventListener("click", () => switchAuthTab("login"));
  tabSignupBtn.addEventListener("click", () => switchAuthTab("signup"));

  // Form Submissions
  loginForm.addEventListener("submit", handleLoginSubmit);
  signupForm.addEventListener("submit", handleSignupSubmit);
  postForm.addEventListener("submit", handlePostSubmit);

  // Close Modal Buttons
  closeAuthModalBtn.addEventListener("click", () => closeModal(authModal));
  closePostModalBtn.addEventListener("click", () => closeModal(postModal));
  closeViewModalBtn.addEventListener("click", () => closeModal(viewModal));

  // Backdrop click to close modals
  [authModal, postModal, viewModal].forEach((modal) => {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        closeModal(modal);
      }
    });
  });
}

// HANDLERS
function handlePostButtonClick() {
  const currentUser = getCurrentUser();
  if (currentUser) {
    clearAlert(postAlert);
    postForm.reset();
    openModal(postModal);
  } else {
    switchAuthTab("login");
    showAlert(loginAlert, "Please log in or sign up to post an opportunity.", "error");
    openModal(authModal);
  }
}

function handleLoginSubmit(e) {
  e.preventDefault();
  clearAlert(loginAlert);

  const usernameInput = document.getElementById("loginUsername").value.trim();
  const passwordInput = document.getElementById("loginPassword").value.trim();

  const users = getStoredUsers();
  const foundUser = users.find(
    (u) => u.username.toLowerCase() === usernameInput.toLowerCase() && u.password === passwordInput
  );

  if (foundUser) {
    setCurrentUser(foundUser);
    renderAuthUI();
    closeModal(authModal);
    loginForm.reset();
  } else {
    showAlert(loginAlert, "Invalid username or password.", "error");
  }
}

function handleSignupSubmit(e) {
  e.preventDefault();
  clearAlert(signupAlert);

  const name = document.getElementById("signupName").value.trim();
  const username = document.getElementById("signupUsername").value.trim().replace(/^@/, "");
  const password = document.getElementById("signupPassword").value.trim();

  if (!name || !username || !password) {
    showAlert(signupAlert, "Please fill out all fields.", "error");
    return;
  }

  const users = getStoredUsers();
  const exists = users.some((u) => u.username.toLowerCase() === username.toLowerCase());

  if (exists) {
    showAlert(signupAlert, "Username is already taken. Please choose another.", "error");
    return;
  }

  const newUser = { name, username, password };
  saveUser(newUser);
  setCurrentUser(newUser);

  renderAuthUI();
  closeModal(authModal);
  signupForm.reset();
}

function handleLogout() {
  setCurrentUser(null);
  renderAuthUI();
}

function handlePostSubmit(e) {
  e.preventDefault();
  clearAlert(postAlert);

  const currentUser = getCurrentUser();
  if (!currentUser) {
    showAlert(postAlert, "Session expired. Please log in again.", "error");
    return;
  }

  const title = document.getElementById("postTitle").value.trim();
  const category = document.getElementById("postCategory").value;
  const description = document.getElementById("postDescription").value.trim();
  const deadline = document.getElementById("postDeadline").value;
  const link = document.getElementById("postLink").value.trim();

  if (!title || !category || !description || !deadline || !link) {
    showAlert(postAlert, "Please fill in all required fields.", "error");
    return;
  }

  const newOpp = {
    id: Date.now().toString(),
    title,
    category,
    description,
    deadline,
    link,
    postedBy: currentUser.username
  };

  saveOpportunity(newOpp);
  renderOpportunities();
  closeModal(postModal);
  postForm.reset();
}

function openViewModal(opp) {
  viewTitle.textContent = opp.title;
  viewCategory.textContent = opp.category;
  viewPostedBy.textContent = `Posted by: @${opp.postedBy}`;
  viewDeadline.textContent = opp.deadline;
  viewDescription.textContent = opp.description;
  viewLink.href = opp.link;

  openModal(viewModal);
}

// MODAL & ALERT UTILITIES
function openModal(modal) {
  modal.classList.remove("hidden");
}

function closeModal(modal) {
  modal.classList.add("hidden");
}

function switchAuthTab(tab) {
  clearAlert(loginAlert);
  clearAlert(signupAlert);

  if (tab === "login") {
    tabLoginBtn.classList.add("active");
    tabSignupBtn.classList.remove("active");
    loginForm.classList.remove("hidden");
    signupForm.classList.add("hidden");
  } else {
    tabSignupBtn.classList.add("active");
    tabLoginBtn.classList.remove("active");
    signupForm.classList.remove("hidden");
    loginForm.classList.add("hidden");
  }
}

function showAlert(alertEl, message, type) {
  alertEl.textContent = message;
  alertEl.className = `alert alert-${type}`;
  alertEl.classList.remove("hidden");
}

function clearAlert(alertEl) {
  alertEl.textContent = "";
  alertEl.className = "alert hidden";
}

function escapeHTML(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
