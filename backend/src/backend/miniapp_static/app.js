const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const initData = tg?.initData || "";

const ROLE_LABELS = { manager: "Менеджер", teamlead: "Тимлид", admin: "Админ", owner: "Владелец" };
const STATUS_LABELS = { active: "Активен", blocked: "Заблокирован" };
const REQUEST_STATUS_LABELS = { pending: "Ожидает", approved: "Подтверждено", rejected: "Отклонено" };
const ACTION_LABELS = { create: "Создание", update: "Правка", delete: "Удаление" };

const TABS = {
  manager: [
    { id: "stats", label: "Статистика", icon: "📊" },
    { id: "deposits", label: "Депозиты", icon: "💰" },
  ],
  teamlead: [
    { id: "team", label: "Команда", icon: "👥" },
    { id: "deposits", label: "Депозиты", icon: "💰" },
    { id: "requests", label: "Заявки", icon: "✅" },
    { id: "more", label: "Ещё", icon: "⋯" },
  ],
  admin: [
    { id: "company", label: "Компания", icon: "🏢" },
    { id: "teams", label: "Команды", icon: "👥" },
    { id: "people", label: "Люди", icon: "🧑" },
    { id: "requests", label: "Заявки", icon: "✅" },
    { id: "more", label: "Ещё", icon: "⋯" },
  ],
  owner: [{ id: "company", label: "Компания", icon: "🏢" }],
};

const state = {
  me: null,
  teams: [],
  users: [],
  activeTab: null,
  loaded: new Set(),
};

// ---------------------------------------------------------------- API ----

async function api(method, path, { params, json } = {}) {
  const url = new URL(path, location.origin);
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  }
  const res = await fetch(url, {
    method,
    headers: {
      "X-Telegram-Init-Data": initData,
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: json !== undefined ? JSON.stringify(json) : undefined,
  });
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

async function downloadReport(params, filename) {
  const url = new URL("/reports/export", location.origin);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url, { headers: { "X-Telegram-Init-Data": initData } });
  if (!res.ok) throw new Error("Не удалось сформировать отчёт");
  const blob = await res.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objUrl);
}

// ------------------------------------------------------------- helpers ----

function money(v) {
  return Number(v).toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function periodThisMonth() {
  const d = new Date();
  const start = new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
  const end = d.toISOString().slice(0, 10);
  return { period_start: start, period_end: end };
}

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2600);
}

function stateBlock(kind, text) {
  const icon = kind === "error" ? "⚠️" : kind === "empty" ? "🗒" : "⏳";
  return `<div class="state ${kind === "error" ? "error" : ""}"><span class="icon">${icon}</span>${esc(text)}</div>`;
}

function skeleton(lines = 3) {
  return `<div class="card">${Array.from({ length: lines })
    .map((_, i) => `<div class="skeleton" style="margin-bottom:${i === lines - 1 ? 0 : 8}px;width:${90 - i * 15}%"></div>`)
    .join("")}</div>`;
}

function teamName(teamId) {
  const t = state.teams.find((t) => t.id === teamId);
  return t ? t.name : null;
}

function userName(userId) {
  const u = state.users.find((u) => u.id === userId);
  return u ? u.full_name : userId?.slice(0, 8);
}

async function ensureTeams() {
  if (!state.teams.length) {
    try {
      state.teams = await api("GET", "/users/teams");
    } catch {
      state.teams = [];
    }
  }
  return state.teams;
}

async function ensureUsers() {
  if (!state.users.length) {
    try {
      state.users = await api("GET", "/users");
    } catch {
      state.users = [];
    }
  }
  return state.users;
}

// -------------------------------------------------------------- sheet ----

function openSheet(title, bodyHtml) {
  document.getElementById("sheet-content").innerHTML = `<div class="sheet-title">${esc(title)}</div>${bodyHtml}`;
  document.getElementById("sheet-backdrop").classList.add("open");
}

