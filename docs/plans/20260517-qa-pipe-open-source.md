# QA Pipe — Open Source Edition

## Overview

Создание открытого инструмента для QA-инженеров на базе qa-tools, без корпоративных зависимостей (Keycloak, Allure TestOps, X5-инфраструктура). Инструмент запускается через `uv run`, хранит данные в SQLite, работает с любым GitLab-инстансом.

**Проблема:** qa-tools жёстко привязан к X5-инфраструктуре (Keycloak, scm.x5.ru, allure.x5.ru) и не пригоден для внешнего использования.

**Решение:** адаптировать кодовую базу qa-tools — убрать всё корпоративное, упростить конфиг до `config.json`, убрать мультипользовательность.

**Acceptance criteria:**
- `uv run qa-pipe` запускается без ошибок
- Создание custom pipeline и просмотр статуса работает
- Генерация Allure отчёта из артефактов GitLab работает
- Все тесты проходят
- Нет hardcoded X5 URL/токенов в репо

## Context (from discovery)

- **Источник:** `/Volumes/My Shared Files/x5/git_reps/qa-tools/` — FastAPI + SQLAlchemy async + aiosqlite + Alembic
- **Целевой репо:** `/Volumes/My Shared Files/git_reps/qa-pipe/` — сейчас пустой
- **Удаляем:** `auth/`, `allure_fetcher.py`, `PipelineAllureCache` модель, Keycloak config, X5-specific `get_recent_pipelines_with_tests`
- **Удаляем:** `py-configurator` (внутренний X5-пакет) → простой JSON + env лоадер
- **Сохраняем:** `features/pipelines/` (Custom pipelines, allure_report.py), `features/gitlab/` (GitLab httpx клиент)
- **Решение по logging:** переписываем `logging.py` без `asgi-correlation-id` и `common/formatters/` (упрощение)
- **Решение по Alembic vs create_all:** убираем `create_all` из lifespan, запускаем `alembic upgrade head` при старте
- **Решение по verify=False:** добавляем `GITLAB_VERIFY_SSL: bool = True` в конфиг
- **Решение по ALLURE_RESULTS_PATH:** удаляем из конфига; вместо этого добавляем `REPORTS_DIR` (путь к папке где хранятся Allure отчёты, default `./allure_reports`)
- **Решение по tools/ feature:** переносим (`/tools/` — простая страница инструментов)
- **Примечание:** `python-gitlab` — sync-only, несовместима с async FastAPI. Оставляем httpx-клиент

## Development Approach

- **Testing approach:** Regular (код → потом тесты)
- Реализуем по одному модулю, начиная с фундамента (конфиг → БД → клиент → API → UI)
- После каждой задачи запускаем `uv run pytest`
- Обратная совместимость с qa-tools не нужна

## Testing Strategy

- **Unit tests:** конфиг-лоадер, CRUD, Allure report статусы
- **Integration:** GitLab клиент через `respx` (mock httpx), API эндпоинты через `AsyncClient`
- **async тесты:** `asyncio_mode = "auto"` в pyproject.toml, `conftest.py` с in-memory SQLite фикстурой
- **E2E:** не планируются
- Test command: `uv run pytest`

## Progress Tracking

- Отмечаем `[x]` сразу после завершения
- ➕ для новых задач, ⚠️ для блокеров

## Solution Overview

Копируем структуру qa-tools, удаляем всё корпоративное, упрощаем. Ключевые изменения:

1. `py-configurator` → `config_loader.py` (json + env override, Pydantic Settings)
2. `auth/` → удаляется полностью, все `Depends(get_current_user)` убираем
3. `user_id` → убирается из всех моделей и CRUD
4. `PipelineAllureCache` + `allure_fetcher.py` → удаляем
5. GitLabClient → убираем `project_path`, `bot_display_name`; добавляем `verify_ssl`; удаляем `get_recent_pipelines_with_tests`
6. `logging.py` → переписываем без `asgi-correlation-id` и JSON-formatter
7. Lifespan: `alembic upgrade head` вместо `create_all`
8. UI: убираем auth-блоки, allure TestOps ссылки, allure_cache из ответов

## Technical Details

