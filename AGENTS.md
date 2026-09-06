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

**The spec for a change is its PR body**, not a committed file: why, design, non-goals,
verification, reviewed with the diff. There is no change file and no lane to choose. A trivial PR
(typo, dep bump, formatter, CI tweak) ships a conventional-commit title with no body ceremony.

Two things outlive the PR, and there are exactly two places to put them: an alternative **rejected**
with reasoning becomes an ADR in [`docs/adr/`](docs/adr/) (`NNNN-slug.md`, sequential, with a
revisit trigger), and real work **not scheduled** becomes a GitHub issue. There is no third state,
and no separate truth-home directory — a behaviour change is reviewed with the diff, not promoted
to a page.

### Where a fact goes

Four homes, one owner each:

| Home | Holds |
|---|---|
| `modern_di_starlette/` | anything readable from the module — the default |
| a named test | an **invariant**: must stay true, and a change could silently break it |
| `docs/adr/` | a rejected alternative, with the reasoning that would otherwise be re-litigated |
| `README.md` | anything a user needs |

Before writing a line anywhere:

> Can an agent get this by reading `modern_di_starlette/`? → **don't write it.**
> Would a wrong change here fail a test? → it belongs **in the test**, not in prose.
> Does a user need it? → **`README.md`**.
> Otherwise it does not get written.

**Prose about mechanism has no home. There is no file to add a paragraph to.** This file included:
it is always loaded, so a line that restates a docstring, a justfile comment, or `pyproject.toml`
costs every turn and rots in two places at once. A package this small tempts a full restatement of
its own source; that is the failure mode to watch for here.

An invariant is a test whose name is the claim, with a docstring opening `INVARIANT:` and a second
paragraph naming **what breaks it** — design rationale, not a report of what this one test catches.
Nothing enforces that docstring shape; it is read at review time. A relative link to an ADR *is*
checked — CI runs lychee `--offline` over every `.md` — but a path named in a docstring or a
comment is not. Both ADRs and `INVARIANT:` docstrings ratchet: nothing prunes a record once its
call is settled. Keeping them lean is a standing habit.