function closeSheet() {
  document.getElementById("sheet-backdrop").classList.remove("open");
}

document.getElementById("sheet-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "sheet-backdrop") closeSheet();
});

// -------------------------------------------------------------- top list --

function renderTopList(entries) {
  if (!entries.length) return stateBlock("empty", "Пока нет данных за период.");
  return `<div class="list">${entries
    .map(
      (e) => `<div class="list-item">
        <div class="rank">${e.rank}</div>
        <div class="main"><div class="title">${esc(e.full_name)}</div><div class="subtitle">${e.deposit_count} деп.</div></div>
        <div class="trailing"><div class="amount">${money(e.total_amount)}</div></div>
      </div>`
    )
    .join("")}</div>`;
}

function renderGoalCard(progress, { canEdit, onEdit } = {}) {
  if (!progress) {
    return `<div class="card">
      <div class="row"><span class="muted">План на месяц не задан</span>${
        canEdit ? `<button class="btn btn-secondary btn-sm" id="goal-edit-btn">Задать план</button>` : ""
      }</div>
    </div>`;
  }
  const pct = Math.min(progress.percent, 100);
  return `<div class="card">
    <div class="progress-row"><span>${money(progress.current_amount)} / ${money(progress.goal.target_amount)}</span><span>${progress.percent.toFixed(0)}%</span></div>
    <div class="progress-track"><div class="progress-fill ${progress.behind_pace ? "warning" : ""}" style="width:${pct}%"></div></div>
    ${progress.behind_pace ? `<div class="behind-pace">⚠️ Отстаём от графика к середине периода</div>` : ""}
    ${canEdit ? `<button class="btn btn-secondary btn-sm mt-4" id="goal-edit-btn">Изменить план</button>` : ""}
  </div>`;
}

function showSetGoalSheet(scope, scopeId, onDone) {
  openSheet("План на месяц", `
    <div class="field"><label>Сумма плана</label><input type="number" inputmode="decimal" id="goal-amount" placeholder="100000" /></div>
    <button class="btn btn-primary" id="goal-submit">Сохранить</button>
  `);
  document.getElementById("goal-submit").onclick = async () => {
    const amount = document.getElementById("goal-amount").value;
    if (!amount || Number(amount) <= 0) return toast("Введите сумму");
    try {
      const { period_start } = periodThisMonth();
      await api("POST", "/goals", { json: { scope, scope_id: scopeId, period: period_start, target_amount: amount } });
      closeSheet();
      toast("План сохранён");
      onDone?.();
    } catch (e) {
      toast(e.message);
    }
  };
}

// ------------------------------------------------------------- deposits --

function depositRow(dep, { canManage }) {
  const managerLabel = dep.manager_id === state.me.id ? "" : `<div class="subtitle">${esc(userName(dep.manager_id))}</div>`;
  const actions = canManage
    ? `<div class="actions">
        <button class="icon-btn" data-edit="${dep.id}" title="Изменить">✏️</button>
        <button class="icon-btn danger" data-del="${dep.id}" title="Удалить">🗑</button>
      </div>`
    : "";
  return `<div class="list-item">
    <div class="main"><div class="title">${esc(dep.client_ref)}</div>${managerLabel}<div class="subtitle">${new Date(dep.created_at).toLocaleDateString("ru-RU")}</div></div>
    <div class="trailing"><div class="amount">${money(dep.amount)} ${esc(dep.currency)}</div></div>
    ${actions}
  </div>`;
}

