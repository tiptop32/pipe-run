// QA Pipe — main application logic
// Token is kept in memory after unlock, never sent to server storage

let _token = null;          // decrypted GitLab token (in-memory only)
let _projects = [];         // list of UserProject from server
let _currentProject = null; // selected UserProject object

// ── API helpers ────────────────────────────────────────────

async function api(method, path, body) {
  if (!_token) { showView('unlock'); return null; }
  const opts = {
    method,
    headers: { 'PRIVATE-TOKEN': _token, 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const resp = await fetch('/api/v1' + path, opts);
  if (resp.status === 401) { lock(); return null; }
  if (resp.status === 204) return null;
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

// ── Views ──────────────────────────────────────────────────

function showView(name) {
  document.querySelectorAll('[data-view]').forEach(el => {
    el.style.display = el.dataset.view === name ? '' : 'none';
  });
}

function toast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type;
  t.style.opacity = '1';
  setTimeout(() => t.style.opacity = '0', 3000);
}

// ── Auth ───────────────────────────────────────────────────

async function boot() {
  await initDB();
  const exists = await hasToken();
  showView(exists ? 'unlock' : 'setup');
}

async function onSetup(e) {
  e.preventDefault();
  const token = document.getElementById('setupToken').value.trim();
  const pass  = document.getElementById('setupPass').value;
  const pass2 = document.getElementById('setupPass2').value;
  if (!token || !pass) return toast('Заполните все поля', 'error');
  if (pass !== pass2) return toast('Пароли не совпадают', 'error');
  await saveToken(token, pass);
  toast('Токен сохранён', 'success');
  _token = token;
  await enterApp();
}

async function onUnlock(e) {
  e.preventDefault();
  const pass = document.getElementById('unlockPass').value;
  const tok  = await loadToken(pass);
  if (!tok) return toast('Неверный пароль', 'error');
  _token = tok;
  await enterApp();
}

async function lock() {
  _token = null;
  _projects = [];
  _currentProject = null;
  showView('unlock');
}

async function logout() {
  await clearToken();
  _token = null;
  _projects = [];
  _currentProject = null;
  showView('setup');
}

// ── App ────────────────────────────────────────────────────

async function enterApp() {
  _projects = await api('GET', '/projects') || [];
  renderTabs();
  if (_projects.length === 0) {
    showView('addProject');
  } else {
    await selectProject(_projects[0]);
    showView('main');
  }
}

function renderTabs() {
  const nav = document.getElementById('projectTabs');
  nav.innerHTML = '';
  _projects.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'tab-btn' + (p.id === _currentProject?.id ? ' active' : '');
    btn.textContent = p.display_name;
    btn.onclick = () => selectProject(p);
    nav.appendChild(btn);
  });
  const addBtn = document.createElement('button');
  addBtn.className = 'tab-btn tab-add';
  addBtn.textContent = '+';
  addBtn.title = 'Добавить проект';
  addBtn.onclick = () => showView('addProject');
  nav.appendChild(addBtn);
}

async function selectProject(project) {
  _currentProject = project;
  renderTabs();
  await loadConfigs();
  showView('main');
}

// ── Add project ────────────────────────────────────────────

