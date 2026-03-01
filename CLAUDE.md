# Project: KivyMD Application

## Overview
A desktop application built with KivyMD 2.0 and Python, using SQLite databases for data storage. The project is managed under a Python `uv` virtual environment.

## Tech Stack
- **Language:** Python
- **UI Framework:** KivyMD 2.0 (Material Design for Kivy)
- **Database:** SQLite3 (`.db` file extension)
- **Package Manager:** uv

## Environment Setup
- All packages are managed through `uv`
- To add a new package: `uv add <package>`
- To run the app: `uv run python main.py`

## Project Structure
```
project-root/
├── CLAUDE.md
├── main.py              # App entry point
├── *.kv                 # KivyMD layout files
├── *.db                 # SQLite database files
├── pyproject.toml       # uv project config
└── ...
```

## Conventions
- KivyMD 2.0 API — use updated widget names and patterns (MDScreen, MDBoxLayout, etc.)
- Separate `.kv` files for layouts
- SQLite3 via Python's built-in `sqlite3` module
- Use parameterized queries (`?` placeholders) for all SQL — never string interpolation
- Database files use `.db` extension

## Database
- Engine: SQLite3
- Files: `*.db` in project directory
- Access: Python `sqlite3` standard library module
- Use views and joins as needed; parameterize queries at the application level

## Notes
- When adding packages, always use `uv add <package>`
- KivyMD 2.0 has breaking changes from 1.x — always reference 2.0 docs/API
- RecycleView is the preferred pattern for displaying large lists/grids
