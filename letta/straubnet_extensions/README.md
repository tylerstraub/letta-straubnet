# StraubNet Extensions

This directory contains the StraubNet extension system for Letta, providing a clean way to add custom functionality without modifying core Letta code. This system is designed to maintain easy synchronization with upstream while enabling fork-specific features.

## Extension Architecture Principles

### The Fundamental Rule: Minimal Core Hooks

When extending Letta, we follow a **minimal hooks** principle:

1. **Small, well-defined integration points** in core code
2. **Graceful degradation** - extensions are optional (try/except with no-op fallback)
3. **Clear boundaries** - extensions don't require changes to core logic beyond hooks
4. **No core dependencies** - extensions use core APIs, but core doesn't depend on extensions

This approach ensures that:
- Upstream synchronization remains straightforward
- Merge conflicts are minimized
- Extensions can be easily enabled/disabled
- Core Letta code stays clean and maintainable

### Container Mounting Considerations

**Note**: Currently, extensions are located inside `letta/straubnet_extensions/` due to container mounting limitations. The ideal architecture would place extensions at the repository root (see `AGENTS.md` for details on the architectural trade-offs).

**Future Improvement**: Configure instance management to mount the parent directory, allowing extensions to live at the repository root for cleaner separation.

## Message Processor Pattern

The extension system uses a **message processor** pattern that allows intercepting and modifying messages before they are sent to agents. This enables features like:

- Dynamic prompt injection (e.g., World Info entries)
- Content filtering and transformation
- Custom routing logic
- Message enrichment

### Architecture

```
straubnet_extensions/
├── __init__.py                    # Main entry point
├── README.md                      # This file (extension patterns)
├── message_processors/
│   ├── __init__.py                # Processor registry and apply function
│   ├── protocol.py                # MessageProcessor abstract base class
│   ├── registry.py                # Processor registry implementation
│   └── _init_processors.py        # Auto-registration of processors
└── [extension-modules]/           # Individual extension implementations
    └── ...
```

### How It Works

1. **Registration**: Processors are registered when `_init_processors.py` is imported
2. **Hook Points**: The extension system hooks into API endpoints via minimal function calls
3. **Processing**: When a message is sent, all registered processors run in order, each receiving the (possibly modified) message list
4. **Execution**: Processors are executed synchronously in registration order

### Integration Points

The extension system integrates with Letta at minimal, well-defined hook points:

**`letta/server/rest_api/routers/v1/agents.py`:**
- `send_message()` endpoint - calls `apply_message_extensions()`
- `send_message_streaming()` endpoint - calls `apply_message_extensions()`

The integration is intentionally minimal - just a single function call:

```python
try:
    from straubnet_extensions import apply_message_extensions
except ImportError:
    # Graceful fallback - extensions are optional
    def apply_message_extensions(messages, agent_id, actor, context=None):
        return messages

# Use extension hook
request.messages = apply_message_extensions(
    messages=request.messages,
    agent_id=agent_id,
    actor=actor,
    context={"server": server},
)
```

This makes upstream sync straightforward - the hook point is small and unlikely to conflict.

## Adding New Processors

To add a new message processor:

### 1. Create Your Processor Class

Create a new file in `message_processors/` (e.g., `my_processor.py`):

```python
from typing import List
from straubnet_extensions.message_processors.protocol import MessageProcessor
from letta.schemas.message import MessageCreate

class MyProcessor(MessageProcessor):
    """
    My custom message processor.
    
    This processor [describe what it does].
    """
    
    def process(
        self,
        messages: List[MessageCreate],
        context: dict,
    ) -> List[MessageCreate]:
        """
        Process messages and return modified message list.
        
        Args:
            messages: List of MessageCreate objects to process
            context: Context dictionary containing:
                - agent_id: The agent ID the messages are being sent to
                - actor: The user making the request (has organization_id)
                - server: Optional SyncServer instance
        
        Returns:
            Modified list of MessageCreate objects (may inject new messages, 
            modify existing ones, or return unchanged)
        """
        # Your processing logic here
        # You can:
        # - Inject new messages (e.g., system messages)
        # - Modify existing messages
        # - Filter messages
        # - Add metadata
        
        return messages  # Return modified or original messages
```