async function onAddProject(e) {
  e.preventDefault();
  const gitlab_project_id = parseInt(document.getElementById('addProjectId').value);
  const display_name = document.getElementById('addProjectName').value.trim();
  const allure_results_path = document.getElementById('addProjectAllure').value.trim() || null;
  if (!gitlab_project_id || !display_name) return toast('Заполните обязательные поля', 'error');
  try {
    const p = await api('POST', '/projects', { gitlab_project_id, display_name, allure_results_path });
    if (!p) return;
    _projects.push(p);
    document.getElementById('addProjectForm').reset();
    await selectProject(p);
    showView('main');
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Custom Pipelines ───────────────────────────────────────

let _configs = [];

async function loadConfigs() {
  if (!_currentProject) return;
  _configs = await api('GET', `/projects/${_currentProject.id}/configs`) || [];
  renderConfigs();
}

function renderConfigs() {
  const list = document.getElementById('configList');
  if (_configs.length === 0) {
    list.innerHTML = '<p class="empty">Нет custom pipelines. Создайте первый.</p>';
    return;
  }
  list.innerHTML = _configs.map(cfg => `
    <div class="card" id="cfg-${cfg.id}">
      <div class="card-header">
        <span class="card-title">${esc(cfg.name)}</span>
        <span class="badge ${statusClass(cfg.last_pipeline_status)}">${cfg.last_pipeline_status || '—'}</span>
      </div>
      <div class="card-meta">ref: <code>${esc(cfg.ref)}</code></div>
      <div class="card-actions">
        <button onclick="runConfig('${cfg.id}')">▶ Run</button>
        <button onclick="editConfig('${cfg.id}')">✎ Edit</button>
        <button class="danger" onclick="deleteConfig('${cfg.id}')">✕</button>
        ${cfg.last_pipeline_status === 'success' && _currentProject.allure_results_path
          ? `<button onclick="triggerAllure('${cfg.id}', ${cfg.last_pipeline_id})">📊 Allure</button>`
          : ''}
      </div>
    </div>
  `).join('');
}

function statusClass(s) {
  return { success: 'success', failed: 'failed', running: 'running', pending: 'pending' }[s] || '';
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function onCreateConfig(e) {
  e.preventDefault();
  const name = document.getElementById('newConfigName').value.trim();
  const ref  = document.getElementById('newConfigRef').value.trim() || 'main';
  if (!name) return toast('Введите название', 'error');
  try {
    const cfg = await api('POST', `/projects/${_currentProject.id}/configs`, { name, ref, variables: [] });
    if (!cfg) return;
    _configs.push(cfg);
    document.getElementById('createConfigForm').reset();
    renderConfigs();
    toast('Pipeline создан', 'success');
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function runConfig(id) {
  try {
    const result = await api('POST', `/projects/${_currentProject.id}/configs/${id}/run`);
    if (!result) return;
    toast(`Pipeline #${result.pipeline_id} запущен (${result.pipeline_status})`, 'success');
    await loadConfigs();
    pollStatus(id, result.pipeline_id);
  } catch (err) {
    toast(err.message, 'error');
  }
}

function pollStatus(configId, pipelineId) {
  const interval = setInterval(async () => {
    try {
      const pipeline = await api('GET', `/gitlab/${_currentProject.gitlab_project_id}/pipelines/${pipelineId}`);
      if (!pipeline) { clearInterval(interval); return; }
      await api('PATCH', `/projects/${_currentProject.id}/configs/${configId}/pipeline-status`, { status: pipeline.status });
      await loadConfigs();
      const TERMINAL = ['success', 'failed', 'canceled', 'skipped'];
      if (TERMINAL.includes(pipeline.status)) clearInterval(interval);
    } catch { clearInterval(interval); }
  }, 5000);
}

async function deleteConfig(id) {
  if (!confirm('Удалить этот pipeline?')) return;
  await api('DELETE', `/projects/${_currentProject.id}/configs/${id}`);
  _configs = _configs.filter(c => c.id !== id);
  renderConfigs();
}

function editConfig(id) {
  // inline editing placeholder — opens a simple prompt for now
  const cfg = _configs.find(c => c.id === id);
  if (!cfg) return;
  const name = prompt('Новое название:', cfg.name);
  if (!name) return;
  api('PUT', `/projects/${_currentProject.id}/configs/${id}`, { name, ref: cfg.ref, variables: cfg.variables })
    .then(updated => {
      if (!updated) return;
      const i = _configs.findIndex(c => c.id === id);
      if (i !== -1) _configs[i] = updated;
      renderConfigs();
    });
}

// ── Allure ─────────────────────────────────────────────────

async function triggerAllure(configId, pipelineId) {
  const cfg = _configs.find(c => c.id === configId);
  if (!cfg) return;
  // find job with artifacts — need to fetch jobs
  try {
    const jobs = await api('GET', `/gitlab/${_currentProject.gitlab_project_id}/pipelines/${pipelineId}/jobs`);
    // not yet in gitlab router — show toast about it
    toast('Запуск генерации Allure...', 'info');
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Bootstrap ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', boot);
