# QA Pipe — Open Source Edition (Local-First + Docker)

## Overview

Создание открытого инструмента для QA-инженеров. Развёртывается в Docker, доступен нескольким пользователям.
Токен GitLab хранится **в браузере** (IndexedDB, AES-256-GCM), а не на сервере — подход Local-First.
Каждый пользователь сам добавляет свои проекты (вкладки). Данные синхронизируются через сервер (ключ — gitlab_user_id).

**Acceptance criteria:**
- `docker compose up` запускает сервис без ошибок
- Несколько пользователей могут использовать один инстанс независимо
- Создание custom pipeline, просмотр расписаний, генерация Allure отчёта — работают
- Данные не теряются при перезапуске контейнера (volume)
- Все тесты проходят, нет X5/Keycloak зависимостей

## Context (from discovery)

- **Целевой репо:** `/Volumes/My Shared Files/git_reps/qa-pipe/`
- **Уже реализовано (старая архитектура):** конфиг, db/base, модели без user_id, CRUD без user_id, GitLab клиент, тесты
- **GitLab клиент** (`gitlab.py`) — не требует изменений, токен передаётся при создании
- **Паттерн хранения токена** — из оригинального qa-pipe (IndexedDB + AES-256-GCM + Web Crypto API)

## Development Approach

- **Testing approach:** Regular (код → потом тесты)
- Реализуем слоями: конфиг → модели → auth → CRUD → API → Docker → UI
- После каждой задачи запускаем `uv run pytest`
- Обратная совместимость со старой архитектурой не нужна

## Testing Strategy

- **Unit tests:** конфиг, CRUD (in-memory SQLite), auth middleware (mock httpx)
- **Integration:** GitLab клиент через `respx`, API через `AsyncClient`
- **async тесты:** `asyncio_mode = "auto"`, conftest с in-memory SQLite фикстурой
- Test command: `uv run pytest`

## Progress Tracking

- Отмечаем `[x]` сразу после завершения
- ➕ для новых задач, ⚠️ для блокеров

## Solution Overview

**Local-First + Stateless Auth:**
1. Браузер хранит токен зашифрованным в IndexedDB (AES-256-GCM + PBKDF2, master password)
2. Каждый запрос несёт заголовок `PRIVATE-TOKEN: <gitlab_token>`
3. Middleware: извлекает токен → `GET /api/v4/user` → `gitlab_user_id` → `request.state.user_id`
4. Все данные на сервере привязаны к `user_id`

**Multi-project tabs:**
- Пользователь добавляет проекты вручную (gitlab_project_id, display_name, опциональный allure_results_path)
- Таблица `user_projects` хранит проекты каждого пользователя

**Docker:**
- Python + Allure CLI (Java) в одном образе
- SQLite + volume для персистентности

## Technical Details

**Конфиг сервера (`config.json`) — минимальный:**
```json
{
  "GITLAB_BASE_URL": "https://gitlab.com",
  "REPORTS_DIR": "./allure_reports",
  "DATABASE_URL": "sqlite+aiosqlite:///./data.db",
  "HOST": "0.0.0.0",
  "PORT": 8080,
  "LOGLEVEL": "INFO"
}
```

**Auth flow:**
```
Browser → PRIVATE-TOKEN header → Middleware → GET /api/v4/user → user_id → request.state
```

**DB Models:**
```
user_projects:        id (UUID PK), user_id (int, gitlab), gitlab_project_id (int),
                      display_name (str), allure_results_path (str|null), created_at

custom_pipelines:     id (UUID PK), user_id (int), project_id (UUID FK→user_projects),
                      name, ref, variables (JSON), seeded_from_schedule_id,
                      last_pipeline_id, last_pipeline_status, last_run_at, created_at, updated_at

schedule_bookmarks:   id (UUID PK), user_id (int), project_id (UUID FK→user_projects),
                      schedule_id (int), display_name (str|null), created_at

allure_reports:       pipeline_id (int PK), gitlab_project_id (int),
                      status (not_started|pending|ready|error), error_text (str|null), created_at
```

**Allure:** генерация локальная, Allure CLI в Docker-образе.
Если `allure_results_path` у проекта null — вкладка Allure скрыта.

## What Goes Where

**Implementation Steps** — всё реализуется в этом репо.

**Post-Completion:**
- Ручное тестирование с реальным GitLab
- Убедиться что `data.db` сохраняется между `docker compose restart`
- Проверить генерацию Allure с реальными артефактами

## Implementation Steps

### Task 1: Bootstrap ✅