async function loadDeposits() {
  const view = document.getElementById("view-deposits");
  view.innerHTML = skeleton(4);
  try {
    const { period_start, period_end } = periodThisMonth();
    const deposits = await api("GET", "/deposits", { params: { period_start, period_end, limit: 50 } });
    if (state.me.role !== "manager") await ensureUsers();
    const canManage = true;
    view.innerHTML = deposits.length
      ? `<div class="list">${deposits.map((d) => depositRow(d, { canManage })).join("")}</div>`
      : stateBlock("empty", "За этот месяц депозитов нет.");

    view.querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = () => confirmDeleteDeposit(btn.dataset.del);
    });
    view.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.onclick = () => {
        const dep = deposits.find((d) => d.id === btn.dataset.edit);
        showEditDepositSheet(dep);
      };
    });
  } catch (e) {
    view.innerHTML = stateBlock("error", e.message);
  }
}

function confirmDeleteDeposit(depositId) {
  openSheet("Удалить депозит?", `
    <p class="muted">Депозит не удалится сразу — запрос уйдёт на согласование тимлиду/админу.</p>
    <button class="btn btn-danger btn-block" id="confirm-del">Запросить удаление</button>
  `);
  document.getElementById("confirm-del").onclick = async () => {
    try {
      await api("POST", `/deposits/${depositId}/change-requests`, { json: { action: "delete" } });
      closeSheet();
      toast("Запрос на удаление отправлен");
    } catch (e) {
      toast(e.message);
    }
  };
}

function showEditDepositSheet(dep) {
  openSheet("Запросить правку", `
    <div class="field"><label>Клиент</label><input id="edit-client" value="${esc(dep.client_ref)}" /></div>
    <div class="field"><label>Сумма</label><input id="edit-amount" type="number" inputmode="decimal" value="${dep.amount}" /></div>
    <button class="btn btn-primary" id="edit-submit">Отправить на согласование</button>
  `);
  document.getElementById("edit-submit").onclick = async () => {
    const client_ref = document.getElementById("edit-client").value.trim();
    const amount = document.getElementById("edit-amount").value;
    if (!client_ref || !amount || Number(amount) <= 0) return toast("Заполните поля");
    try {
      await api("POST", `/deposits/${dep.id}/change-requests`, {
        json: { action: "update", payload: { client_ref, amount } },
      });
      closeSheet();
      toast("Запрос на правку отправлен");
    } catch (e) {
      toast(e.message);
    }
  };
}

function showAddDepositSheet() {
  const isManager = state.me.role === "manager";
  openSheet("Внести депозит", `
    ${!isManager ? `<div class="field"><label>Менеджер</label><select id="dep-manager"></select></div>` : ""}
    <div class="field"><label>Клиент</label><input id="dep-client" placeholder="Имя или ID клиента" /></div>
    <div class="field"><label>Сумма</label><input id="dep-amount" type="number" inputmode="decimal" placeholder="0.00" /></div>
    <button class="btn btn-primary" id="dep-submit">Сохранить</button>
  `);
  if (!isManager) {
    ensureUsers().then((users) => {
      const managers = users.filter((u) => u.role === "manager" && (state.me.role === "admin" || u.team_id === state.me.team_id));
      document.getElementById("dep-manager").innerHTML = managers
        .map((u) => `<option value="${u.id}">${esc(u.full_name)}</option>`)
        .join("") || `<option value="">Нет менеджеров</option>`;
    });
  }
  document.getElementById("dep-submit").onclick = async () => {
    const client_ref = document.getElementById("dep-client").value.trim();
    const amount = document.getElementById("dep-amount").value;
    if (!client_ref || !amount || Number(amount) <= 0) return toast("Заполните поля");
    const json = { client_ref, amount, currency: "USD" };
    if (!isManager) {
      const managerId = document.getElementById("dep-manager").value;
      if (!managerId) return toast("Выберите менеджера");
      json.manager_id = managerId;
    }
    try {
      await api("POST", "/deposits", { json });
      closeSheet();
      toast("Депозит сохранён");
      state.loaded.delete("deposits");
      if (state.activeTab === "deposits") loadDeposits();
    } catch (e) {
      toast(e.message);
    }
  };
}

// ----------------------------------------------------------------- stats -

