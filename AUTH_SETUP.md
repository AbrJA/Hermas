# Auth0 Integration Guide

This document explains the new Auth0 and per-user scoping implementation for Hermas.

## Overview

**Version 2.0 of Hermas** adds production-grade authentication and strict per-user resource isolation:

- ✅ **Auth0 JWT support** – Stateless, distributed-ready authentication
- ✅ **Per-user skills** – Each user owns their own skill library
- ✅ **Per-user MCP servers** – Each user manages their own tool integrations
- ✅ **Global skill fallback** – Shared read-only skills available to all users
- ✅ **Safe DB migrations** – Automatic composite PK upgrade on first boot
- ✅ **Zero breaking changes** (for classic deploy) – Legacy session mode still supported

## Quick Start: Session Mode (Legacy, Default)

No change required. Existing deployments continue to work:

```bash
HERMAS_REQUIRE_AUTH=false       # Or true to enforce
HERMAS_AUTH_PROVIDER=session    # Default
HERMAS_APP_API_TOKEN=your-token
HERMAS_SESSION_TTL_SECONDS=86400
```

## Quick Start: Auth0 (Recommended)

### 1. Create Auth0 Application

1. Sign up for [Auth0.com](https://auth0.com)
2. Create a new **Machine-to-Machine** or **Regular Web App** application
3. Note:
   - **Domain** (e.g., `example.auth0.com`)
   - **Client ID / API Audience** (use as `HERMAS_AUTH0_AUDIENCE`)
4. Create an API resource if needed:
   - **Identifier** = `https://your-api.example.com` (or custom value)
   - This becomes `HERMAS_AUTH0_AUDIENCE`

### 2. Configure Hermas

```bash
# .env
HERMAS_REQUIRE_AUTH=true
HERMAS_AUTH_PROVIDER=auth0
HERMAS_AUTH0_DOMAIN=example.auth0.com
HERMAS_AUTH0_AUDIENCE=https://your-api.example.com
HERMAS_AUTH0_ISSUER=https://example.auth0.com/
HERMAS_AUTH0_ALGORITHM=RS256
HERMAS_AUTH0_JWKS_CACHE_TTL_SECONDS=600
```

### 3. Obtain User Token

```bash
# Get access token from Auth0
curl --request POST \
  --url https://example.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_SECRET","audience":"https://your-api.example.com","grant_type":"client_credentials"}'
```

### 4. Call API with Bearer Token

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "gpt-4o-mini",
    "selectedSkillIds": [],
    "mcpServerIds": [],
    "autoSkillRouting": true
  }'
```

## Per-User Resource Scoping

### Skills

**API:**
- `GET /api/skills` – List authenticated user's skills + global shared skills
- `POST /api/skills` – Create skill owned by authenticated user
- `DELETE /api/skills/{skill_id}` – Delete if user is owner

**Database:**
```sql
-- Composite primary key prevents ID collisions
CREATE TABLE skills (
  id VARCHAR(128),
  user_id VARCHAR(128),
  ...
  PRIMARY KEY (id, user_id)
);

-- Two users can both have "summarizer" skill, but they own separate copies
alice | summarizer | Alice's instructions
bob   | summarizer | Bob's instructions
__global__ | summarizer | Shared global skill
```

**User preference:**
- If user has own skill: use their version
- Else if global skill exists: use shared version
- Else: not found

### MCP Servers

**API:**
- `GET /api/mcp/servers` – List servers owned by authenticated user
- `POST /api/mcp/servers` – Register server for authenticated user
- `POST /api/mcp/tools?serverId=X` – List tools from user's server (checked against DB)
- `POST /api/mcp/call` – Execute tool from user's server only

**Payload Change:**
```javascript
// OLD (before v2.0):
{
  mcpServers: [{ name, url, auth... }]  // RAW config in request
}

// NEW (v2.0+):
{
  mcpServerIds: ["server-1", "server-2"]  // Only IDs; configs loaded from DB
}
```

This prevents payload injection attacks where users could access arbitrary servers.

## Database Schema Changes

### Automatic Migration

On first boot with new tables:

```python
# database.py automatically migrates:
# 1. skills: primary key (id) → (id, user_id)
# 2. mcp_servers: primary key (id) → (id, user_id)
```

**Safety:**
- ✅ Renames old tables to `*_legacy`
- ✅ Creates new schema with composite PK
- ✅ Copies data, preserving timestamps
- ✅ Drops legacy tables on success
- ✅ Creates indexes for query performance

**Rollback:** Export data before upgrading if needed.

### Manual Verification

```sql
-- Check schema
PRAGMA table_info(skills);
-- Should show: id (pk), user_id (pk)

