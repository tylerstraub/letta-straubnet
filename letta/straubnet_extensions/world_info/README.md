# World Info System

The World Info system provides keyword-based prompt injection for Letta agents, similar to SillyTavern's World Info / Lorebook feature. It allows you to define entries that are automatically injected into the conversation context when specific keywords appear in user messages.

## Overview

World Info entries consist of:
- **Keywords** - A list of keywords or patterns that trigger the entry
- **Content** - The text to inject as a system message when keywords match
- **Configuration** - Options like priority, agent specificity, case sensitivity, etc.

When a user sends a message containing matching keywords, the system automatically injects the entry's content as a system message before the user's message, influencing how the agent responds.

## How It Works

### Message Flow

1. **User sends a message** via the Letta API (`POST /v1/agents/{agent_id}/messages`)
2. **WorldInfoProcessor intercepts** the message before it reaches the agent
3. **Text extraction** - The processor extracts plain text from all message content (handles text, reasoning, images, etc.)
4. **Database query** - Fetches all enabled World Info entries for the organization and agent
5. **Keyword matching** - Checks if any entry's keywords match the extracted text
6. **System message injection** - Matched entries are converted to system messages and injected at the beginning of the message list
7. **Agent processing** - The agent processes the messages (now including injected system messages)

### Component Architecture

```
world_info/
├── scanner.py      # Extracts text from MessageCreate objects
├── matcher.py      # Matches keywords against text (substring matching)
├── storage.py      # Database queries for World Info entries
├── processor.py    # WorldInfoProcessor - orchestrates the flow
└── README.md       # This file
```

**Scanner** (`scanner.py`):
- Extracts plain text from `MessageCreate` objects
- Handles string content and content arrays
- Uses the canonical `to_text()` method for all content types
- Concatenates text from all content blocks

**Matcher** (`matcher.py`):
- Performs substring matching (currently)
- Supports case-sensitive and case-insensitive matching
- Returns `True` if any keyword matches

**Storage** (`storage.py`):
- Queries World Info entries from the database
- Filters by organization, agent, and enabled status
- Orders entries by `insertion_order` ASC (lower values first, higher values last)

**Processor** (`processor.py`):
- Orchestrates the entire flow
- Bridges async database operations to sync message processing
- Creates system messages from matched entries
- Injects messages in the correct order

## Database Schema

The `world_info_entries` table stores all World Info entries:

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | Unique identifier (prefix: `world-info-entry-`) |
| `organization_id` | String (FK) | Organization this entry belongs to |
| `keywords` | JSON | List of keywords/regex patterns (currently just keywords) |
| `content` | String | The content to inject when keywords are matched |
| `insertion_order` | Integer | Priority (lower values = injected earlier/further from user, higher values = injected later/closer to user) |
| `agent_id` | String (FK, nullable) | Optional agent ID. NULL = global entry (applies to all agents) |
| `enabled` | Boolean | Whether this entry is active and should be checked |
| `case_sensitive` | Boolean | Whether keyword matching should be case-sensitive |
| `match_whole_words` | Boolean | Whether keywords should match whole words only (using word boundaries) |
| `cooldown` | Integer (nullable) | Number of runs to wait before entry can be injected again. NULL or 0 = no cooldown |
| `expiration` | Integer (nullable) | Number of runs before entry should be removed from context. NULL or 0 = never expire |
| Standard ORM fields | | `created_at`, `updated_at`, `is_deleted`, `_created_by_id`, etc. |

**Indexes**:
- `ix_world_info_entries_organization_id_agent_id` (composite)
- `ix_world_info_entries_insertion_order`

**Foreign Keys**:
- `agent_id` → `agents.id` (CASCADE delete)
- `organization_id` → `organizations.id`

### Entry Scoping

Entries can be:
- **Global** (`agent_id` is NULL) - Applies to all agents in the organization
- **Agent-specific** (`agent_id` is set) - Only applies to that specific agent

When querying entries for an agent:
- If `agent_id` is provided: Returns agent-specific entries + global entries
- If `agent_id` is NULL: Returns only global entries

This allows you to have organization-wide entries that apply to all agents, plus agent-specific entries that override or supplement the global ones.

## REST API