Уже выполнено: `pyproject.toml`, `alembic.ini`, `.gitignore`, `conftest.py`, структура директорий.

### Task 2: Обновить конфиг — убрать GITLAB_TOKEN/PROJECT_ID/VERIFY_SSL

**Files:**
- Modify: `src/app/conf/config_model.py`
- Modify: `config.example.json`
- Modify: `tests/test_config.py`

- [x] убрать `GITLAB_TOKEN`, `GITLAB_PROJECT_ID`, `GITLAB_VERIFY_SSL` из `Settings`
- [x] обновить `config.example.json` — только: GITLAB_BASE_URL, REPORTS_DIR, DATABASE_URL, HOST, PORT, LOGLEVEL
- [x] обновить `tests/test_config.py` — убрать тесты на удалённые поля
- [x] `uv run pytest tests/test_config.py` — проходит ✅

### Task 3: Обновить DB модели — UserProject, user_id, AllureReport

**Files:**
- Modify: `src/app/features/pipelines/models.py`
- Modify: `src/app/db/migrations/versions/0001_initial.py`
- Modify: `tests/test_db.py`

- [x] добавить `UserProject` модель (user_id int, gitlab_project_id int, display_name, allure_results_path nullable)
- [x] добавить `user_id: int` в `CustomPipeline` (nullable=False)
- [x] изменить `project_id` в `CustomPipeline` на UUID FK → user_projects.id
- [x] добавить `user_id: int` в `ScheduleBookmark` (nullable=False)
- [x] изменить `project_id` в `ScheduleBookmark` на UUID FK → user_projects.id
- [x] добавить `AllureReport` модель (pipeline_id int PK, gitlab_project_id int, status, error_text, created_at)
- [x] переписать миграцию `0001_initial.py` с четырьмя таблицами
- [x] обновить `tests/test_db.py` для новых моделей
- [x] `uv run pytest tests/test_db.py` — проходит

### Task 4: Обновить CRUD — user_id, UserProject CRUD

**Files:**
- Modify: `src/app/features/pipelines/crud.py`
- Modify: `tests/test_crud.py`

- [x] добавить `user_id` параметр во все функции CustomPipeline и ScheduleBookmark
- [x] фильтровать запросы по `user_id` (`.where(Model.user_id == user_id)`)
- [x] добавить CRUD для `UserProject`: create, list, get, delete
- [x] добавить CRUD для `AllureReport`: upsert_status, get_status
- [x] обновить `tests/test_crud.py` с user_id во всех вызовах
- [x] `uv run pytest tests/test_crud.py` — проходит

### Task 5: Auth middleware и deps

**Files:**
- Create: `src/app/auth/__init__.py`
- Create: `src/app/auth/middleware.py`
- Create: `src/app/auth/deps.py`
- Create: `tests/test_auth.py`

- [x] создать `middleware.py` — `GitLabAuthMiddleware(BaseHTTPMiddleware)`:
  - пропускать `/health`, `/static`, `/favicon.ico` без токена
  - читать `PRIVATE-TOKEN` из заголовка; если нет — 401
  - `GET {GITLAB_BASE_URL}/api/v4/user` с токеном
  - если 401/403 от GitLab — 401 клиенту
  - записывать `request.state.user_id` и `request.state.gitlab_token`
- [x] создать `deps.py` — FastAPI dependency `get_current_user() -> int` (читает `request.state.user_id`)
- [x] создать dependency `get_gitlab_client(request) -> GitLabClient` (токен + project_id из path/body)
- [x] написать тесты: middleware с валидным токеном (mock respx), невалидным, без токена
- [x] `uv run pytest tests/test_auth.py` — проходит ✅

### Task 6: GitLab клиент ✅

Уже реализован и протестирован (`src/app/features/pipelines/gitlab.py`, `tests/test_gitlab_client.py`).
Не требует изменений — токен передаётся при создании `GitLabClient(base_url, access_token, project_id)`.

### Task 7–13: Реализация ✅ (выполнено)

Allure report, Projects API, Pipelines API, GitLab router, main.py, Docker, Frontend — реализованы и протестированы. 61 тест проходит.

### Task 14: README и финальная проверка ✅ (выполнено)

README написан. Тесты проходят.

---

## Code Review findings (2026-05-17)

Три параллельных ревью выявили следующие проблемы, требующие исправления.

### Task 15: Критические исправления безопасности

