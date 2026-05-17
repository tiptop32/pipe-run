# QA Pipe

Инструмент для QA-инженеров: запуск GitLab CI пайплайнов, управление расписаниями и генерация Allure-отчётов из артефактов. Разворачивается через Docker, поддерживает несколько пользователей.

## Ключевые особенности

- **Local-First безопасность** — GitLab токен хранится в браузере (IndexedDB, AES-256-GCM + PBKDF2), на сервер не передаётся и нигде не сохраняется
- **Мультипользовательский** — один Docker-инстанс для всей команды, каждый авторизуется своим токеном
- **Мультипроектный** — каждый пользователь добавляет нужные GitLab-проекты как вкладки

## Что умеет

| Функция | Описание |
|---------|----------|
| Custom Pipelines | Сохраняйте конфигурации пайплайнов (ветка + переменные) и запускайте в один клик |
| Расписания | Просматривайте и запускайте GitLab pipeline schedules |
| Закладки расписаний | Сохраняйте часто используемые расписания |
| Allure-отчёты | Скачивает артефакты из GitLab, генерирует HTML-отчёт локально |
| Мониторинг статуса | Автообновление статуса запущенного пайплайна |

---

## Быстрый старт (Docker)

### 1. Подготовьте `config.json`

```bash
cp config.example.json config.json
```

Отредактируйте:

```json
{
  "GITLAB_BASE_URL": "https://gitlab.com",
  "REPORTS_DIR": "/app/allure_reports",
  "DATABASE_URL": "sqlite+aiosqlite:////app/data/data.db",
  "HOST": "0.0.0.0",
  "PORT": 8080,
  "LOGLEVEL": "INFO"
}
```

> `GITLAB_BASE_URL` — адрес вашего GitLab (self-hosted или `https://gitlab.com`).
> Остальные параметры можно оставить как есть при использовании Docker.

### 2. Создайте папки для данных

```bash
mkdir -p data allure_reports
```

### 3. Запустите

```bash
docker compose up -d
```

Сервис доступен по адресу **http://localhost:8080**

### 4. Первый вход

При первом открытии браузер попросит:

1. **GitLab токен** — создайте Personal Access Token в GitLab (Settings → Access Tokens), с правами `read_api` и `write_repository`
2. **Мастер-пароль** — произвольный пароль для шифрования токена в браузере

Токен зашифруется AES-256-GCM с PBKDF2 (100 000 итераций) и сохранится в IndexedDB браузера. Сервер его **не хранит** — получает только в заголовке каждого запроса.

### 5. Добавьте проект

После входа нажмите `+` и введите:

- **GitLab Project ID** — найдите на странице проекта (Settings → General → Project ID)
- **Название вкладки** — произвольное имя
- **Путь к Allure results** (опционально) — путь внутри ZIP-архива артефактов, например `allure-results`. Если не указать, кнопка Allure не появится

---

## Локальный запуск (без Docker)

