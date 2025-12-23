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
1. NEVER commit to `main` - it's kept identical to upstream using `reset --hard`
2. All development on `main_straubnet` or topic branches
3. Use instance management scripts for updates (handles two-branch sync automatically)

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
- **Feature branch**: `feat/world-info` (long-lived, will receive many incremental commits)
- **Initial commit**: `feat(straubnet): add World Info system foundation` (includes framework, schema, processor, API)
- **Future commits**: Use conventional commit format with `feat(straubnet):` prefix for World Info enhancements
  - Examples: `feat(straubnet): add whole-word matching to World Info`, `feat(straubnet): implement scan_depth for World Info`
- **Commit strategy**: Incremental commits as features are added/extended (not monolithic)
- **All World Info work** should be committed to `feat/world-info` branch

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
letta-manage.sh shell <instance-name>
cd /letta
pytest  # or whatever test command Letta uses
```

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

**Last Updated**: December 2024 - World Info system foundation committed to `feat/world-info` branch
