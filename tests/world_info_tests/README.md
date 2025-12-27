# World Info Test Organization

This directory contains organized test files for the World Info system.

## Structure

```
tests/world_info_tests/
├── conftest.py              # Shared fixtures and utilities
├── test_world_info_api.py   # Core API CRUD tests (keep minimal)
├── test_world_info_matcher.py  # Detailed matcher tests (if needed)
├── test_world_info_scanner.py  # Scanner tests (if needed)
└── test_world_info_processor.py # Processor integration tests (if needed)
```

## Usage

Pytest automatically discovers all test files. Run tests with:

```bash
# Run all World Info tests
pytest tests/world_info_tests/

# Run specific test file
pytest tests/world_info_tests/test_world_info_api.py

# Run specific test
pytest tests/world_info_tests/test_world_info_api.py::test_create_entry
```

## Shared Fixtures

All fixtures in `conftest.py` are automatically available to all test files in this directory and subdirectories. The root `conftest.py` is also available via imports.

## Organization Strategy

- **Keep `test_world_info_api.py` minimal** - Only essential CRUD and core functionality
- **Add detailed tests to separate files** - When you need comprehensive coverage of specific components
- **Use descriptive file names** - Makes it clear what each file tests

