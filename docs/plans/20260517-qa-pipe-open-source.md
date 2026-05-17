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

### Task 7: Allure Report генератор

**Files:**
- Create: `src/app/features/pipelines/allure_report.py`
- Create: `tests/test_allure_report.py`

- [ ] создать `allure_report.py`:
  - `AllureStatus = Literal["not_started", "pending", "ready", "error"]`
  - `async def generate_report(gitlab_client, job_id, report_dir) -> Path` — скачать артефакты, распаковать zip, запустить `allure generate`
  - `async def get_report_status(pipeline_id, session) -> AllureStatus` — читать из `allure_reports` таблицы
- [ ] написать тесты: `get_report_status` для всех статусов, mock для download + extract
- [ ] `uv run pytest tests/test_allure_report.py` — проходит

### Task 8: API — User Projects

**Files:**
- Create: `src/app/features/projects/router.py`
- Create: `src/app/features/projects/__init__.py`
- Create: `tests/test_api_projects.py`

- [ ] `POST /api/v1/projects` — создать проект (gitlab_project_id, display_name, allure_results_path?)
- [ ] `GET /api/v1/projects` — список проектов пользователя
- [ ] `DELETE /api/v1/projects/{id}` — удалить проект
- [ ] использовать `Depends(get_current_user)` для user_id
- [ ] написать тесты через `AsyncClient` с мок-middleware
- [ ] `uv run pytest tests/test_api_projects.py` — проходит

### Task 9: API — Custom Pipelines

**Files:**
- Create: `src/app/features/pipelines/api.py`
- Create: `src/app/features/pipelines/__init__.py`
- Create: `tests/test_api_pipelines.py`

- [ ] перенести эндпоинты из qa-tools, адаптировать: добавить `user_id` через `Depends`, добавить `project_id` из пути или тела
- [ ] убрать `allure_cache` из ответов, убрать `fetch_and_cache_allure` вызовы
- [ ] `POST /api/v1/projects/{project_id}/configs`
- [ ] `GET /api/v1/projects/{project_id}/configs`
- [ ] `POST /api/v1/projects/{project_id}/configs/{id}/run` — запускает pipeline через GitLabClient
- [ ] `PATCH /api/v1/projects/{project_id}/configs/{id}/pipeline-status`
- [ ] `DELETE /api/v1/projects/{project_id}/configs/{id}`
- [ ] написать тесты: CRUD + run (mock gitlab)
- [ ] `uv run pytest tests/test_api_pipelines.py` — проходит

### Task 10: API — GitLab Router (schedules, branches, bookmarks)

**Files:**
- Create: `src/app/features/gitlab/router.py`
- Create: `src/app/features/gitlab/__init__.py`
- Create: `tests/test_api_gitlab.py`

- [ ] `GET /api/v1/gitlab/{project_id}/branches`
- [ ] `GET /api/v1/gitlab/{project_id}/schedules?q=...`
- [ ] `GET /api/v1/gitlab/{project_id}/schedules/{id}`
- [ ] `POST /api/v1/gitlab/{project_id}/schedules/{id}/run`
- [ ] `GET /api/v1/gitlab/{project_id}/pipelines/{id}`
- [ ] `GET /api/v1/projects/{project_id}/bookmarks`, `POST`, `DELETE /{id}`
- [ ] `POST /api/v1/gitlab/{project_id}/pipelines/{id}/allure` — запустить генерацию отчёта
- [ ] `GET /api/v1/gitlab/{project_id}/pipelines/{id}/allure/status`
- [ ] написать тесты (respx + mock middleware)
- [ ] `uv run pytest tests/test_api_gitlab.py` — проходит

### Task 11: FastAPI приложение (main.py)

**Files:**
- Create: `src/app/main.py`
- Create: `src/app/features/pipelines/router.py` (HTML страница)

- [ ] собрать `main.py` — lifespan, middleware (GitLabAuthMiddleware), mount static, include routers
- [ ] lifespan: `alembic upgrade head` через Alembic API (не subprocess)
- [ ] `GET /health` — без auth, для Docker healthcheck
- [ ] роутер HTML: `GET /` → редирект на первый проект или страницу добавления проекта
- [ ] проверить: `uv run python -m app.main` запускается

### Task 12: Docker

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] `Dockerfile` — multi-stage: 1) Python + uv install deps, 2) + Allure CLI (wget + OpenJDK)
- [ ] копировать `src/` и `config.json.example`
- [ ] `ENTRYPOINT ["uv", "run", "python", "-m", "app.main"]`
- [ ] `docker-compose.yml`:
  - volumes: `./data:/app/data` (data.db), `./allure_reports:/app/allure_reports`
  - ports: `8080:8080`
  - env_file или volumes config.json
- [ ] `.dockerignore`: `.venv`, `__pycache__`, `data.db`, `allure_reports/`, `tests/`
- [ ] проверить: `docker compose build` успешно
- [ ] проверить: `docker compose up` + `curl http://localhost:8080/health` → 200

### Task 13: HTML + Frontend (IndexedDB token storage)

**Files:**
- Create: `src/app/templates/base.html`
- Create: `src/app/templates/index.html` (setup / token input)
- Create: `src/app/templates/pipelines/index.html`
- Create: `src/app/static/js/auth.js` (IndexedDB + AES-256-GCM)
- Create: `src/app/static/js/htmx.min.js`
- Create: `src/app/static/js/pipelines.js`
- Create: `src/app/static/css/`

- [ ] `auth.js`:
  - Web Crypto API: PBKDF2 → AES-256-GCM key
  - `saveToken(token, masterPassword)` → IndexedDB
  - `loadToken(masterPassword)` → строка токена или null
  - при первом визите: показать форму ввода master password + GitLab token
- [ ] `base.html`: навигация с вкладками проектов, кнопка logout (очистка IndexedDB)
- [ ] `index.html`: форма добавления проекта (gitlab_project_id, display_name, allure_results_path optional)
- [ ] `pipelines/index.html`: список custom pipelines текущего проекта, кнопки run / allure
- [ ] убрать все ссылки на keycloak/allure testops/x5.ru
- [ ] smoke-тест: `GET /` возвращает 200 или 302

### Task 14: Финальная проверка

- [ ] `uv run pytest` — все тесты проходят
- [ ] `docker compose up` — сервис стартует
- [ ] `curl http://localhost:8080/health` → `{"status": "ok"}`
- [ ] `grep -r "x5.ru\|keycloak\|allure.x5" src/` — 0 результатов
- [ ] написать README: docker compose быстрый старт, настройка config.json
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
