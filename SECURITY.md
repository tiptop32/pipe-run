# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| latest  | ✅        |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please email **nexus32t@gmail.com** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- (optional) Suggested fix

You will receive a response within 72 hours.  
We will coordinate a fix and disclose the issue responsibly after a patch is released.

## Security design notes

- GitLab tokens are stored **only in the browser** (IndexedDB, AES-256-GCM + PBKDF2 600 000 iterations)
- The server never persists tokens — it receives them per-request in `PRIVATE-TOKEN` header
- All user data in the database is isolated by `gitlab_user_id`
- The Docker image runs as a non-root user
