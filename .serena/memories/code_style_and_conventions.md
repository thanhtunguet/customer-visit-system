# Code Style and Conventions

## Python (Backend)

- **Formatting**: The Python codebase is formatted using `black`. To format the code, run:
  ```bash
  make fmt
  ```
- **Linting**: There is currently no linter configured. It is recommended to set up a linter like `ruff` or `flake8` to ensure code quality. A placeholder `lint` command exists in the `Makefile`.
- **Type Hinting**: The codebase uses Python's type hints, and they should be used for all new code.
- **Docstrings**: (Not specified, but it is good practice to add docstrings to public modules, classes, and functions).

## TypeScript/JavaScript (Frontend)

- **Formatting**: The frontend codebase formatting is managed by Prettier, which is often integrated into IDEs and run on save. Configuration for Prettier might be in `package.json` or a dedicated configuration file.
- **Linting**: ESLint is typically used in React projects, but a configuration file is not immediately visible. It's recommended to add a linting step to the `package.json` scripts.

## Naming Conventions

- **Python**: Follows PEP 8 conventions (e.g., `snake_case` for variables and functions, `PascalCase` for classes).
- **TypeScript**: Follows standard TypeScript conventions (e.g., `camelCase` for variables and functions, `PascalCase` for components and types).
