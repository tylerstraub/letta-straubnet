# World Info Tests - Quick Start Guide

## Overview

The World Info tests are now organized in a subdirectory structure, following the same pattern as `managers/` and `mcp_tests/` in this codebase.

## Current Structure

```
tests/world_info_tests/
├── conftest.py                    # Shared fixtures (WorldInfoClient, test_agent, etc.)
├── test_world_info_api.py         # Core API tests (7 tests - essential only)
├── test_world_info_matcher.py.example  # Example template for detailed matcher tests
└── README.md                      # Full documentation
```

## Running Tests

```bash
# Run all World Info tests
pytest tests/world_info_tests/

# Run specific file
pytest tests/world_info_tests/test_world_info_api.py

# Run specific test
pytest tests/world_info_tests/test_world_info_api.py::test_create_entry

# Run with verbose output
pytest tests/world_info_tests/ -v
```

## Adding New Test Files

When you want to add more detailed tests, create new files in this directory:

1. **For matcher tests**: Create `test_world_info_matcher.py`
   - Copy `test_world_info_matcher.py.example` as a starting point
   - Add your detailed matcher unit tests here

2. **For scanner tests**: Create `test_world_info_scanner.py`
   - Test text extraction from various message formats

3. **For processor tests**: Create `test_world_info_processor.py`
   - Integration tests for the full processor flow

All fixtures from `conftest.py` are automatically available to all test files in this directory.

## Migration Complete

The old `tests/test_world_info.py` file has been removed. All tests are now in the `tests/world_info_tests/` directory structure.

## Fixtures Available

All test files in `world_info_tests/` automatically have access to:

- `world_info_client` - Pre-configured API client
- `test_agent` - Test agent fixture with automatic cleanup
- All fixtures from root `tests/conftest.py` (e.g., `server_url`, `default_user`)

## Example: Adding a New Test File

```python
# tests/world_info_tests/test_world_info_matcher.py
"""
Detailed matcher unit tests.
"""

import pytest

# Fixtures from conftest.py are automatically available
# You can use world_info_client, test_agent, etc.

def test_matcher_whole_words():
    """Test whole word matching."""
    # Your test code here
    pass
```

