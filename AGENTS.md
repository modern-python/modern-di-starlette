# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`modern-di-starlette` is the [`modern-di`](https://github.com/modern-python/modern-di) integration
for [Starlette](https://www.starlette.io); [`CONTEXT.md`](CONTEXT.md) opens with what it does and
owns the vocabulary — read it before naming a concept in code, a test name, or an issue title. It is
one of that project's integrations, each of which lives in a separate repository and ships as a
separate PyPI package.

## Commands

`just` (task runner) and `uv` (package manager). The [`justfile`](justfile) is the source of truth —
`just --list`, or read it. The one thing it does not say: a `ty` suppression is written
`# ty: ignore`, never `# type: ignore`.

## Architecture

All implementation is `modern_di_starlette/main.py`, short enough to read whole. Read it. What that
read will not tell you: `modern-di-fastapi` is the closest sibling and FastAPI is built on Starlette,
so its shapes look transferable — but it exposes the child container through a yield dependency
rather than the ASGI scope, and the two packages diverge exactly there. Do not port a decision
across without checking it against [`docs/adr/`](docs/adr/).

### Testing patterns

`tests/dependencies.py` is the fixture model every test builds on: one `Group` spanning APP,
SESSION and REQUEST, including providers whose creators take the `Request` / `WebSocket` so context
injection is exercised rather than assumed.

## Workflow

Real work **not scheduled** becomes a GitHub issue.

An invariant is a test whose name is the claim, with a docstring opening `INVARIANT:` and a second
paragraph naming **what breaks it** — design rationale, not a report of what this one test catches.
Nothing enforces that docstring shape; it is read at review time.