async function loadStats() {
  const view = document.getElementById("view-stats");
  view.innerHTML = skeleton(2) + skeleton(2);
  try {
    const period = periodThisMonth();
    const stats = await api("GET", "/stats/me", { params: period });
    const deltaKnown = stats.change_percent !== null && stats.change_percent !== undefined;
    const deltaClass = deltaKnown ? (stats.change_percent >= 0 ? "up" : "down") : "";
    const deltaText = deltaKnown ? `${stats.change_percent >= 0 ? "▲" : "▼"} ${Math.abs(stats.change_percent).toFixed(0)}%` : "";

    let html = `<h2 class="section-title">Этот месяц</h2>
    <div class="stat-grid">
      <div class="card stat-card"><div class="label">Сумма</div><div class="value">${money(stats.total_amount)}</div>${deltaKnown ? `<div class="delta ${deltaClass}">${deltaText}</div>` : ""}</div>
      <div class="card stat-card"><div class="label">Депозитов</div><div class="value">${stats.deposit_count}</div></div>
    </div>
    <div class="card stat-card mt-4"><div class="label">Место в команде</div><div class="value">${stats.rank ? `${stats.rank} из ${stats.team_size}` : "нет команды"}</div></div>`;

    if (stats.commission_rate !== null && stats.commission_rate !== undefined) {
      html += `<div class="card stat-card mt-4"><div class="label">Комиссия (${stats.commission_rate}%)</div><div class="value">${money(stats.commission_amount)}</div></div>`;
    }

    html += `<h2 class="section-title">План на месяц</h2><div id="stats-goal">${skeleton(2)}</div>`;
    view.innerHTML = html;

    try {
      const progress = await api("GET", "/goals/progress", { params: { scope: "user", scope_id: state.me.id, period: period.period_start } });
      document.getElementById("stats-goal").innerHTML = renderGoalCard(progress);
    } catch {
      document.getElementById("stats-goal").innerHTML = renderGoalCard(null);
    }
  } catch (e) {
    view.innerHTML = stateBlock("error", e.message);
  }
}

// ------------------------------------------------------------------ team -

async function loadTeam() {
  const view = document.getElementById("view-team");
  view.innerHTML = skeleton(4);
  try {
    const period = periodThisMonth();
    const top = await api("GET", "/stats/top/team", { params: period });
    let html = `<h2 class="section-title">Топ команды</h2>${renderTopList(top)}`;
    html += `<h2 class="section-title">План команды</h2><div id="team-goal">${skeleton(2)}</div>`;
    view.innerHTML = html;

    const loadGoal = async () => {
      try {
        const progress = await api("GET", "/goals/progress", { params: { scope: "team", scope_id: state.me.team_id, period: period.period_start } });
        document.getElementById("team-goal").innerHTML = renderGoalCard(progress, { canEdit: true });
      } catch {
        document.getElementById("team-goal").innerHTML = renderGoalCard(null, { canEdit: true });
      }
      document.getElementById("goal-edit-btn")?.addEventListener("click", () => {
        showSetGoalSheet("team", state.me.team_id, loadGoal);
      });
    };
    await loadGoal();
  } catch (e) {
    view.innerHTML = stateBlock("error", e.message);
  }
}

// --------------------------------------------------------------- company -

