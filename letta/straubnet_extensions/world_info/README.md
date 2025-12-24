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
- Orders entries by `insertion_order` (higher priority first)

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
| `insertion_order` | Integer | Priority (higher = inserted later/closer to end of context) |
| `agent_id` | String (FK, nullable) | Optional agent ID. NULL = global entry (applies to all agents) |
| `enabled` | Boolean | Whether this entry is active and should be checked |
| `case_sensitive` | Boolean | Whether keyword matching should be case-sensitive |
| `match_whole_words` | Boolean | Whether keywords should match whole words only (schema ready, not yet implemented) |
| `scan_depth` | Integer (nullable) | How many messages back to scan (NULL = global default, not yet used) |
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

The World Info system provides a full CRUD API at `/v1/world-info/`.

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
  "match_whole_words": true,
  "scan_depth": null
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

**Response**: `200 OK` with array of entries, ordered by `insertion_order` DESC (higher priority first)

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

Entries with higher `insertion_order` values are inserted later (closer to the end of the context):

```json
// Lower priority (inserted first)
{
  "keywords": ["character"],
  "content": "General character information",
  "insertion_order": 50
}

// Higher priority (inserted later, closer to user message)
{
  "keywords": ["character", "personality"],
  "content": "Specific personality traits",
  "insertion_order": 150
}
```

When both entries match, the system will inject:
1. General character information (order 50)
2. Specific personality traits (order 150)
3. User message

This ensures more specific/important information appears closer to the user's message, which typically has more influence on the agent's response.

## Current Limitations

### Matching Behavior

- **Substring matching only** - Keywords match as substrings (e.g., "dog" matches "hotdog")
- **No whole-word matching yet** - The `match_whole_words` field exists in the schema but is not yet implemented
- **No regex support yet** - Keywords are treated as plain strings, not regex patterns
- **Case sensitivity** - Supported via `case_sensitive` flag (defaults to `false`)

### Message History

- **Current messages only** - Only scans the current message batch, not conversation history
- **No scan_depth implementation** - The `scan_depth` field exists but is not yet used

### Content Format

- **Plain text only** - Content is stored as plain text (markdown is supported as text, but not parsed)
- **No template variables** - Content cannot reference message content or variables

## Future Enhancements

Planned improvements:

1. **Regex Pattern Support** - Allow keywords to be regex patterns for more flexible matching
2. **Whole-Word Matching** - Implement the `match_whole_words` option to avoid substring false positives
3. **Message History Scanning** - Implement `scan_depth` to scan previous messages in the conversation
4. **Template Variables** - Support variables in content that can reference message content
5. **Vector/Embedding Matching** - Semantic similarity matching in addition to keyword matching
6. **Recursive Activation** - Entries that trigger other entries
7. **Conditional Activation** - Entries that only activate under certain conditions (time-based, state-based, etc.)

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
ORDER BY insertion_order DESC;

-- List entries for a specific agent
SELECT * FROM world_info_entries 
WHERE organization_id = 'your-org-id'
  AND (agent_id = 'agent-123' OR agent_id IS NULL)
  AND enabled = true
  AND is_deleted = false;
```

## Testing

The World Info system includes foundation tests in `tests/test_world_info.py` that demonstrate the testing patterns used throughout the Letta codebase.

### Running Tests

```bash
# Run all World Info tests
pytest tests/test_world_info.py -v

# Run a specific test
pytest tests/test_world_info.py::test_create_world_info_entry -v

# Run tests from container
podman exec letta-atlas bash -c "cd /app && pytest tests/test_world_info.py -v"
```

### Test Coverage

The foundation tests cover:
- **Create Entry** - POST endpoint with full and minimal field validation
- **List Entries** - GET endpoint with optional filtering
- **List with Agent Filter** - Testing agent_id filtering (global vs agent-specific)
- **Get by ID** - Retrieving specific entries and 404 handling
- **Update Entry** - PATCH for partial and single-field updates
- **Delete Entry** - DELETE with verification

### Test Architecture

The test suite is structured with helper classes and fixtures for scalability and maintainability:

**Helper Classes:**
- `WorldInfoClient` - Encapsulates all World Info API operations (create, list, get, update, delete)
  - Centralizes endpoint changes and error handling
  - Provides clean API: `client.create_entry(data)` instead of manual HTTP requests

**Fixtures:**
- `world_info_client` - Provides a `WorldInfoClient` instance configured for the test user
- `entry_factory` - Flexible factory for creating test entry data with sensible defaults
- `test_agent` - Creates a test agent for agent-specific entry tests

**Assertion Helpers:**
- `assert_entry_matches()` - Validates entry fields (only checks provided fields, resilient to schema changes)
- `assert_entry_in_list()` - Checks entry presence in lists

**Test Structure Example:**
```python
@pytest.mark.asyncio
async def test_create_world_info_entry(world_info_client, entry_factory, default_user):
    entry_data = entry_factory(
        keywords=["dog", "puppy"],
        content="You are a friendly dog.",
    )
    entry = world_info_client.create_entry(entry_data)
    assert_entry_matches(entry, entry_data, default_user.organization_id)
```

**Benefits:**
- **Maintainable** - Endpoint changes centralized in `WorldInfoClient`
- **Extensible** - Easy to add new tests using existing patterns
- **Resilient** - Assertions check only what matters (schema evolution won't break tests)
- **Clear** - Well-organized structure with section comments

For more details on test patterns, see the Testing section in `AGENTS.md`.

## Related Documentation

- **Extension System**: See `../README.md` for information about the extension architecture
- **Development State**: See `../WORLD_INFO_STATE.md` for implementation details and development status
- **SillyTavern Reference**: https://docs.sillytavern.app/usage/core-concepts/worldinfo/

