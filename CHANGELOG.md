# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-17

### Added

- Local-first architecture: GitLab token stored in browser IndexedDB (AES-256-GCM + PBKDF2 600 000 iterations)
- Multi-user support via `gitlab_user_id` isolation in SQLite
- Multi-project tabs — each user adds their own GitLab projects
- Custom Pipelines: save branch + variables configurations, run in one click
- Pipeline schedule viewer with bookmarks
- Allure report generation from GitLab job artifacts (Docker includes Allure CLI + JDK)
- Pipeline status polling with auto-refresh
- Docker Compose deployment with SQLite persistence via volume
- Auth middleware: stateless per-request token validation with 60-second TTL cache
- GitHub Actions CI (test) and Docker publish workflows
