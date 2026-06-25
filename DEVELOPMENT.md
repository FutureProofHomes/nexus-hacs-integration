# Development Guide

This guide provides instructions for setting up the development environment and running linting, formatting, and validation checks locally.

## Prerequisites

- Python 3.13 or later
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Git

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/ms1design/nexus-hacs-integration.git
cd nexus-hacs-integration
```

### 2. Create and activate virtual environment

```bash
uv venv
source .venv/bin/activate  # On Linux/Mac
# OR
.venv\Scripts\activate    # On Windows
```

### 3. Install dependencies

```bash
uv pip install -r requirements.txt
```

## Running Linter

The project uses [Ruff](https://github.com/astral-sh/ruff) for linting, which is configured in `.ruff.toml`.

### Run linter

```bash
python -m ruff check .
```

### Fix auto-fixable issues

```bash
python -m ruff check --fix .
```

### Show detailed explanations for issues

```bash
python -m ruff check --explain .
```

## Running Formatter

Ruff also provides formatting capabilities.

### Check formatting

```bash
python -m ruff format . --check
```

### Apply formatting

```bash
python -m ruff format .
```

## Common Linting Issues

### Import Organization (I001)

Ruff enforces sorted imports. To fix:

```bash
python -m ruff check --select I001 --fix .
```

### Type Checking Imports (TC002)

Imports that should be in type-checking blocks:

```bash
# Move these imports after TYPE_CHECKING guard
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.images_response import ImagesResponse
    from homeassistant.helpers.typing import ConfigType
```

### Unused Arguments (ARG001)

Remove unused function arguments or add `# noqa: ARG001` if intentional.

### Line Length (E501)

Lines should be <= 88 characters. Use:

```bash
python -m ruff format .
```

## Running Validation

### HACS Validation

```bash
pip install hacs-validation
hacs validate
```

### Home Assistant Core Validation (hassfest)

```bash
pip install hassfest
hassfest --config custom_components/nexus_conversation/manifest.json
```

## GitHub Actions

The project uses GitHub Actions for:

- **Linting**: Runs on every push and pull request to main
- **Validation**: Runs on every push and pull request to main
- **Hassfest**: Validates integration manifest
- **Release**: Automatically creates releases when manifest.json version is updated

## Pre-commit Hooks

To run checks before each commit, install pre-commit:

```bash
pip install pre-commit
pre-commit install
```

This will automatically run:
- Ruff linter
- Ruff formatter check
- Other configured hooks

## Fixing Specific Issues

### Import Order

The project follows Home Assistant's import order:

1. Future imports
2. Standard library imports
3. Third-party imports
4. Home Assistant imports
5. Local imports

Example:

```python
from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import openai
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entity import NexusBaseLLMEntity
```

### Type Checking Blocks

Use `TYPE_CHECKING` for imports only needed for type hints:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.responses import Response
    from homeassistant.helpers.typing import ConfigType
```

### Docstrings

All functions and classes should have docstrings following Google style:

```python
def my_function(param: str) -> bool:
    """Brief description.
    
    Detailed description if needed.
    
    Args:
        param: Description of parameter.
    
    Returns:
        Description of return value.
    """
    pass
```

## Running Tests

To run tests locally:

```bash
pip install pytest pytest-homeassistant-custom-component
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run linting and formatting checks
5. Commit your changes
6. Push to your fork
7. Open a pull request

## Version Management

The version is managed in `custom_components/nexus_conversation/manifest.json`. When updating the version:

1. Update the version in manifest.json
2. Commit the change
3. Push to main branch
4. GitHub Actions will automatically create a release

Example version format: `0.0.3`

## Troubleshooting

### Ruff not found

Make sure you have activated the virtual environment:

```bash
source .venv/bin/activate
```

### Import errors

Ensure all dependencies are installed:

```bash
uv pip install -r requirements.txt
```

### Formatting conflicts

If you have formatting conflicts with other tools (like Black), run:

```bash
python -m ruff format .
```

This will standardize the formatting according to the project's configuration.