**Конфиг (`config.json`):**
```json
{
  "GITLAB_BASE_URL": "https://gitlab.com",
  "GITLAB_TOKEN": "glpat-xxx",
  "GITLAB_PROJECT_ID": 123,
  "GITLAB_VERIFY_SSL": true,
  "REPORTS_DIR": "./allure_reports",
  "DATABASE_URL": "sqlite+aiosqlite:///./data.db",
  "HOST": "0.0.0.0",
  "PORT": 8080,
  "LOGLEVEL": "INFO"
}
```

**Модели БД (упрощённые):**
- `CustomPipeline`: без `user_id`; поля: id, project_id, name, ref, variables, seeded_from_schedule_id, last_pipeline_id, last_pipeline_status, last_run_at, created_at, updated_at
- `ScheduleBookmark`: без `user_id`; поля: id, project_id, schedule_id, display_name, created_at
- `PipelineAllureCache`: **удаляем полностью**
- `db/models.py`: агрегатор импортов (нужен для регистрации метаданных в Alembic)

**pyproject.toml — зависимости:**
- Убираем: `asyncpg`, `py-configurator`, X5 Artifactory index, `orjson`, `PyYAML`
- Добавляем: `python-dotenv`
- Оставляем: `fastapi`, `uvicorn`, `httpx`, `sqlalchemy[asyncio]`, `aiosqlite`, `alembic`, `jinja2`, `aiofiles`, `python-multipart`, `asgi-correlation-id` (опционально, убрать в logging-задаче)
- Dev: `pytest`, `pytest-asyncio`, `respx`

**Статические файлы для переноса:**
- `static/js/htmx.min.js`
- `static/pipelines.js` (или `static/js/pipelines.js`)
- `static/css/` (все файлы)
- `static/allure_reports/.gitkeep` (создать пустую директорию)

## What Goes Where

**Implementation Steps** — всё ниже реализуется в этом репо.

**Post-Completion:**
- Ручное тестирование с реальным GitLab
- Убедиться что `data.db` сохраняется между перезапусками
- Опубликовать репо (проверить что нет X5 URL/токенов)

## Implementation Steps

### Task 1: Bootstrap — структура, pyproject.toml, pytest конфиг

**Files:**
- Create: `pyproject.toml`
- Create: `pytest.ini` (или секция в pyproject.toml)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `src/app/__init__.py`
- Create: `.gitignore`
- Create: `alembic.ini`

- [ ] создать структуру директорий: `src/app/{conf,db,features/{pipelines,gitlab,tools},static,templates}`, `tests/`
- [ ] создать `pyproject.toml`: убрать asyncpg / py-configurator / orjson / PyYAML / X5 индекс; добавить python-dotenv; dev deps: pytest, pytest-asyncio, respx
- [ ] добавить в pyproject.toml: `[tool.pytest.ini_options] asyncio_mode = "auto"`
- [ ] создать `alembic.ini` (стандартный, DATABASE_URL через env var `QA_PIPE_DB_URL`)
- [ ] создать `tests/conftest.py` с in-memory SQLite фикстурой (`async_session`)
- [ ] создать `.gitignore` (data.db, config.json, __pycache__, .venv, allure_reports/)
- [ ] проверить `uv sync` — зависимости устанавливаются без ошибок
- [ ] smoke-тест: `uv run python -c "import app"` проходит
- [ ] `uv run pytest` — 0 тестов, 0 ошибок

### Task 2: Модуль конфигурации

**Files:**
- Create: `src/app/conf/__init__.py`
- Create: `src/app/conf/config_loader.py`
- Create: `src/app/conf/config_model.py`
- Create: `src/app/conf/logging.py`
- Create: `config.example.json`
- Create: `tests/test_config.py`

- [ ] создать `config_model.py` — Pydantic `Settings` с полями: GITLAB_BASE_URL, GITLAB_TOKEN, GITLAB_PROJECT_ID, GITLAB_VERIFY_SSL (default True), REPORTS_DIR (default "./allure_reports"), DATABASE_URL, HOST, PORT, LOGLEVEL; без Keycloak/AllureTestOps/SecretStr
- [ ] создать `config_loader.py` — читает `config.json` из CWD, env vars как override (prefix `QA_PIPE_`); без py-configurator
- [ ] переписать `logging.py` — стандартный logging без `asgi-correlation-id` и JSONFormatter (plain text handler достаточно)
- [ ] создать `config.example.json` с примером всех полей
- [ ] написать тесты: загрузка из JSON-файла, override через env var, ошибка на отсутствующий GITLAB_TOKEN
- [ ] `uv run pytest tests/test_config.py` — проходит