async function loadCompany() {
  const view = document.getElementById("view-company");
  view.innerHTML = skeleton(4);
  try {
    const period = periodThisMonth();
    const [companyTop, teams] = await Promise.all([
      api("GET", "/stats/top/company", { params: period }),
      ensureTeams(),
    ]);
    const total = companyTop.reduce((sum, e) => sum + Number(e.total_amount), 0);

    let html = `<div class="card"><div class="label">Компания за месяц</div><div class="value">${money(total)}</div></div>`;
    html += `<h2 class="section-title">Топ по компании</h2>${renderTopList(companyTop)}`;

    if (teams.length) {
      html += `<h2 class="section-title">Топ по команде</h2>
        <select id="company-team-select">${teams.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("")}</select>
        <div id="company-team-top" class="mt-4">${skeleton(3)}</div>`;
    }
    view.innerHTML = html;

    if (teams.length) {
      const select = document.getElementById("company-team-select");
      const loadTeamTop = async () => {
        const box = document.getElementById("company-team-top");
        box.innerHTML = skeleton(3);
        try {
          const entries = await api("GET", "/stats/top/team", { params: { ...period, team_id: select.value } });
          box.innerHTML = renderTopList(entries);
        } catch (e) {
          box.innerHTML = stateBlock("error", e.message);
        }
      };
      select.onchange = loadTeamTop;
      await loadTeamTop();
    }
  } catch (e) {
    view.innerHTML = stateBlock("error", e.message);
  }
}

// ----------------------------------------------------------------- teams -

async function loadTeams() {
  const view = document.getElementById("view-teams");
  view.innerHTML = skeleton(3);
  try {
    const [teams, users] = await Promise.all([ensureTeams(), ensureUsers()]);
    const teamleads = users.filter((u) => u.role === "teamlead");

    const rows = teams.length
      ? teams
          .map((t) => {
            const lead = users.find((u) => u.id === t.teamlead_id);
            return `<div class="list-item">
              <div class="main"><div class="title">${esc(t.name)}</div><div class="subtitle">${lead ? "Тимлид: " + esc(lead.full_name) : "Без тимлида"}</div></div>
              <button class="btn btn-secondary btn-sm" data-assign="${t.id}">Тимлид</button>
            </div>`;
          })
          .join("")
      : "";

    view.innerHTML = `
      <button class="btn btn-primary" id="add-team-btn">+ Новая команда</button>
      <div class="list mt-4">${rows || stateBlock("empty", "Команд пока нет")}</div>
    `;

    document.getElementById("add-team-btn").onclick = () => {
      openSheet("Новая команда", `
        <div class="field"><label>Название</label><input id="team-name" placeholder="Отдел продаж" /></div>
        <button class="btn btn-primary" id="team-submit">Создать</button>
      `);
      document.getElementById("team-submit").onclick = async () => {
        const name = document.getElementById("team-name").value.trim();
        if (!name) return toast("Введите название");
        try {
          await api("POST", "/users/teams", { json: { name } });
          state.teams = [];
          closeSheet();
          toast("Команда создана");
          loadTeams();
        } catch (e) {
          toast(e.message);
        }
      };
    };

    view.querySelectorAll("[data-assign]").forEach((btn) => {
      btn.onclick = () => {
        const teamId = btn.dataset.assign;
        openSheet("Назначить тимлида", `
          <div class="field"><label>Тимлид</label>
            <select id="lead-select"><option value="">— без тимлида —</option>${teamleads
              .map((u) => `<option value="${u.id}">${esc(u.full_name)}</option>`)
              .join("")}</select>
          </div>
          <button class="btn btn-primary" id="lead-submit">Сохранить</button>
        `);
        document.getElementById("lead-submit").onclick = async () => {
          const teamlead_id = document.getElementById("lead-select").value || null;
          try {
            await api("PATCH", `/users/teams/${teamId}`, { json: { teamlead_id } });
            state.teams = [];
            closeSheet();
            toast("Сохранено");
            loadTeams();
          } catch (e) {
            toast(e.message);
          }
        };
      };
    });
  } catch (e) {
    view.innerHTML = stateBlock("error", e.message);
  }
}

// ---------------------------------------------------------------- people -

