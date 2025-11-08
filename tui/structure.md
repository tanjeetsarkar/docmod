# Graph TUI Application - Project Structure

## Directory Layout

```
graph-tui/
├── pyproject.toml
├── README.md
├── .python-version
├── src/
│   └── graph_tui/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py                 # Main Textual App
│       ├── config.py              # Configuration
│       │
│       ├── api/                   # GraphQL API Layer
│       │   ├── __init__.py
│       │   ├── client.py          # GraphQL client wrapper
│       │   ├── queries.py         # GraphQL queries
│       │   ├── mutations.py       # GraphQL mutations
│       │   └── subscriptions.py   # GraphQL subscriptions
│       │
│       ├── models/                # Data models
│       │   ├── __init__.py
│       │   ├── graph.py           # Graph model
│       │   ├── node.py            # Node model
│       │   └── execution.py       # Execution status model
│       │
│       ├── widgets/               # Custom Textual widgets
│       │   ├── __init__.py
│       │   ├── graph_canvas.py    # Main graph visualization
│       │   ├── node_widget.py     # Node representation
│       │   ├── edge_widget.py     # Edge rendering
│       │   ├── node_list.py       # Node tree/list view
│       │   ├── property_panel.py  # Properties editor
│       │   ├── execution_panel.py # Execution status
│       │   └── modals.py          # Dialog/modal windows
│       │
│       ├── screens/               # Textual screens
│       │   ├── __init__.py
│       │   ├── main_screen.py     # Main graph editor
│       │   ├── graph_list.py      # Graph selection screen
│       │   └── help_screen.py     # Keyboard shortcuts help
│       │
│       └── utils/                 # Utilities
│           ├── __init__.py
│           ├── layout.py          # Graph layout algorithms
│           ├── rendering.py       # Canvas rendering helpers
│           └── keybindings.py     # Keyboard shortcut handlers
│
└── tests/
    ├── __init__.py
    ├── test_api/
    ├── test_models/
    └── test_widgets/
```

## Initial Setup Commands

```bash
# Create project directory
mkdir graph-tui
cd graph-tui

# Initialize uv project
uv init

# Add dependencies
uv add textual rich httpx gql[all] networkx pydantic

# Add dev dependencies
uv add --dev pytest pytest-asyncio textual-dev

# Create directory structure
mkdir -p src/graph_tui/{api,models,widgets,screens,utils}
mkdir -p tests/{test_api,test_models,test_widgets}

# Create __init__.py files
touch src/graph_tui/__init__.py
touch src/graph_tui/{api,models,widgets,screens,utils}/__init__.py
touch tests/__init__.py

# Set Python version
echo "3.11" > .python-version
```

## pyproject.toml

```toml
[project]
name = "graph-tui"
version = "0.1.0"
description = "Terminal UI for FastAPI Graph Backend"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.47.0",
    "rich>=13.7.0",
    "httpx>=0.26.0",
    "gql[all]>=3.5.0",
    "networkx>=3.2",
    "pydantic>=2.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "textual-dev>=1.3.0",
]

[project.scripts]
graph-tui = "graph_tui.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = []
```

## Key Dependencies Explained

- **textual**: Modern TUI framework with rich widgets
- **rich**: Terminal formatting (used by Textual)
- **httpx**: Async HTTP client for GraphQL
- **gql[all]**: GraphQL client library with WebSocket support
- **networkx**: Graph algorithms for layout
- **pydantic**: Data validation and models

## Next Steps

1. Set up configuration management
2. Implement GraphQL client layer
3. Create data models
4. Build core widgets
5. Assemble the main application

Ready to start implementing?
```