**Files:**
- Modify: `src/app/features/pipelines/allure_report.py`
- Modify: `src/app/features/pipelines/crud.py`
- Modify: `src/app/features/gitlab/router.py`
- Modify: `src/app/auth/middleware.py`
- Modify: `src/app/main.py`
- Modify: `Dockerfile`
- Modify: `tests/test_allure_report.py`
- Modify: `tests/test_api_gitlab.py`

- [x] **IDOR**: добавить `Depends(get_current_user)` и проверку владения в `trigger_allure_report` — пользователь должен иметь проект с таким `gitlab_project_id`
- [x] **IDOR**: добавить проверку владения в `allure_report_status`
- [x] **BackgroundTasks session**: `generate_report` открывает собственную сессию через `async_session_factory` — session из Depends закрывается до запуска фоновой задачи
- [x] **asyncio.run в lifespan**: запускать `_run_migrations` через `await loop.run_in_executor(None, _run_migrations)` — Alembic вызывает asyncio.run() внутри, что падает в уже запущенном loop
- [x] **Zip slip**: добавить явную проверку `target.resolve().startswith(results_dir.resolve())` в `_extract_allure_results`
- [x] **allure_results_path**: брать из user_project и передавать в `generate_report` → `_extract_allure_results` вместо хардкода `"allure-results/"`
- [x] **TTL cache**: кешировать token→user_id в middleware (60 сек, max 1000 записей) чтобы не долбить GitLab каждым запросом
- [x] **Dockerfile**: добавить непривилегированного пользователя (`RUN useradd … && USER app`) — контейнер не должен работать от root
- [x] Обновить тесты: `test_allure_report.py` (новая сигнатура), `test_api_gitlab.py` (IDOR fix)
- [x] `uv run pytest` — 63 теста проходят ✅

### Task 16: Качество кода (HIGH/MEDIUM)

**Files:**
- Modify: `src/app/features/projects/router.py`
- Modify: `src/app/features/pipelines/gitlab.py`
- Modify: `src/app/features/pipelines/schemas.py`
- Modify: `src/app/db/base.py`
- Modify: `src/app/features/pipelines/allure_report.py`
- Modify: `src/app/static/js/app.js`
- Modify: `src/app/static/js/auth.js`

- [x] **UUID path param**: `project_id: uuid.UUID` вместо `str` + убрать `import uuid as _uuid` внутри функции в `projects/router.py`
- [x] **httpx connection pooling**: `GitLabClient.__init__` создаёт `self._client = httpx.AsyncClient(...)` — переиспользовать клиент внутри одного запроса
- [x] **AllureStatus StrEnum**: заменить `Literal[...]` на `StrEnum` (stdlib, Python 3.11+)
- [x] **return type annotation**: `AsyncGenerator[AsyncSession, None]` в `get_db_session`
- [x] **`import io`**: перенести на верх `allure_report.py`
- [x] **`Field(default_factory=list)`**: в `schemas.py` для `variables`
- [x] **`esc()` XSS**: добавить экранирование `"` → `&quot;` и `'` → `&#x27;` в `app.js`
- [x] **PBKDF2**: увеличить итерации до 600 000 (OWASP 2026) в `auth.js`
- [x] `uv run pytest` — 63 теста проходят ✅

### Task 17: CI/CD и OSS-файлы

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/docker.yml`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/dependabot.yml`

- [x] `ci.yml`: запускать `uv run pytest` на каждый push/PR, Python 3.11
- [x] `docker.yml`: сборка и публикация образа при создании тега `v*`
- [x] `CONTRIBUTING.md`: гайд по вкладу (fork, ветка, PR, тесты)
- [x] `SECURITY.md`: disclosure policy — отправлять на email, не через issues
- [x] `CHANGELOG.md`: Keep a Changelog формат, первая версия 0.1.0
- [x] issue templates: bug_report.yml, feature_request.yml
- [x] PR template + dependabot.yml (pip weekly)

### Task 18: Финальная проверка после исправлений

- [ ] `uv run pytest` — все тесты проходят
- [ ] нет regression в существующих 61+ тестах
- [ ] `grep -rn "import io" src/app/features/pipelines/allure_report.py` — импорт на верхнем уровне
- [ ] переместить план в `docs/plans/completed/`

## Post-Completion

**Ручная проверка:**
- Открыть браузер, ввести master password + GitLab токен
- Добавить проект, создать custom pipeline, запустить, дождаться статуса
- Если allure_results_path настроен — сгенерировать отчёт
- Перезапустить `docker compose restart` — данные сохранились

**Внешние шаги:**
- Проверить видимость репо перед публикацией
- Настроить GitHub Actions (опционально)