async function loadPeople() {
  const view = document.getElementById("view-people");
  view.innerHTML = skeleton(4);
  try {
    const [users, teams] = await Promise.all([ensureUsers(), ensureTeams()]);
    state.users = await api("GET", "/users"); // always fresh here — this is the management screen

    const rows = state.users
      .map((u) => {
        const team = teamName(u.team_id);
        const statusBadge = `<span class="badge ${u.status}">${STATUS_LABELS[u.status]}</span>`;
        const commission = u.role === "manager" && u.commission_rate !== null ? ` · комиссия ${u.commission_rate}%` : "";
        return `<div class="list-item">
          <div class="main">
            <div class="title">${esc(u.full_name)} <span class="badge role">${ROLE_LABELS[u.role]}</span></div>
            <div class="subtitle">id ${u.telegram_id}${team ? " · " + esc(team) : ""}${commission}</div>
          </div>
          <div class="actions">
            ${statusBadge}
            <button class="icon-btn" data-manage="${u.id}">⚙️</button>
          </div>
        </div>`;
      })
      .join("");

    view.innerHTML = `
      <button class="btn btn-primary" id="add-user-btn">+ Добавить пользователя</button>
      <h2 class="section-title">Все пользователи</h2>
      <div class="list">${rows || stateBlock("empty", "Пользователей пока нет")}</div>
    `;

    document.getElementById("add-user-btn").onclick = showAddUserSheet;
    view.querySelectorAll("[data-manage]").forEach((btn) => {
      btn.onclick = () => showManageUserSheet(state.users.find((u) => u.id === btn.dataset.manage));
    });
  } catch (e) {
    view.innerHTML = stateBlock("error", e.message);
  }
}

function showAddUserSheet() {
  openSheet("Добавить пользователя", `
    <div class="field"><label>Telegram ID</label><input id="nu-tgid" type="number" placeholder="123456789" /></div>
    <div class="field"><label>Имя</label><input id="nu-name" placeholder="Имя Фамилия" /></div>
    <div class="field"><label>Роль</label>
      <select id="nu-role">
        <option value="manager">Менеджер</option>
        <option value="teamlead">Тимлид</option>
        <option value="admin">Админ</option>
      </select>
    </div>
    <div class="field"><label>Команда</label>
      <select id="nu-team"><option value="">— без команды —</option>${state.teams
        .map((t) => `<option value="${t.id}">${esc(t.name)}</option>`)
        .join("")}</select>
    </div>
    <button class="btn btn-primary" id="nu-submit">Добавить</button>
  `);
  document.getElementById("nu-submit").onclick = async () => {
    const telegram_id = Number(document.getElementById("nu-tgid").value);
    const full_name = document.getElementById("nu-name").value.trim();
    const role = document.getElementById("nu-role").value;
    const team_id = document.getElementById("nu-team").value || null;
    if (!telegram_id || !full_name) return toast("Заполните поля");
    try {
      await api("POST", "/users", { json: { telegram_id, full_name, role, team_id } });
      closeSheet();
      toast("Пользователь добавлен");
      loadPeople();
    } catch (e) {
      toast(e.message);
    }
  };
}

