# AGENTS.md - Letta Development Context

**This file serves as "durable state" for AI agents working on Letta source code within the StraubNet fork. It should be loaded into context at the start of each new session to provide essential development knowledge.**

## Project Overview

You are working on [Letta](https://github.com/letta-ai/letta), an AI agent framework. This codebase is a fork (`tylerstraub/letta-straubnet`) that runs within an isolated instance managed by the `letta-instances` system.

### Key Context

- **Repository**: This is a fork of the official Letta repository
- **Remotes**:
  - `origin`: `git@github.com:tylerstraub/letta-straubnet.git` (your fork)
  - `upstream`: `git@github.com:letta-ai/letta.git` (official Letta repository)
- **Instance Management**: This code runs in a Podman container managed by the `letta-instances` system
- **Hot Reload**: Source code changes are automatically hot-reloaded (no container restart needed)
- **Development Branch**: All work happens on `main_straubnet` branch (never commit to `main`)

## Git Workflow - StraubNet Fork Strategy

This fork uses a **two-branch workflow** to maintain clean upstream integration while allowing fork-specific development.

### Branch Structure

```
upstream/main ───────────────► A ─► B ─► C ─► D ─► E
                                \
main_straubnet ─► A ─► B ─► C ─► S1 ─► S2 ─► S3    (StraubNet-only commits)
                                \
feat/mcp-bridge ────────────────► F1 ─► F2 ─► F3    (topic branch)
```

**Branches:**
- **`main`**: Clean mirror of `upstream/main`. NEVER commit to this branch. It's kept identical to upstream using `reset --hard`.
- **`main_straubnet`**: Your working trunk. All development happens here or on topic branches that merge back here.
- **Topic branches**: `feat/`, `fix/`, `exp/`, or `straubnet_` prefix for isolated work.

### Workflow Rules

1. **NEVER commit to `main`** - It's a clean mirror of upstream
2. **All development on `main_straubnet`** - This is your working branch
3. **Use topic branches** - Create `feat/`, `fix/`, or `exp/` branches for features
4. **Keep `main` clean** - It's synced with upstream using `reset --hard` (not merge)

## Instance Management Integration

This Letta instance is managed by the `letta-instances` system. Key paths and commands:

### Instance Location
- **Instance Root**: `/home/echolab/letta-instances`
- **This Instance**: `/home/echolab/letta-instances/instances/<instance-name>/`
- **Source Code**: `/home/echolab/letta-instances/instances/<instance-name>/letta/` (this directory)
- **Management Script**: `/home/echolab/letta-instances/letta-manage.sh`

### Common Instance Operations

**Check instance status:**
```bash
/home/echolab/letta-instances/letta-manage.sh status <instance-name>
```

**View logs:**
```bash
/home/echolab/letta-instances/letta-manage.sh logs <instance-name>
```

**Restart instance (if needed):**
```bash
/home/echolab/letta-instances/letta-manage.sh restart <instance-name>
```

**Access container shell:**
```bash
/home/echolab/letta-instances/letta-manage.sh shell <instance-name>
```

**Note**: For most development, you don't need to restart - changes are hot-reloaded automatically.

### Container Details

- **Container Name**: `letta-<instance-name>`
- **Source Mount**: `/letta` (inside container) → `./letta` (on host)
- **Hot Reload**: Enabled via `WATCHFILES_FORCE_POLLING=true`
- **Logs**: Available at `instances/<instance-name>/.persist/logs/Letta.log`
- **Database**: PostgreSQL running in container (isolated per instance)

## Git Operations

### Daily Development Workflow

#### 1. Check Current Status
```bash
git status
git branch --show-current  # Should be main_straubnet or a topic branch
```

#### 2. Create a Topic Branch (for new work)
```bash
# From the instance management system (recommended):
/home/echolab/letta-instances/letta-manage.sh feature <instance-name> create feat/my-feature

# Or manually:
git checkout main_straubnet
git checkout -b feat/my-feature
```

**Topic Branch Naming:**
- `feat/` - New features
- `fix/` - Bug fixes
- `exp/` - Experiments
- `straubnet_` - Legacy prefix (still supported)

#### 3. Make Changes and Commit
```bash
# Make your code changes
# Changes are hot-reloaded automatically (no restart needed)

# Commit your changes
git add <files>
git commit -m "feat: description of changes"
```

#### 4. Push Your Work
```bash
# Push topic branch
git push -u origin feat/my-feature

# Or if working directly on main_straubnet
git push origin main_straubnet
```

#### 5. Merge Topic Branch Back
```bash
# Using instance management (recommended):
/home/echolab/letta-instances/letta-manage.sh feature <instance-name> merge feat/my-feature

# Or manually:
git checkout main_straubnet
git merge --no-ff feat/my-feature
git push origin main_straubnet
```

### Updating from Upstream

**Important**: Always use the instance management script for updates - it handles the two-branch workflow automatically.

```bash
# Update from upstream (recommended):
/home/echolab/letta-instances/letta-manage.sh update <instance-name>

# This automatically:
# 1. Updates 'main' from upstream/main (reset --hard, keeps it clean)
# 2. Merges 'main' into 'main_straubnet' (brings upstream changes into dev)
```

**Using rebase instead of merge:**
```bash
/home/echolab/letta-instances/letta-manage.sh update <instance-name> --rebase
```

**Manual update (if needed):**
```bash
git fetch upstream
git checkout main
git fetch upstream
git reset --hard upstream/main
git push --force-with-lease origin main

git checkout main_straubnet
git merge main  # or: git rebase main
git push origin main_straubnet
```

### Creating Upstream Pull Requests

When you want to contribute changes back to the official Letta repository, you need to create a clean PR branch that only contains your commits (not StraubNet-specific changes).

#### Method 1: Cherry-Pick Export (Recommended)

```bash
# Using instance management:
/home/echolab/letta-instances/letta-manage.sh upstream-pr <instance-name> create upstream-pr/my-feature feat/my-feature

# This:
# 1. Creates a branch from clean 'main' (which matches upstream/main)
# 2. Cherry-picks your commits from the topic branch
# 3. Pushes to origin for PR creation
```

#### Method 2: Rebase-Onto Export

```bash
/home/echolab/letta-instances/letta-manage.sh upstream-pr <instance-name> rebase upstream-pr/my-feature feat/my-feature

# This uses rebase --onto to strip StraubNet base commits
```

#### Check What You're Dragging

Before creating an upstream PR, check what `main_straubnet` has that upstream doesn't:

```bash
/home/echolab/letta-instances/letta-manage.sh check-diff <instance-name>
```

This shows StraubNet-specific commits that should NOT be in upstream PRs.

### Branch Management

**List topic branches:**
```bash
/home/echolab/letta-instances/letta-manage.sh feature <instance-name> list
```

**Check branch status:**
```bash
/home/echolab/letta-instances/letta-manage.sh feature <instance-name> status feat/my-feature
```

**Switch branches:**
```bash
/home/echolab/letta-instances/letta-manage.sh feature <instance-name> switch feat/my-feature
```

**Delete topic branch:**
```bash
/home/echolab/letta-instances/letta-manage.sh feature <instance-name> delete feat/my-feature
```

## Development Practices

### Hot Reload

- **Enabled by default**: Changes to Python files are automatically reloaded
- **No restart needed**: Just save your files and the changes take effect
- **Watch mode**: Uses `WATCHFILES_FORCE_POLLING=true` for reliable file watching

### Testing

Run tests inside the container:
```bash
# Access container shell
/home/echolab/letta-instances/letta-manage.sh shell <instance-name>

# Inside container, run tests
cd /letta
pytest  # or whatever test command Letta uses
```

### Debugging

**View logs:**
```bash
# From host
/home/echolab/letta-instances/letta-manage.sh logs <instance-name>

# Or directly
tail -f /home/echolab/letta-instances/instances/<instance-name>/.persist/logs/Letta.log
```

**Container access:**
```bash
/home/echolab/letta-instances/letta-manage.sh shell <instance-name>
```

**Environment variables:**
- Check `.env` file in instance directory
- Or inside container: `env | grep LETTA`

### Database Access

PostgreSQL runs inside the container:
- **Host**: `localhost` (from inside container)
- **Port**: Check instance `.env` file for `LETTA_PG_PORT`
- **Database**: `letta_<instance-name>`
- **Data**: Persisted at `instances/<instance-name>/.persist/pgdata/`

Access from host:
```bash
# Check .env for port
psql -h localhost -p <PG_PORT> -U postgres -d letta_<instance-name>
```

## Important Reminders

1. **Never commit to `main`** - It's a clean mirror of upstream
2. **Always work on `main_straubnet` or topic branches** - Never directly on `main`
3. **Use topic branches** - Create `feat/`, `fix/`, or `exp/` branches for isolated work
4. **Hot reload is enabled** - No need to restart container for code changes
5. **Use instance management scripts** - They handle the two-branch workflow correctly
6. **Check diffs before upstream PRs** - Use `check-diff` to see what you're dragging
7. **Clean PR branches** - Use `upstream-pr` commands to create clean PRs without StraubNet commits

## Quick Reference

### Git Workflow Summary

```
Daily Development:
  1. git checkout main_straubnet (or create topic branch)
  2. Make changes (hot-reloaded automatically)
  3. git commit
  4. git push origin <branch>
  5. Merge topic branch back to main_straubnet when done

Updating from Upstream:
  letta-manage.sh update <instance-name>

Creating Upstream PR:
  letta-manage.sh upstream-pr <instance-name> create upstream-pr/name feat/branch
```

### Instance Management Quick Reference

```bash
# Status and logs
letta-manage.sh status <instance-name>
letta-manage.sh logs <instance-name>

# Git operations
letta-manage.sh update <instance-name>          # Update from upstream
letta-manage.sh feature <instance-name> <cmd>  # Manage topic branches
letta-manage.sh check-diff <instance-name>      # Check what differs from upstream
letta-manage.sh upstream-pr <instance-name> <cmd>  # Create upstream PR branches

# Container operations
letta-manage.sh shell <instance-name>           # Access container
letta-manage.sh restart <instance-name>         # Restart (rarely needed)
```

## Relationship to Instance Management System

This Letta instance is managed by the `letta-instances` system located at `/home/echolab/letta-instances/`. 

- **For instance management tasks** (creating instances, backups, etc.): Open `/home/echolab/letta-instances/` as workspace and see `AGENTS.md` there
- **For Letta development tasks** (this file): You're working in the instance's `letta/` directory

The instance management system provides:
- Container lifecycle management
- Database persistence
- Port management
- Git workflow automation (two-branch sync, topic branches, upstream PRs)
- Log management

You interact with it via the `letta-manage.sh` script for Git operations and instance management, but your primary work is in this Letta source code directory.

---

**Last Updated**: December 2024 - StraubNet fork workflow implementation