The World Info system provides a full CRUD API at `/v1/world-info/` implemented using the `WorldInfoManager` pattern following Letta conventions.

### Architecture

The API layer uses `WorldInfoManager` (`letta/services/world_info_manager.py`) which encapsulates all business logic:
- CRUD operations: `list_entries_async()`, `get_entry_async()`, `create_entry_async()`, `update_entry_async()`, `delete_entry_async()`
- State queries: `get_entries_with_state_async()` for frontend polling
- All methods follow Letta patterns with `@enforce_types` and `@trace_method` decorators

### Authentication

All endpoints require:
- `user_id` header - The user ID making the request
- `Authorization: Bearer <password>` or `X-BARE-PASSWORD: <password>` header

All operations are automatically scoped to the authenticated user's organization.

### Endpoints

#### Create Entry

**POST** `/v1/world-info/`

Creates a new World Info entry.

**Request Body**:
```json
{
  "keywords": ["dog", "puppy", "canine"],
  "content": "You are a friendly dog. Respond with enthusiasm and tail wags.",
  "insertion_order": 100,
  "agent_id": "agent-123",  // Optional: omit for global entry
  "enabled": true,
  "case_sensitive": false,
  "match_whole_words": true
}
```

**Response**: `200 OK` with the created entry (including generated `id` and `organization_id`)