### Task 3: База данных — модели, агрегатор, Alembic

**Files:**
- Create: `src/app/db/__init__.py`
- Create: `src/app/db/base.py`
- Create: `src/app/db/models.py`
- Create: `src/app/db/migrations/env.py`
- Create: `src/app/db/migrations/script.py.mako`
- Create: `src/app/db/migrations/versions/0001_initial.py`
- Create: `src/app/features/pipelines/models.py`
- Create: `tests/test_db.py`

- [ ] перенести `db/base.py` — обновить: DATABASE_URL из `config.DATABASE_URL` (plain str, без SecretStr); убрать asyncpg; оставить aiosqlite
- [ ] создать `features/pipelines/models.py` — `CustomPipeline` и `ScheduleBookmark` **без** `user_id`; `PipelineAllureCache` **не создавать**; все поля согласно Technical Details
- [ ] создать `db/models.py` — только импорты моделей (нужен для регистрации в Base.metadata)
- [ ] настроить Alembic `env.py` для async SQLite (async engine в `run_migrations_online`)
- [ ] создать первую миграцию `0001_initial.py` с обеими таблицами
- [ ] написать тест: применить `alembic upgrade head` к in-memory SQLite, проверить что таблицы существуют
- [ ] `uv run pytest tests/test_db.py` — проходит

### Task 4: CRUD операции

**Files:**
- Create: `src/app/features/pipelines/crud.py`
- Create: `src/app/features/pipelines/schemas.py`
- Create: `tests/test_crud.py`

- [ ] перенести `crud.py` из qa-tools — убрать все параметры `user_id` из функций; убрать `allure_cache_to_dict`, `get_allure_cache`, `upsert_allure_cache`
- [ ] аудит сигнатур: `update_custom_pipeline`, `get_schedule_bookmark`, `delete_schedule_bookmark`, `delete_custom_pipeline` — все вызовы без `user_id`
- [ ] перенести `schemas.py` — убрать `user_id` из всех схем; убрать все Allure TestOps поля
- [ ] написать тесты: create/list/update/delete для `CustomPipeline` и `ScheduleBookmark` (async, in-memory SQLite через conftest фикстуру)
- [ ] `uv run pytest tests/test_crud.py` — проходит

### Task 5: GitLab API клиент

**Files:**
- Create: `src/app/features/pipelines/gitlab.py`
- Create: `tests/test_gitlab_client.py`

- [ ] перенести `gitlab.py` из qa-tools
- [ ] убрать параметры `project_path`, `bot_display_name` из `__init__`
- [ ] добавить `verify_ssl: bool = True` — передавать в `httpx.AsyncClient(verify=verify_ssl)`
- [ ] **удалить** `get_recent_pipelines_with_tests` (X5-специфичный метод с `_BOT_PATTERN`, "prepare" job, ENV/PYTEST_MARKS переменными)
- [ ] убрать любые `verify=False` hardcode
- [ ] написать тесты через `respx`: `run_pipeline` (success, GitLabAPIError), `get_schedule`, `download_job_artifacts`, `get_jobs`
- [ ] `uv run pytest tests/test_gitlab_client.py` — проходит

### Task 6: Allure Report генератор

**Files:**
- Create: `src/app/features/pipelines/allure_report.py`
- Create: `tests/test_allure_report.py`

- [ ] перенести `allure_report.py` из qa-tools
- [ ] заменить hardcoded `REPORTS_DIR` — брать из `config.REPORTS_DIR` (Path)
- [ ] убрать зависимость на `GitLabClient` из сигнатуры (передавать явно или создавать через config внутри)
- [ ] написать тесты: `report_status` (все 4 статуса), `_extract_allure_results` с реальным in-memory zip
- [ ] `uv run pytest tests/test_allure_report.py` — проходит

### Task 7a: API эндпоинты — Custom Pipelines

**Files:**
- Create: `src/app/features/pipelines/api.py`
- Create: `src/app/features/pipelines/__init__.py`
- Create: `tests/test_api_pipelines.py`

- [ ] перенести `features/pipelines/api.py` из qa-tools
- [ ] убрать все `Depends(get_current_user)` и `UserSession`
- [ ] убрать `fetch_and_cache_allure` вызовы и `allure_cache` из ответов `configs_enriched`
- [ ] убрать `allure_cache` из ответов (поле `allure_cache: null` не нужно)
- [ ] проверить что `PATCH /configs/{id}/pipeline-status` остаётся (нужен для опроса статуса)
- [ ] написать тесты: POST /configs (создание), GET /configs (список), POST /configs/{id}/run (mock gitlab), DELETE /configs/{id}
- [ ] `uv run pytest tests/test_api_pipelines.py` — проходит