### Требования

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — менеджер пакетов
- Allure CLI (только для генерации отчётов): [скачать](https://allurereport.org/docs/install/)

### Установка

```bash
git clone https://github.com/yourname/qa-pipe.git
cd qa-pipe

# Установить зависимости
uv sync

# Создать конфиг
cp config.example.json config.json
# Отредактируйте config.json — укажите GITLAB_BASE_URL

# Применить миграции БД
uv run alembic upgrade head

# Запустить
uv run qa-pipe
```

Сервис будет доступен по адресу `http://localhost:8080`

---

## Архитектура

```
Browser                          Server                        GitLab
───────                          ──────                        ──────
IndexedDB                        FastAPI + SQLite
  └─ token (AES-256-GCM)
        │
        │  PRIVATE-TOKEN: glpat-xxx  (каждый запрос)
        ├────────────────────────────►  Auth Middleware
        │                                └─ GET /api/v4/user ──────► GitLab
        │                                └─ user_id → request.state
        │
        │  GET /api/v1/projects          
        ├────────────────────────────►  Projects Router
        │◄────────────────────────────  [user_projects WHERE user_id=N]
        │
        │  POST /api/v1/.../configs/run
        ├────────────────────────────►  Pipelines API
        │                                └─ POST /projects/{id}/pipeline ──► GitLab
        │◄────────────────────────────  {pipeline_id, status}
```

### Auth flow (stateless)

1. Браузер хранит токен в IndexedDB (зашифрован мастер-паролем)
2. При каждом API-запросе браузер расшифровывает токен в памяти и отправляет в заголовке `PRIVATE-TOKEN`
3. Middleware проверяет токен через `GET /api/v4/user` и получает `gitlab_user_id`
4. Все данные в БД привязаны к `gitlab_user_id` — пользователи изолированы

Сервер **не хранит** токены. Если сессия истекла — браузер спрашивает мастер-пароль снова.

### База данных (SQLite)

```
user_projects         — проекты пользователей (gitlab_project_id, display_name, allure_results_path)
custom_pipelines      — сохранённые конфигурации пайплайнов (ref, variables)
schedule_bookmarks    — закладки на pipeline schedules
allure_reports        — статус генерации Allure-отчётов (not_started / pending / ready / error)
```

---

## Конфигурация сервера

Файл `config.json` в рабочей директории (все поля опциональны, есть дефолты):

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `GITLAB_BASE_URL` | `https://gitlab.com` | Адрес GitLab |
| `REPORTS_DIR` | `./allure_reports` | Путь для хранения Allure-отчётов |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data.db` | URL базы данных |
| `HOST` | `0.0.0.0` | Адрес для прослушивания |
| `PORT` | `8080` | Порт |
| `LOGLEVEL` | `INFO` | Уровень логирования (`DEBUG`, `INFO`, `WARNING`) |

Все параметры можно переопределить переменными окружения с префиксом `QA_PIPE_`:

```bash
QA_PIPE_LOGLEVEL=DEBUG docker compose up
```

---

## GitLab токен

Создайте Personal Access Token в GitLab: **Settings → Access Tokens → Add new token**

Необходимые права:
- `read_api` — чтение пайплайнов, расписаний, веток
- `write_repository` — запуск пайплайнов (если репозиторий protected)

Токен создаётся **один раз** и хранится в вашем браузере. При смене браузера или устройства нужно ввести токен заново.

---

## Allure-отчёты

Для работы Allure в Docker — всё включено в образ (Allure CLI + OpenJDK).

При локальном запуске установите Allure CLI отдельно:

```bash
# macOS
brew install allure

# Linux (wget)
wget https://github.com/allure-framework/allure2/releases/download/2.27.0/allure-2.27.0.zip
unzip allure-2.27.0.zip -d /opt
ln -s /opt/allure-2.27.0/bin/allure /usr/local/bin/allure
```

### Как работает генерация

1. При создании проекта укажите **Путь к Allure results** — это путь к папке с JSON-файлами внутри ZIP-артефакта пайплайна (например: `allure-results` или `artifacts/allure-results`)
2. После успешного запуска пайплайна появится кнопка 📊 **Allure**
3. Сервер скачает артефакты, распакует нужную директорию и запустит `allure generate`
4. Отчёт будет доступен по `/static/allure_reports/{pipeline_id}/index.html`

---

## Разработка

```bash
# Установить зависимости (включая dev)
uv sync

# Запустить тесты
uv run pytest

# Запустить с авто-перезагрузкой
uv run uvicorn app.main:app --reload --port 8080

# Создать новую миграцию после изменения моделей
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

### Структура проекта

```
src/app/
├── auth/
│   ├── middleware.py     — GitLabAuthMiddleware (PRIVATE-TOKEN → user_id)
│   └── deps.py          — FastAPI dependencies (get_current_user, get_gitlab_token)
├── conf/
│   ├── config_model.py  — Pydantic Settings
│   ├── config_loader.py — загрузка config.json + env vars
│   └── logging.py       — настройка логирования
├── db/
│   ├── base.py          — AsyncEngine, async_session_factory
│   ├── models.py        — агрегатор импортов моделей
│   └── migrations/      — Alembic миграции
├── features/
│   ├── pipelines/
│   │   ├── models.py       — UserProject, CustomPipeline, ScheduleBookmark, AllureReport
│   │   ├── crud.py         — CRUD операции
│   │   ├── schemas.py      — Pydantic схемы запросов/ответов
│   │   ├── gitlab.py       — GitLabClient (httpx)
│   │   ├── api.py          — /api/v1/projects/{id}/configs роутер
│   │   └── allure_report.py — генерация Allure-отчётов
│   ├── gitlab/
│   │   └── router.py    — /api/v1/gitlab/{project_id}/... (branches, schedules, pipelines)
│   └── projects/
│       ├── router.py    — /api/v1/projects CRUD
│       └── schemas.py
├── static/
│   ├── js/
│   │   ├── auth.js      — IndexedDB + AES-256-GCM (Web Crypto API)
│   │   └── app.js       — логика SPA (проекты, пайплайны, polling)
│   └── css/style.css
├── templates/index.html  — SPA-оболочка
└── main.py              — FastAPI app, lifespan, routers
```

### Тесты

```
tests/
├── test_config.py          — конфиг-лоадер
├── test_db.py              — схема БД (таблицы, колонки)
├── test_crud.py            — CRUD (in-memory SQLite)
├── test_gitlab_client.py   — GitLabClient (respx mock)
├── test_auth.py            — middleware (respx mock)
├── test_allure_report.py   — генерация отчётов
├── test_api_projects.py    — Projects API
├── test_api_pipelines.py   — Pipelines API
└── test_api_gitlab.py      — GitLab Router + Bookmarks API
```

---

## API

Swagger UI доступен по адресу `http://localhost:8080/docs`

### Projects

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/projects` | Список проектов пользователя |
| `POST` | `/api/v1/projects` | Добавить проект |
| `DELETE` | `/api/v1/projects/{id}` | Удалить проект |

### Custom Pipelines

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/projects/{project_id}/configs` | Список конфигураций |
| `POST` | `/api/v1/projects/{project_id}/configs` | Создать конфигурацию |
| `PUT` | `/api/v1/projects/{project_id}/configs/{id}` | Обновить |
| `DELETE` | `/api/v1/projects/{project_id}/configs/{id}` | Удалить |
| `POST` | `/api/v1/projects/{project_id}/configs/{id}/run` | Запустить пайплайн |
| `PATCH` | `/api/v1/projects/{project_id}/configs/{id}/pipeline-status` | Обновить статус |

### GitLab

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/gitlab/{project_id}/branches` | Список веток |
| `GET` | `/api/v1/gitlab/{project_id}/schedules` | Расписания (`?q=` для поиска) |
| `GET` | `/api/v1/gitlab/{project_id}/schedules/{id}` | Детали расписания |
| `POST` | `/api/v1/gitlab/{project_id}/schedules/{id}/run` | Запустить по расписанию |
| `GET` | `/api/v1/gitlab/{project_id}/pipelines/{id}` | Детали пайплайна |
| `POST` | `/api/v1/gitlab/{project_id}/pipelines/{id}/allure` | Сгенерировать отчёт |
| `GET` | `/api/v1/gitlab/{project_id}/pipelines/{id}/allure/status` | Статус отчёта |

### Bookmarks

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/projects/{project_id}/bookmarks` | Закладки расписаний |
| `POST` | `/api/v1/projects/{project_id}/bookmarks` | Добавить закладку |
| `DELETE` | `/api/v1/projects/{project_id}/bookmarks/{id}` | Удалить закладку |

---

## Безопасность токена

Схема шифрования:

```
master_password + random_salt(16 bytes)
        │
        ▼ PBKDF2-SHA256, 100 000 итераций
    AES-256 key
        │
        ▼ AES-GCM, random_iv(12 bytes)
  encrypted_token → IndexedDB
```

- Мастер-пароль **никуда не отправляется** и нигде не хранится
- Если забыли мастер-пароль — нажмите «Выйти» (сбросит токен) и введите токен заново
- Каждый браузер/устройство хранит свою копию зашифрованного токена

---

## Лицензия

MIT
