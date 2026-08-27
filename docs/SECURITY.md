# Security and deployment

Hawk-Eye is **local-first**. Treat any network-exposed deployment as **production** and apply the controls below.

## Threat model (summary)

| Asset | Risk | Mitigation |
|-------|------|------------|
| User passwords | Offline cracking if DB leaked | **Argon2id** password hashes (legacy SHA-256 is upgraded on next successful login). |
| API keys | Replay if intercepted | **TLS** in front of the API; optional `HAWK_EYE_API_KEY_PEPPER`; revoke compromised keys. |
| Bearer tokens | Session hijack | HTTPS only; short-lived access tokens; refresh rotation; `POST /api/v1/auth/logout` / revoke-all. |
| SQLite file | Tampering or theft | Filesystem permissions; backups; optional encryption at rest (volume/disk). |

This is **not** a certified product security evaluation; adapt to your org’s standards.

## TLS

- **Development:** `http://127.0.0.1` is acceptable on a single machine.
- **Production:** terminate TLS at **nginx**, **Caddy**, or a cloud load balancer; do not expose the API over plain HTTP to untrusted networks.

## Authentication

- Passwords are stored with **Argon2id** (`passwords.hash_password`).
- **Legacy:** rows with SHA-256 hashes still work until the user logs in successfully, then the hash is replaced.
- **Production default admin:** when `HAWK_EYE_ENV=production`, the database does **not** seed `admin` / `admin123`. Set **`HAWK_EYE_INITIAL_ADMIN_PASSWORD`** on first boot (or create users with `scripts/seed_user.py`) and rotate immediately.

## Environment variables (security-related)

| Variable | Purpose |
|----------|---------|
| `HAWK_EYE_ENV` | Set to `production` to disable weak default admin seeding. |
| `HAWK_EYE_INITIAL_ADMIN_PASSWORD` | One-time password for seeding `admin` when `HAWK_EYE_ENV=production`. |
| `HAWK_EYE_API_KEY_PEPPER` | Optional secret prepended to raw API keys before hashing. **When set, existing API keys must be re-issued** (hashes are incompatible). |
| `HAWK_EYE_CORS_ORIGINS` | Comma-separated browser origins allowed for CORS (do not use `*` in production). |

See [ENVIRONMENT.md](ENVIRONMENT.md) for the full operator variable list.

## Supply chain

- Pin dependencies in [`pyproject.toml`](../pyproject.toml); review Dependabot PRs.
- Prefer `pip install -e ".[dev]"` from a locked environment for reproducible runs.

## Reporting vulnerabilities

Use the process in the repository root **[SECURITY.md](../SECURITY.md)** (GitHub Security Advisories or private disclosure). Do not post exploit details on public issues before a fix is coordinated.