### 2. Register Your Processor

Add registration to `message_processors/_init_processors.py`:

```python
from letta.log import get_logger
from straubnet_extensions.message_processors import register_processor
from straubnet_extensions.message_processors.my_processor import MyProcessor

logger = get_logger(__name__)

# Register your processor
try:
    _my_processor = MyProcessor()
    register_processor(_my_processor)
    logger.info("[StraubNet Extensions] MyProcessor registered successfully")
except Exception as e:
    logger.error(f"[StraubNet Extensions] Failed to register MyProcessor: {e}", exc_info=True)
```

### 3. Processing Order

Processors execute in **registration order**. Each processor receives the output of the previous processor. This means:
- Order matters - processors can depend on transformations made by earlier processors
- Processors should be idempotent when possible
- Be mindful of side effects

### 4. Error Handling

Processors should handle errors gracefully:
- Log errors appropriately
- Return original messages on failure (fail-safe behavior)
- Don't raise exceptions that could break message sending

Example error handling:

```python
def process(self, messages: List[MessageCreate], context: dict) -> List[MessageCreate]:
    try:
        # Your processing logic
        return processed_messages
    except Exception as e:
        from letta.log import get_logger
        logger = get_logger(__name__)
        logger.error(f"[MyProcessor] Error processing messages: {e}", exc_info=True)
        # Fail-safe: return original messages
        return messages
```

## Context Dictionary

Processors receive a context dictionary containing:

- **`agent_id`**: The agent ID the messages are being sent to
- **`actor`**: The user making the request (has `organization_id` and other user attributes)
- **`server`**: Optional `SyncServer` instance (if provided by the caller)
- **Additional context**: Any other context passed by the caller

Use the context to:
- Scope operations to the correct organization (`actor.organization_id`)
- Access user information
- Query the database or access server resources
- Make decisions based on the agent or user

## Best Practices

### 1. Keep Processors Focused

Each processor should have a single, well-defined responsibility. Don't create "god processors" that do everything.

### 2. Document Your Processor

Add clear docstrings explaining:
- What the processor does
- What context it requires
- What modifications it makes to messages
- Any side effects or dependencies

### 3. Use Logging Appropriately

Log at appropriate levels:
- `logger.debug()` - Detailed flow information
- `logger.info()` - Important state changes (e.g., "Processor X activated")
- `logger.warning()` - Non-critical issues (e.g., "No entries found, skipping")
- `logger.error()` - Errors that are handled gracefully

### 4. Test Your Processor

Test processors in isolation and in integration:
- Unit tests for processor logic
- Integration tests with actual message flows
- Test error conditions and edge cases

### 5. Consider Performance

Processors run on every message, so keep them efficient:
- Cache expensive operations when possible
- Use async database queries properly (see World Info processor for example)
- Avoid blocking operations in the processor
- Consider timeouts for external calls

## Maintaining Upstream Sync

### Integration Point Maintenance

When upstream Letta changes the API endpoints where we hook in:
1. Review the changes carefully
2. Update the hook point if needed (usually minimal)
3. Test that extensions still work
4. Update documentation if hook points change

### Extension Module Changes

Changes to extension modules don't affect upstream sync since they're separate from core code. However:
- Follow Letta's coding standards and patterns
- Use Letta's existing APIs and abstractions
- Don't duplicate functionality that exists in core

### Database Schema Changes

If your extension adds database tables:
- Use Alembic migrations (see World Info example)
- Ensure migrations are independent of core Letta migrations
- Test migrations on clean databases
- Document schema dependencies

## Extension Modules

Current extension modules:

- **`world_info/`** - World Info system (SillyTavern-style keyword-based prompt injection)
  - See `world_info/README.md` for detailed documentation

For information about specific extension implementations, see their individual README files.

## Future Enhancements

Potential improvements to the extension system:

- **Async processor support** - Allow processors to be async for better performance
- **Processor priority/ordering** - Explicit control over processor execution order
- **Conditional execution** - Processors that only run under certain conditions
- **Error handling framework** - Standardized error handling and recovery
- **Processor metrics** - Performance monitoring and metrics collection
- **Processor configuration** - Per-processor configuration system