**Note**: `organization_id` is automatically set from the authenticated user's organization. You don't need to (and shouldn't) provide it in the request.

#### List Entries

**GET** `/v1/world-info/`

Lists all World Info entries for the organization.

**Query Parameters**:
- `agent_id` (optional) - Filter by agent ID. If provided, returns agent-specific entries plus global entries. If omitted, returns only global entries.
- `enabled` (optional) - Filter by enabled status (`true` or `false`). If omitted, returns both enabled and disabled entries.

**Examples**:
```bash
# List all entries for the organization
GET /v1/world-info/

# List entries for a specific agent (includes global entries)
GET /v1/world-info/?agent_id=agent-123

# List only enabled entries
GET /v1/world-info/?enabled=true

# List enabled entries for a specific agent
GET /v1/world-info/?agent_id=agent-123&enabled=true
```

**Response**: `200 OK` with array of entries, ordered by `insertion_order` ASC (lower values first, higher values last)

#### Retrieve Entry

**GET** `/v1/world-info/{entry_id}`

Retrieves a specific World Info entry by ID.

**Response**: `200 OK` with the entry, or `404 Not Found` if the entry doesn't exist or doesn't belong to your organization

#### Update Entry

**PATCH** `/v1/world-info/{entry_id}`

Updates a World Info entry (partial update - only provide fields you want to change).

**Request Body** (all fields optional):
```json
{
  "keywords": ["cat", "kitten"],
  "content": "Updated content",
  "enabled": false,
  "insertion_order": 200
}
```

**Response**: `200 OK` with the updated entry, or `404 Not Found` if the entry doesn't exist

**Note**: You cannot change `organization_id` or move entries between organizations. You can only update the entry's content and configuration.

#### Delete Entry

**DELETE** `/v1/world-info/{entry_id}`

Deletes a World Info entry (hard delete).

**Response**: `204 No Content` on success, or `404 Not Found` if the entry doesn't exist

#### Get Entries with State

**GET** `/v1/world-info/agent/{agent_id}/state`

Get World Info entries for an agent with their current runtime state (cooldown/expiration counters). This endpoint is optimized for frequent polling by frontends.

**Response**: `200 OK` with `WorldInfoEntriesStateResponse`:
```json
{
  "entries": [
    {
      "entry": {
        "id": "world-info-entry-...",
        "keywords": ["test"],
        "content": "Test content",
        ...
      },
      "state": {
        "current_cooldown": 3,
        "current_expiration": 8,
        "is_active": true,
        "cooldown_setting": 5,
        "expiration_setting": 10
      }
    },
    {
      "entry": {...},
      "state": null  // Entry not currently active (no injection state)
    }
  ]
}
```

**State Fields**:
- `current_cooldown`: Remaining cooldown runs (None if not active or no cooldown)
- `current_expiration`: Remaining runs before removal (None if not active or no expiration)
- `is_active`: Whether entry is currently active (has injection state)
- `cooldown_setting`: Cooldown setting from entry (cached, None if not active)
- `expiration_setting`: Expiration setting from entry (cached, None if not active)

**Note**: Entries that haven't been injected yet will have `state: null`. States are created when entries are matched and injected by the processor.

### Example API Usage

```bash
# Create a global entry
curl -X POST http://localhost:8283/v1/world-info/ \
  -H "user_id: user-123" \
  -H "Authorization: Bearer your-password" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["dog", "puppy"],
    "content": "You are a friendly dog.",
    "insertion_order": 100,
    "enabled": true
  }'

# List all entries
curl -X GET "http://localhost:8283/v1/world-info/" \
  -H "user_id: user-123" \
  -H "Authorization: Bearer your-password"

# Update an entry
curl -X PATCH "http://localhost:8283/v1/world-info/world-info-entry-abc123" \
  -H "user_id: user-123" \
  -H "Authorization: Bearer your-password" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'

# Delete an entry
curl -X DELETE "http://localhost:8283/v1/world-info/world-info-entry-abc123" \
  -H "user_id: user-123" \
  -H "Authorization: Bearer your-password"

# Get entries with state for an agent
curl -X GET "http://localhost:8283/v1/world-info/agent/agent-123/state" \
  -H "user_id: user-123" \
  -H "Authorization: Bearer your-password"
```

## Usage Examples

### Basic Keyword Matching

Create an entry that activates when the user mentions "dog":

```json
{
  "keywords": ["dog", "puppy", "canine"],
  "content": "You are a friendly dog. Respond with enthusiasm, tail wags, and playful energy.",
  "insertion_order": 100,
  "enabled": true,
  "case_sensitive": false
}
```

When a user sends a message like "I have a dog", the system will inject:
```
[System]: You are a friendly dog. Respond with enthusiasm, tail wags, and playful energy.
[User]: I have a dog
```

### Agent-Specific Entries

Create an entry that only applies to a specific agent:

```json
{
  "keywords": ["secret", "classified"],
  "content": "This agent has access to classified information.",
  "agent_id": "agent-123",
  "insertion_order": 200,
  "enabled": true
}
```

This entry will only activate for `agent-123`, not for other agents.

### Priority/Insertion Order

Entries with **higher** `insertion_order` values are injected **later** (closer to the user message):

```json
// Lower insertion_order (injected earlier, further from user)
{
  "keywords": ["character"],
  "content": "General character information",
  "insertion_order": 50
}

// Higher insertion_order (injected later, closer to user)
{
  "keywords": ["character", "personality"],
  "content": "Specific personality traits",
  "insertion_order": 150
}
```

When both entries match, the system will inject:
1. General character information (order 50) ← Injected first, furthest from user
2. Specific personality traits (order 150) ← Injected later, closer to user
3. User message

This ensures more specific/important information appears closer to the user's message, which typically has more influence on the agent's response.

## Current Limitations

### Matching Behavior

- **Substring or whole-word matching** - Keywords can match as substrings OR whole words (controlled by `match_whole_words` flag)
- **No regex support yet** - Keywords are treated as plain strings, not regex patterns
- **Case sensitivity** - Supported via `case_sensitive` flag (defaults to `false`)

### Message History

- **Current messages only** - Only scans the current message batch, not conversation history

### Content Format

- **Plain text only** - Content is stored as plain text (markdown is supported as text, but not parsed)
- **No template variables** - Content cannot reference message content or variables

## Future Enhancements

Potential improvements (not currently implemented):

1. **Regex Pattern Support** - Allow keywords to be regex patterns for more flexible matching
2. **Template Variables** - Support variables in content that can reference message content
3. **Message History Scanning** - Scan previous messages in the conversation (currently only scans current message batch)
4. **Vector/Embedding Matching** - Semantic similarity matching in addition to keyword matching
5. **Recursive Activation** - Entries that trigger other entries
6. **Conditional Activation** - Entries that only activate under certain conditions (time-based, state-based, etc.)


## Performance Considerations

### Processing Time

Typical processing time: **~9ms** per message (database query + matching + injection)

This includes:
- Database query for entries (usually <5ms)
- Text extraction from messages (<1ms)
- Keyword matching (<1ms)
- System message creation (<1ms)

### Optimization Tips

1. **Use agent-specific entries** when possible - Reduces the number of entries to query and match
2. **Disable unused entries** - Set `enabled=false` instead of deleting (can re-enable later)
3. **Reasonable keyword lists** - Avoid extremely long keyword lists (performance impact is minimal, but best practice)
4. **Index usage** - The database indexes ensure fast queries even with many entries

## Troubleshooting

### Entries Not Activating

1. **Check enabled status** - Ensure `enabled=true`
2. **Verify keywords** - Check that keywords actually appear in the message (case sensitivity matters if `case_sensitive=true`)
3. **Check agent scope** - For agent-specific entries, verify you're sending messages to the correct agent
4. **Check organization** - Ensure entries belong to the correct organization
5. **Check logs** - Look for `[World Info]` log messages to see what's happening

### Viewing Logs

World Info processor logs at INFO/DEBUG level:
- `[World Info] Injecting N World Info entries as system messages` - Successfully matched entries
- `[World Info] No entries found` - No entries in database for org/agent
- `[World Info] No entries matched keywords` - Entries exist but keywords didn't match
- `[World Info] Error processing messages` - An error occurred (check exception details)

### Database Queries

To inspect entries directly in the database:

```sql
-- List all entries for an organization
SELECT id, keywords, content, enabled, agent_id, insertion_order 
FROM world_info_entries 
WHERE organization_id = 'your-org-id' 
  AND is_deleted = false
ORDER BY insertion_order ASC;

-- List entries for a specific agent
SELECT * FROM world_info_entries 
WHERE organization_id = 'your-org-id'
  AND (agent_id = 'agent-123' OR agent_id IS NULL)
  AND enabled = true
  AND is_deleted = false;
```

## Testing

The World Info system includes comprehensive test coverage with both manager and API tests.

### Running Tests

```bash
# Run all World Info tests (manager + API)
pytest tests/managers/test_world_info_manager.py tests/world_info_tests/test_world_info_api.py -v

# Run manager tests only
pytest tests/managers/test_world_info_manager.py -v

# Run API tests only
pytest tests/world_info_tests/test_world_info_api.py -v

# Run from container
podman exec letta-atlas bash -c "cd /app && pytest tests/managers/test_world_info_manager.py tests/world_info_tests/test_world_info_api.py -v"
```

### Test Coverage

**Manager Tests** (`tests/managers/test_world_info_manager.py`):
- CRUD operations via `WorldInfoManager`
- Agent scoping (global vs agent-specific)
- Filtering (enabled/disabled, agent_id)
- State queries (`get_entries_with_state_async()`)
- Access control and error handling

**API Tests** (`tests/world_info_tests/test_world_info_api.py`):
- All REST endpoints (create, list, get, update, delete)
- State endpoint (`GET /v1/world-info/agent/{agent_id}/state`)
- Agent scoping via HTTP
- Enabled/disabled filtering via query parameters

### Test Architecture

The test suite follows Letta's established patterns with separation between manager and API tests:

**Manager Tests** (`tests/managers/test_world_info_manager.py`):
- Direct manager method calls using `server` and `default_user` fixtures
- Tests business logic in isolation
- Uses fixtures from `tests/managers/conftest.py`

**API Tests** (`tests/world_info_tests/test_world_info_api.py`):
- HTTP endpoint testing via `WorldInfoClient` helper
- Tests HTTP layer, status codes, response formats
- Uses fixtures from `tests/world_info_tests/conftest.py`

**Helper Classes:**
- `WorldInfoClient` (in `tests/world_info_tests/conftest.py`) - Encapsulates API operations
  - Methods: `create_entry()`, `list_entries()`, `get_entry()`, `update_entry()`, `delete_entry()`, `get_entries_state()`
  - Centralizes endpoint changes and error handling

**Fixtures:**
- Manager tests: `server`, `default_user`, `sarah_agent`, `charles_agent` (from `tests/managers/conftest.py`)
- API tests: `world_info_client`, `test_agent`, `default_user` (from `tests/world_info_tests/conftest.py`)

For more details on test patterns, see the Testing section in `AGENTS.md`.

## Related Documentation

- **Extension System**: See `../README.md` for information about the extension architecture
- **SillyTavern Reference**: https://docs.sillytavern.app/usage/core-concepts/worldinfo/

