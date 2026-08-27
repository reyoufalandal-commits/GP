# Sessions, JWT, and API keys

This document summarizes **browser session** behavior and **API keys** for scripts. It reflects the current FastAPI implementation in `src/hawk_eye/backend/routes.py`.

## Browser session (login)

| Token | Lifetime | Notes |
|-------|-----------|--------|
| **Access token** | ~24 hours from issue | Sent as `Authorization: Bearer …` on API calls. |
| **Refresh token** | ~30 days | Used by the dashboard to obtain a new access/refresh pair (`POST /api/v1/auth/refresh`). Each refresh **rotates** the refresh token (old one is revoked). |

- **Logout (`POST /api/v1/auth/logout`)** revokes the current access token.
- **Revoke all (`POST /api/v1/auth/revoke-all`)** revokes refresh tokens for the user — use if credentials may be compromised; forces sign-in everywhere.

The **Session** page in the dashboard documents the same controls.

## API keys (`X-API-Key`)

Long-lived keys for automation are hashed server-side (with optional `HAWK_EYE_API_KEY_PEPPER`). Treat them like passwords: store only in secret managers or CI variables, not in git.

## SSO / enterprise IdP

Native SAML/OIDC **inside** this API is **not** implemented. Typical pattern: terminate TLS and authentication at a **reverse proxy** (OIDC, OAuth2 proxy, or corporate IdP) and only expose the API on a trusted network. See [ROADMAP.md](ROADMAP.md) for scope.

## Related

- [ENVIRONMENT.md](ENVIRONMENT.md) — env vars including rate limits and logging.
- [SECURITY.md](../SECURITY.md) — reporting issues.