function showManageUserSheet(user) {
  const isBlocked = user.status === "blocked";
  openSheet(user.full_name, `
    <div class="field"><label>Роль (Telegram ID ${user.telegram_id})</label>
      <select id="mu-role">
        ${["manager", "teamlead", "admin"].map((r) => `<option value="${r}" ${r === user.role ? "selected" : ""}>${ROLE_LABELS[r]}</option>`).join("")}
      </select>
    </div>
    <div class="field"><label>Команда</label>
      <select id="mu-team"><option value="">— без команды —</option>${state.teams
        .map((t) => `<option value="${t.id}" ${t.id === user.team_id ? "selected" : ""}>${esc(t.name)}</option>`)
        .join("")}</select>
    </div>
    ${user.role === "manager" ? `<div class="field"><label>Комиссия, %</label><input id="mu-commission" type="number" inputmode="decimal" value="${user.commission_rate ?? ""}" placeholder="0" /></div>` : ""}
    <button class="btn btn-primary btn-block" id="mu-save">Сохранить</button>
    <button class="btn ${isBlocked ? "btn-secondary" : "btn-danger"} btn-block mt-4" id="mu-toggle-block">${isBlocked ? "Разблокировать" : "Заблокировать"}</button>
  `);

  document.getElementById("mu-save").onclick = async () => {
    try {
      const role = document.getElementById("mu-role").value;
      const team_id = document.getElementById("mu-team").value || null;
      if (role !== user.role) await api("PATCH", `/users/${user.id}/role`, { json: { role } });
      if (team_id !== user.team_id) await api("PATCH", `/users/${user.id}/team`, { json: { team_id } });
      const commissionInput = document.getElementById("mu-commission");
      if (commissionInput && role === "manager") {
        const rate = commissionInput.value === "" ? 0 : Number(commissionInput.value);
        await api("POST", `/users/${user.id}/commission-rate`, { json: { commission_rate: rate } });
      }
      closeSheet();
      toast("Сохранено");
      loadPeople();
    } catch (e) {
      toast(e.message);
    }
  };

  document.getElementById("mu-toggle-block").onclick = async () => {
    try {
      await api("POST", `/users/${user.id}/${isBlocked ? "unblock" : "block"}`);
      closeSheet();
      toast(isBlocked ? "Разблокирован" : "Заблокирован");
      loadPeople();
    } catch (e) {
      toast(e.message);
    }
  };
}

// -------------------------------------------------------------- requests -

async function loadRequests() {
  const view = document.getElementById("view-requests");
  view.innerHTML = skeleton(3);
  try {
    const requests = await api("GET", "/change-requests", { params: { status: "pending" } });
    if (!requests.length) {
      view.innerHTML = stateBlock("empty", "Нет заявок, ожидающих согласования.");
      return;
    }
    const deposits = await Promise.all(
      requests.map((r) => api("GET", `/deposits/${r.deposit_id}`).catch(() => null))
    );
    await ensureUsers();

    view.innerHTML = `<div class="list">${requests
      .map((r, i) => {
        const dep = deposits[i];
        const depositLine = dep ? `${esc(dep.client_ref)} — ${money(dep.amount)} ${esc(dep.currency)}` : "депозит не найден";
        const requester = userName(r.requested_by);
        const changes = r.action === "update" && r.payload ? `<div class="subtitle">Новое: ${esc(JSON.stringify(r.payload))}</div>` : "";
        return `<div class="list-item">
          <div class="main">
            <div class="title">${ACTION_LABELS[r.action]}: ${depositLine}</div>
            <div class="subtitle">от ${esc(requester)}</div>
            ${changes}
          </div>
          <div class="actions">
            <button class="icon-btn" data-approve="${r.id}" title="Подтвердить">✅</button>
            <button class="icon-btn danger" data-reject="${r.id}" title="Отклонить">❌</button>
          </div>
        </div>`;
      })
      .join("")}</div>`;

    view.querySelectorAll("[data-approve]").forEach((btn) => {
      btn.onclick = () => reviewRequest(btn.dataset.approve, "approve");
    });
    view.querySelectorAll("[data-reject]").forEach((btn) => {
      btn.onclick = () => reviewRequest(btn.dataset.reject, "reject");
    });
  } catch (e) {
    view.innerHTML = stateBlock("error", e.message);
  }
}

async function reviewRequest(id, action) {
  try {
    await api("POST", `/change-requests/${id}/${action}`);
    toast(action === "approve" ? "Подтверждено" : "Отклонено");
    loadRequests();
  } catch (e) {
    toast(e.message);
  }
}

// ------------------------------------------------------------------ more -