PRAGMA table_info(mcp_servers);
-- Should show: id (pk), user_id (pk)
```

## API Changes Summary

### Headers

| Provider | Header | Format |
|----------|--------|--------|
| **session** | `X-Session-Token` | UUID token |
| **session** | `X-User-Id` | Any string |
| **session** | `X-App-Token` (optional, /api/session only) | Static token |
| **auth0** | `Authorization` | `Bearer <jwt_token>` |

### Request Payloads

```javascript
// Chat: mcpServers → mcpServerIds
{
  messages: [...],
  mcpServerIds: ["srv-1"],  // IDs only
  selectedSkillIds: ["skill-a"]
}

// MCP Tools: new format
{
  serverId: "srv-1"  // ID only, server config loaded from DB
}

// MCP Call: new format
{
  serverId: "srv-1",
  toolName: "query",
  arguments: { ... }
}
```

## Troubleshooting

### "Invalid JWT header"

**Cause:** Auth0 token malformed or missing `kid` claim.

**Fix:**
- ✅ Verify token is valid at [jwt.io](https://jwt.io)
- ✅ Ensure `HERMAS_AUTH0_DOMAIN` is correct

### "Token expired"

**Cause:** Access token TTL exceeded.

**Fix:** Request new token from Auth0.

### "Unsupported auth provider"

**Cause:** `HERMAS_AUTH_PROVIDER` set to invalid value.

**Fix:** Use `session` or `auth0`.

### "Server not found"

**Cause:** `mcpServerId` doesn't belong to authenticated user.

**Fix:**
- Verify user is owner of server in DB
- Use `/api/mcp/servers` API to list available servers

## Migration Path (Existing Users)

### 1. Upgrade Code

```bash
git pull origin main
uv sync  # Install pyjwt[crypto]
```

### 2. Keep Session Mode (No Config Change)

App continues to work with `HERMAS_AUTH_PROVIDER=session`.

### 3. (Optional) Adopt Auth0 Later

When ready:
1. Set up Auth0 tenant
2. Update `.env` with `HERMAS_AUTH_PROVIDER=auth0` + Auth0 config
3. Restart application
4. Users authenticate via Bearer token instead

### 4. Data Persistence

All user data is preserved. Skills and servers remain associated with their original user_id.

## Security Considerations

1. **Token Transport:** Always use HTTPS in production
2. **JWKS Caching:** Hermas caches auth0 public keys for 10 minutes by default (configurable)
3. **Subject Claim:** `sub` claim is extracted as `user_id` and used for all resource ownership checks
4. **MCP Injection:** Raw MCP server configs in requests are rejected; only DB-stored IDs are trusted
5. **Composite Keys:** Prevent two users from overwriting each other's skills/servers with same ID

## Examples

### Session Mode (Legacy)

```bash
# Create session
curl -X POST http://localhost:8080/api/session \
  -H "X-App-Token: your-app-token" \
  -d '{"userId":"alice"}'
# Returns: {"sessionToken":"...", "userId":"alice", "expiresAt":...}

# Use session in requests
curl -X GET http://localhost:8080/api/mcp/servers \
  -H "X-Session-Token: <sessionToken>" \
  -H "X-User-Id: alice"
```

### Auth0 Mode

```bash
# Get token from Auth0
TOKEN=$(curl -s ... | jq -r '.access_token')

# Use Bearer token in requests
curl -X GET http://localhost:8080/api/mcp/servers \
  -H "Authorization: Bearer $TOKEN"
```

## References

- [Auth0 Documentation](https://auth0.com/docs)
- [JWT at jwt.io](https://jwt.io)
- [JWKS Specification](https://tools.ietf.org/html/rfc7517)
- [PyJWT Library](https://pyjwt.readthedocs.io/)

---

**Questions?** Open an issue or check the [main README](README.md).