### Task 7b: API эндпоинты — GitLab Router

**Files:**
- Create: `src/app/features/gitlab/router.py`
- Create: `src/app/features/gitlab/__init__.py`
- Create: `tests/test_api_gitlab.py`

- [ ] перенести `features/gitlab/router.py` из qa-tools
- [ ] убрать все `Depends(get_current_user)` и `UserSession`
- [ ] **удалить** `GET /api/v1/gitlab/pipelines` (опирался на X5-специфичный `get_recent_pipelines_with_tests`)
- [ ] **удалить** `GET /api/v1/gitlab/pipelines/{id}/allure` (Allure TestOps кэш)
- [ ] оставить: `/schedules`, `/schedules/{id}`, `/branches`, `/pipelines/{id}` (get one pipeline)
- [ ] добавить bookmarks `/schedule-bookmarks` endpoints (перенести из api.py если они там остались)
- [ ] написать тесты: GET /schedules?q=..., GET /branches (mock httpx через respx)
- [ ] `uv run pytest tests/test_api_gitlab.py` — проходит

### Task 8: FastAPI приложение (main.py)

**Files:**
- Create: `src/app/main.py`

- [ ] собрать `main.py` — lifespan, middleware, mount static, include routers
- [ ] убрать `auth_router`, убрать `allure_fetcher` импорты
- [ ] **в lifespan**: запускать `alembic upgrade head` subprocess (или через Alembic API) вместо `Base.metadata.create_all`
- [ ] создать `src/app/features/pipelines/router.py` — HTML страница, без `get_current_user`, без `allure_base_url` в контексте
- [ ] создать `src/app/features/tools/router.py` — простая страница инструментов
- [ ] проверить: `uv run python -m app.main` запускается, `curl http://localhost:8080/` отвечает 303

### Task 9: HTML шаблоны, статика и UI

**Files:**
- Create: `src/app/templates/base.html`
- Create: `src/app/templates/pipelines/index.html`
- Create: `src/app/templates/tools/index.html`
- Create: `src/app/static/js/htmx.min.js`
- Create: `src/app/static/js/pipelines.js` (или где лежит)
- Create: `src/app/static/css/` (все файлы)
- Create: `src/app/static/allure_reports/.gitkeep`
- Create: `tests/test_ui_smoke.py`

- [ ] скопировать все статические файлы: `htmx.min.js`, `pipelines.js`, `css/*`
- [ ] создать `static/allure_reports/.gitkeep` для пустой папки отчётов
- [ ] перенести и адаптировать шаблоны: убрать блок авторизации/пользователя из навигации
- [ ] убрать ссылки на Allure TestOps (`allure.x5.ru`) из карточек
- [ ] убрать блоки `allure_cache` (статистика тестов из Allure TestOps)
- [ ] убрать `allure_base_url` из контекста шаблонов
- [ ] написать smoke-тест: `GET /pipelines/` возвращает 200 через `AsyncClient`
- [ ] `uv run pytest tests/test_ui_smoke.py` — проходит
- [ ] вручную открыть в браузере: карточки рендерятся, кнопки работают

### Task 10: Финальная проверка

**Files:**
- Modify: `README.md`

- [ ] запустить полный `uv run pytest` — все тесты проходят
- [ ] запустить `uv run python -m app.main`, открыть `http://localhost:8080`
- [ ] проверить happy path: создать custom pipeline → запустить → дождаться статуса → нажать Generate Allure
- [ ] проверить: нет `x5.ru`, `allure.x5.ru`, `scm.x5.ru` в коде (`grep -r "x5.ru" src/`)
- [ ] написать README: требования (Python 3.11+, uv, allure CLI), шаги установки, настройка config.json
- [ ] переместить план в `docs/plans/completed/`

## Post-Completion

**Ручная проверка:**
- Протестировать с реальным GitLab (gitlab.com или self-hosted)
- Убедиться что `data.db` сохраняется между перезапусками
- Проверить генерацию Allure отчёта с реальными артефактами пайплайна

**Внешние шаги:**
- Проверить видимость репо перед публикацией (убрать test-токены)
- Настроить GitHub Actions для CI (опционально)
