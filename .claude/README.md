# Project Claude Code setup

Vendored tooling, committed so it survives fresh clones and ephemeral sessions.

## CBT Framework

AI-powered backtesting framework — idea to live trading bot in one workflow.
Source: https://github.com/Trade-With-Claude/cbt-framework (installed via `npx cbt-framework`, vendored here; version in `.claude/cbt-framework/VERSION`).

- `commands/cbt/` — 21 slash commands (`/cbt:new`, `/cbt:discover`, `/cbt:research`, `/cbt:eda`, `/cbt:plan`, `/cbt:build`, `/cbt:run`, `/cbt:analyze`, `/cbt:optimize`, `/cbt:live`, ...)
- `agents/cbt-*.md` — 4 agents: cbt-analyzer, cbt-researcher, cbt-builder, cbt-eda
- `cbt-framework/` — engine, templates (pandas + fast, 4 exchange live-bot templates), references

The cbt commands reference support files at `~/.claude/cbt-framework/`; the
`SessionStart` hook in `settings.json` syncs `.claude/cbt-framework/` there on
each session start.

## Caveman plugin

Marketplace + plugin from https://github.com/JuliusBrussee/caveman, registered
in `settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) so Claude Code
auto-installs it for sessions in this repo.

## Autoresearch skill

Autonomous goal-directed iteration (modify → verify → keep/discard → repeat),
inspired by Karpathy's autoresearch.
Source: https://github.com/uditgoenka/autoresearch (manual install per its README).

- `skills/autoresearch/` — SKILL.md + reference files
- `commands/autoresearch.md` + `commands/autoresearch/` — `/autoresearch` and 13 subcommands
  (plan, debug, fix, security, ship, scenario, predict, learn, reason, improve, probe, evals, regression)
