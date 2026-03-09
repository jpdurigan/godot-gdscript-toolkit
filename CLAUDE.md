# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GDScript Toolkit is a Python-based set of tools for working with GDScript (Godot's scripting language): **gdparse** (parser/debugger), **gdlint** (linter), **gdformat** (formatter), **gd2py** (converter), and **gdradon** (complexity metrics). This is a maintained fork of [Scony/godot-gdscript-toolkit](https://github.com/Scony/godot-gdscript-toolkit).

## Commands

```bash
# Run tests
make          # runs pytest -v
tox           # full suite (tests, lint, type check, format)
tox -e py3    # just pytest
pytest tests/formatter/test_formatter.py  # run a single test file
pytest -k "test_name"                     # run a single test by name

# Lint/format (dev tools)
tox -e lint   # pylint + flake8
tox -e format # check black formatting
tox -e mypy   # type checking

# Install for development
pip3 install -e .

# CLI tools (after install)
gdparse file.gd
gdlint file.gd
gdformat file.gd
```

## Architecture

All source lives in `gdtoolkit/`. The data flow is:

```
GDScript Source
      ↓
  [parser/]  ← Lark grammar (gdscript.lark, comments.lark)
      ↓  Lark Tree
  [linter/]  [formatter/]  [gd2py/]  [gdradon/]
```

**`gdtoolkit/parser/`** — Uses Lark (LALR) to parse GDScript. `parser.py` is the main class; `gdscript.lark` is the grammar. Comments are parsed separately via `comments.lark`.

**`gdtoolkit/linter/`** — Walks the Lark parse tree. Check logic is split into focused modules: `name_checks.py`, `design_checks.py`, `format_checks.py`, `basic_checks.py`, `class_checks.py`, `misc_checks.py`, `if_return_checks.py`. Configuration is an immutable `MappingProxyType` dict; `DEFAULT_CONFIG` in `__init__.py`.

**`gdtoolkit/formatter/`** — Transforms the parse tree back to formatted source. `formatter.py` has the main `format_code()` entry point. `context.py` tracks state (indentation, line numbers, pending comments) during the pass. `safety_checks.py` validates that the output re-parses to the same tree, is stable on a second format pass, and preserves all comments.

**`gdtoolkit/common/`** — Shared utilities: file discovery (`utils.py`), version/cache management (`version.py`), exceptions (`exceptions.py`).

**Tests** in `tests/` mirror the package structure. Formatter tests use input/output `.gd` file pairs. `tests/valid-gd-scripts/` and `tests/invalid-gd-scripts/` hold fixture files.

## Key Design Notes

- **Formatter safety**: After formatting, three invariants are checked — parse tree preserved, output is stable (formatting again yields the same result), and no comments were dropped.
- **Formatter disable/enable**: Regions can be excluded with `# gdformat: off` / `# gdformat: on` comments.
- **Linter config**: Passed as a dict to `lint_code()`; merges with `DEFAULT_CONFIG`. Supports per-line `# gdlint: ignore` comments.
- **Grammar changes**: Modifying `gdscript.lark` affects everything downstream (parser, linter, formatter). Always run the full test suite after grammar edits.
- **Python ≥ 3.7 required**; primary dependency is `lark-parser==0.8.0` (pinned).
