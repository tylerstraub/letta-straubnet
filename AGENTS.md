# AGENTS.md - Letta Development Context

**This file serves as "durable state" for AI agents working on Letta source code within the StraubNet fork. It should be loaded into context at the start of each new session to provide essential development knowledge.**

## Project Overview

You are working on [Letta](https://github.com/letta-ai/letta), an AI agent framework. This codebase is a fork (`tylerstraub/letta-straubnet`) that runs within an isolated instance managed by the `letta-instances` system.

### Key Context

- **Repository**: Fork of the official Letta repository
- **Remotes**:
  - `origin`: `git@github.com:tylerstraub/letta-straubnet.git` (your fork)
  - `upstream`: `git@github.com:letta-ai/letta.git` (official repository)
- **Instance Management**: Code runs in a Podman container managed by `letta-instances` system
- **Hot Reload**: Enabled via `LETTA_UVICORN_RELOAD=true` - code changes auto-reload (no restart needed)
- **Development Branch**: All work on `main_straubnet` branch (NEVER commit to `main`)

## Git Workflow - StraubNet Fork Strategy

This fork uses a **two-branch workflow** to maintain clean upstream integration.

**Branches:**
- **`main`**: Clean mirror of `upstream/main`. NEVER commit to this branch.
- **`main_straubnet`**: Your working trunk. All development happens here or on topic branches.
- **Topic branches**: `feat/`, `fix/`, `exp/` prefixes for isolated work.

**Workflow Rules:**
1. **NEVER commit to `main`** - it's kept identical to upstream using `reset --hard`
2. **All development on `main_straubnet` or topic branches** - use topic branches for isolated work
3. **CRITICAL: Code running in instances MUST be on `main_straubnet`**
   - Feature branches are for development/testing only
   - Before running migrations or deploying to instances, merge feature branches to `main_straubnet`
   - Never run database migrations on feature branches that aren't merged (causes state mismatch)
4. **Use instance management scripts** for updates (handles two-branch sync automatically)

### Quick Git Reference

```bash
# Update from upstream (recommended - handles two-branch sync)
/home/echolab/letta-instances/letta-manage.sh update <instance-name>

# Create topic branch
/home/echolab/letta-instances/letta-manage.sh feature <instance-name> create feat/my-feature

# Check what differs from upstream (before creating PR)
/home/echolab/letta-instances/letta-manage.sh check-diff <instance-name>

# Create clean upstream PR branch
/home/echolab/letta-instances/letta-manage.sh upstream-pr <instance-name> create upstream-pr/name feat/branch
```

## Instance Management

This Letta instance is managed by the `letta-instances` system at `/home/echolab/letta-instances/`.

**Key Paths:**
- Instance root: `/home/echolab/letta-instances/instances/<instance-name>/`
- Source code: `./letta/` (this directory)
- Management script: `/home/echolab/letta-instances/letta-manage.sh`

**Quick Commands:**
```bash
letta-manage.sh status <instance-name>    # Check status
letta-manage.sh logs <instance-name>      # View logs
letta-manage.sh shell <instance-name>     # Access container
```

**Container Details:**
- Container name: `letta-<instance-name>`
- Source mount: `/letta` (inside container) → `./letta` (on host)
- Hot reload: Enabled (code changes auto-reload)
- Database: PostgreSQL in container, isolated per instance

**Note**: For most development, you don't need to restart - changes are hot-reloaded automatically.

## Extension System Architecture

The StraubNet extension system allows adding custom functionality without modifying core Letta code, maintaining easy upstream sync.

### Key Principle: Minimal Core Hooks

Extensions use minimal, well-defined integration points in core code:
- Small hook functions (e.g., `apply_message_extensions()`)
- Graceful degradation (try/except with no-op fallback)
- Clear boundaries (extensions don't require core logic changes)

### Current Structure

```
letta/straubnet_extensions/
├── README.md                      # Extension patterns & procedures
├── message_processors/            # Processor system (registry, protocol)
│   └── _init_processors.py        # Auto-registration
└── world_info/                    # World Info system (complete)
    ├── README.md                  # World Info documentation
    ├── processor.py               # WorldInfoProcessor
    ├── scanner.py, matcher.py, storage.py
```

### Integration Points

Extensions hook into core code at minimal points:

**`letta/server/rest_api/routers/v1/agents.py`:**
- `send_message()` and `send_message_streaming()` endpoints call `apply_message_extensions()`
- Integration is a single function call with try/except fallback

**Extension Location Note:**
Currently extensions are in `letta/straubnet_extensions/` due to container mounting. Ideal would be repository root, but current location is acceptable with proper documentation.

### Extension Modules

**World Info System** (Complete):
- Keyword-based prompt injection (SillyTavern-style)
- Full CRUD REST API at `/v1/world-info/`
- Database-driven entries with organization/agent scoping
- See `letta/straubnet_extensions/world_info/README.md` for full documentation

**World Info Development Process:**
- **Feature branch**: `feat/world-info` (long-lived, for incremental development)
- **Development workflow**:
  1. Develop and commit on `feat/world-info` branch
  2. **Before running migrations or using in instances**: Merge `feat/world-info` → `main_straubnet`
  3. Code must exist on `main_straubnet` to be used by running instances
- **Commit conventions**: Use `feat(straubnet):` prefix for World Info enhancements
  - Examples: `feat(straubnet): add whole-word matching to World Info`, `feat(straubnet): implement scan_depth for World Info`
- **Commit strategy**: Incremental commits as features are added/extended (not monolithic)
- **Current status**: World Info foundation merged to `main_straubnet` (commit `9ea99b87d`)

For details on:
- **Extension patterns and adding processors**: See `letta/straubnet_extensions/README.md`
- **World Info usage and API**: See `letta/straubnet_extensions/world_info/README.md`

## Development Practices

### Hot Reload
- **Enabled**: `LETTA_UVICORN_RELOAD=true`
- Code changes auto-reload (watchfiles with polling)
- No container restart needed for code changes
- Look for `watchfiles.main - INFO - X change detected` in logs

### Testing & Debugging

**View logs:**
```bash
letta-manage.sh logs <instance-name>
# Or directly: tail -f instances/<instance-name>/.persist/logs/Letta.log
```

**Database access:**
```bash
# From container
podman exec letta-<instance-name> psql -U letta -d letta_<instance-name>

# Or from host (check .env for port)
psql -h localhost -p <PG_PORT> -U postgres -d letta_<instance-name>
```

**Run tests:**
```bash
# From container
podman exec letta-<instance-name> bash -c "cd /app && pytest tests/<test_file>.py -v"

# Or enter container shell
letta-manage.sh shell <instance-name>
cd /app
pytest tests/<test_file>.py -v
```

### Test-Driven Development Patterns

The Letta codebase uses pytest with async support. Tests are organized by purpose:

**Test Organization:**
- `tests/` - Root-level integration tests
- `tests/managers/` - Database manager tests (direct DB access)
- `tests/sdk/` - REST API tests using SDK client
- `tests/integration_test_*.py` - Full integration tests

**Key Test Patterns:**

1. **Integration Tests (REST API)** - Use `server_url` + `client` fixtures:
   ```python
   @pytest.mark.asyncio
   async def test_endpoint(server_url, default_user):
       headers = {"user_id": default_user.id, **_get_auth_headers()}
       response = requests.post(f"{server_url}/v1/endpoint/", headers=headers, json=data)
       assert response.status_code == 200
   ```

2. **Manager Tests** - Use `async_session` + `server` fixtures:
   ```python
   @pytest.mark.asyncio
   async def test_manager(server, default_user):
       result = await server.manager.method_async(actor=default_user)
       assert result is not None
   ```

**Important Fixtures:**
- `server_url` - Server URL (from `tests/conftest.py`, uses `LETTA_SERVER_URL` env var or starts server)
- `default_user` - Test user with organization (requires DB connection)
- `default_organization` - Test organization (requires DB connection)
- `async_session` - Database session (manager tests only)

**Authentication:**
Tests that make HTTP requests must include authentication:
```python
def _get_auth_headers():
    """Get authentication headers for API requests."""
    password = os.getenv("LETTA_SERVER_PASSWORD", "")
    if password:
        return {"Authorization": f"Bearer {password}"}
    return {}
```

**Environment Requirements:**
- `LETTA_PG_DB` - Database name (e.g., `letta_atlas`)
- `LETTA_PG_HOST` - Database host (e.g., `localhost`)
- `LETTA_PG_PORT` - Database port (e.g., `5432`)
- `LETTA_PG_USER` - Database user
- `LETTA_PG_PASSWORD` - Database password
- `LETTA_SERVER_PASSWORD` - Server authentication password (for API requests)
- `LETTA_SERVER_URL` - Optional: pre-existing server URL (if not set, tests start server)

**Container Setup:**
The `tests/` directory must be mounted in the container for test files to be visible. The instance manager configures this automatically.

**Example: World Info Tests**
See `tests/world_info_tests/` for a complete example following these patterns. The World Info test suite demonstrates:

- **Organized subdirectory structure** - Tests organized in `tests/world_info_tests/` following the same pattern as `tests/managers/`
- **Shared fixtures via conftest.py** - Common fixtures (`WorldInfoClient`, `test_agent`) available to all test files
- **Helper classes** (`WorldInfoClient`) for encapsulating API operations
- **Minimal core tests** - Focused on essential CRUD and regression testing in `test_world_info_api.py`
- **Scalable structure** - Easy to add detailed test files as needed (e.g., `test_world_info_matcher.py`)

This pattern can be adapted for other extension test suites as they grow in complexity.

## Important Reminders

1. **Never commit to `main`** - It's a clean mirror of upstream
2. **Hot reload is enabled** - No restart needed for code changes
3. **Use instance management scripts** - They handle two-branch workflow correctly
4. **Extensions are optional** - Core code gracefully degrades if extensions missing
5. **Check diffs before upstream PRs** - Use `check-diff` to see StraubNet-specific changes

## Quick Reference

### Git Workflow
- Daily dev: Work on `main_straubnet` or topic branches
- Updates: `letta-manage.sh update <instance-name>`
- Upstream PRs: `letta-manage.sh upstream-pr <instance-name> create ...`

### Extension Development
- Patterns: See `letta/straubnet_extensions/README.md`
- World Info: See `letta/straubnet_extensions/world_info/README.md`
- Hook point: `letta/server/rest_api/routers/v1/agents.py` → `apply_message_extensions()`

### Instance Operations
- Status/logs: `letta-manage.sh status/logs <instance-name>`
- Shell: `letta-manage.sh shell <instance-name>`
- Container: `letta-<instance-name>`, database: `letta_<instance-name>`

---

## Important Workflow Lessons

### Database Migrations and Feature Branches

**CRITICAL RULE**: Never run database migrations on a feature branch unless that branch's code is already merged to `main_straubnet`.

**Why**: Instances run code from `main_straubnet`. If you migrate the database on a feature branch but don't merge the code:
- Database state won't match the codebase
- Alembic revisions will be out of sync
- Container startup will fail due to schema validation errors

**Correct workflow**:
1. Develop feature on topic branch (e.g., `feat/world-info`)
2. **Merge to `main_straubnet` FIRST**
3. Then run migrations (or migrations run automatically on container startup)
4. Database state and codebase state stay in sync

**Lesson learned** (December 2024): World Info migration was run on `feat/world-info` before merging, causing a regression when the codebase was on `main_straubnet` without the migration file. Fix: Merge feature branches before running migrations.

---

**Last Updated**: December 2024 - World Info system merged to `main_straubnet`, workflow rules updated, testing patterns documented