async function loadMore() {
  const view = document.getElementById("view-more");
  const isAdmin = state.me.role === "admin";
  view.innerHTML = `
    <h2 class="section-title">Отчёты</h2>
    <button class="btn btn-secondary btn-block" id="export-btn">Экспорт в Excel (этот месяц)</button>
    ${isAdmin ? `<h2 class="section-title">Аудит-лог</h2><div id="audit-log">${skeleton(4)}</div>` : ""}
  `;
  document.getElementById("export-btn").onclick = async () => {
    const period = periodThisMonth();
    const params = { ...period };
    if (state.me.role === "teamlead") {
      params.scope = "team";
      params.scope_id = state.me.team_id;
    } else {
      params.scope = "company";
    }
    try {
      toast("Формируем отчёт…");
      await downloadReport(params, `deposits_${params.scope}_${period.period_start}_${period.period_end}.xlsx`);
    } catch (e) {
      toast(e.message);
    }
  };

  if (isAdmin) {
    try {
      await ensureUsers();
      const log = await api("GET", "/audit-log");
      const box = document.getElementById("audit-log");
      box.innerHTML = log.length
        ? `<div class="list">${log
            .slice(0, 30)
            .map((entry) => {
              const diff = entry.diff || {};
              const before = diff.before || {};
              const after = diff.after || {};
              let changeText = "";
              if (entry.action === "update") {
                const changed = Object.keys(after).filter((k) => String(before[k]) !== String(after[k]));
                changeText = changed.map((k) => `${k}: ${before[k]} → ${after[k]}`).join(", ");
              } else if (entry.action === "create") {
                changeText = `${after.client_ref ?? ""} — ${after.amount ?? ""}`;
              } else if (entry.action === "delete") {
                changeText = `${before.client_ref ?? ""} — ${before.amount ?? ""}`;
              }
              return `<div class="list-item">
                <div class="main">
                  <div class="title">${ACTION_LABELS[entry.action]} · ${esc(userName(entry.changed_by))}</div>
                  <div class="subtitle">${esc(changeText)}</div>
                </div>
                <div class="trailing"><div class="meta">${new Date(entry.changed_at).toLocaleDateString("ru-RU")}</div></div>
              </div>`;
            })
            .join("")}</div>`
        : stateBlock("empty", "Аудит-лог пуст.");
    } catch (e) {
      document.getElementById("audit-log").innerHTML = stateBlock("error", e.message);
    }
  }
}

// ------------------------------------------------------------- routing --

const LOADERS = {
  stats: loadStats,
  deposits: loadDeposits,
  team: loadTeam,
  company: loadCompany,
  teams: loadTeams,
  people: loadPeople,
  requests: loadRequests,
  more: loadMore,
};

function switchTab(id) {
  state.activeTab = id;
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${id}`));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === id));

  const fab = document.getElementById("fab");
  fab.hidden = !(id === "deposits");
  fab.onclick = () => showAddDepositSheet();

  if (!state.loaded.has(id)) {
    state.loaded.add(id);
    LOADERS[id]?.();
  }
}

function refreshActiveTab() {
  if (state.activeTab) LOADERS[state.activeTab]?.();
}

function buildLayout() {
  const tabs = TABS[state.me.role] || [];
  document.getElementById("views").innerHTML = tabs.map((t) => `<div class="view" id="view-${t.id}"></div>`).join("");
  document.getElementById("tabbar").innerHTML = tabs
    .map((t) => `<button class="tab" data-tab="${t.id}"><span class="tab-icon">${t.icon}</span>${esc(t.label)}</button>`)
    .join("");
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.onclick = () => switchTab(btn.dataset.tab);
  });
  switchTab(tabs[0]?.id);
}

// --------------------------------------------------------------- init --

async function init() {
  try {
    state.me = await api("GET", "/users/me");
  } catch (e) {
    document.getElementById("app").innerHTML = stateBlock("error", "Доступ запрещён. Обратитесь к администратору.");
    return;
  }
  document.getElementById("greeting").textContent = state.me.full_name;
  document.getElementById("role-badge").textContent = ROLE_LABELS[state.me.role] || state.me.role;
  buildLayout();
}

init();
