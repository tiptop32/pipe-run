# QA Pipe

A tool for QA engineers to manage GitLab CI pipelines, schedules, and generate Allure reports from artifacts. Runs locally via Docker and supports multi-user mode.

---

## ✨ Features

- Custom GitLab CI pipeline runs (saved configurations)
- GitLab pipeline schedules management (run, bookmarks)
- Allure report generation from GitLab artifacts
- Real-time pipeline status monitoring
- Multi-user support (single Docker instance)
- Multi-project support per user
- Local-first security (token stored in browser only)

---

## 🔐 Security

- GitLab token is stored only in browser (IndexedDB)
- Encrypted using AES-256-GCM + PBKDF2 (100k iterations)
- Server never stores tokens
- Each request sends `PRIVATE-TOKEN` directly to GitLab
- Users are isolated via `gitlab_user_id`

---

## 🚀 Quick Start (Docker)

### 1. Create config

```bash
cp config.example.json config.json
```

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

---

### 2. Create folders

```bash
mkdir -p data allure_reports
```

---

### 3. Start service

```bash
docker compose up -d
```

Service will be available at:

```
http://localhost:8080
```

---

## 🔑 First Login

You will be asked for:

- GitLab Personal Access Token
  - read_api
  - write_repository
- Master password (used to encrypt token in browser)

---

## 📊 Allure Reports

- Downloaded from GitLab artifacts
- Processed locally using Allure CLI
- Available in UI after pipeline completion

---

## ⚙️ Configuration

| Parameter | Default | Description |
|----------|---------|-------------|
| GITLAB_BASE_URL | https://gitlab.com | GitLab instance URL |
| REPORTS_DIR | /app/allure_reports | Reports directory |
| DATABASE_URL | sqlite+aiosqlite:///data.db | Database connection |
| HOST | 0.0.0.0 | Server host |
| PORT | 8080 | Server port |
| LOGLEVEL | INFO | Logging level |

---

## 🧩 Features Overview

| Feature | Description |
|--------|-------------|
| Pipelines | Saved pipeline configurations |
| Schedules | Manage GitLab schedules |
| Bookmarks | Favorite schedules |
| Allure | HTML report generation |
| Monitoring | Pipeline status tracking |

---

## 🏗 Architecture

```
Browser (SPA)
    │
    │  PRIVATE-TOKEN (AES encrypted in IndexedDB)
    ▼
FastAPI Backend
    │
    ├── GitLab API integration
    ├── SQLite (async)
    ├── Allure CLI
    ▼
GitLab CI
```

---

## 🧠 Auth Flow

1. Token stored in browser (IndexedDB + AES-256-GCM)
2. Decrypted in memory per request
3. Sent via `PRIVATE-TOKEN` header
4. Backend validates via GitLab `/user`
5. All data scoped by `gitlab_user_id`

---

## 🗄 Database Schema

- user_projects — user GitLab projects
- custom_pipelines — saved pipeline configurations
- schedule_bookmarks — bookmarked schedules
- allure_reports — report generation status

---

## 🧪 Local Development

```bash
uv sync

uv run alembic upgrade head

uv run uvicorn app.main:app --reload --port 8080
```

---

## 📁 Project Structure

```
src/app/
  auth/        — GitLab authentication middleware
  conf/        — configuration layer
  db/          — database + migrations
  features/
    pipelines/ — pipelines + Allure logic
    gitlab/    — GitLab API client
    projects/  — project management
  static/      — SPA frontend
  templates/   — HTML entrypoint
  main.py
```

---

## 🔌 API

### Projects

- GET `/api/v1/projects`
- POST `/api/v1/projects`
- DELETE `/api/v1/projects/{id}`

### Pipelines

- GET `/api/v1/projects/{id}/configs`
- POST `/api/v1/projects/{id}/configs`
- POST `/run`
- DELETE `/configs/{id}`

### GitLab Integration

- Branches
- Schedules
- Pipelines
- Allure report generation

---

## 📄 License

MIT

