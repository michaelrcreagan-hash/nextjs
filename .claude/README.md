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
auto-installs it for sessions in this repo. Cuts output tokens ~65% (terse
"caveman" phrasing, full technical accuracy kept).

Repo-wide, cross-agent activation ran via `caveman-init` — writes the same
always-on terse rule for every IDE agent, not just Claude Code:
`.cursor/rules/caveman.mdc`, `.windsurf/rules/caveman.md`,
`.clinerules/caveman.md`, `.github/copilot-instructions.md`,
`.opencode/AGENTS.md`, `AGENTS.md`. Re-run `node
.claude/plugins/marketplaces/caveman/src/tools/caveman-init.js --force` (or
`/caveman-init`) if these ever need regenerating.

Use `/caveman-compress <file>` to shrink CLAUDE.md/memory files into the same
format when one exists. Delegate locate/1-2-file-edit/review work to the
`cavecrew-investigator` / `cavecrew-builder` / `cavecrew-reviewer` subagents
(caveman-compressed output, ~60% fewer tokens back to main context) instead of
plain `Explore` where it fits.

## Autoresearch skill

Autonomous goal-directed iteration (modify → verify → keep/discard → repeat),
inspired by Karpathy's autoresearch.
Source: https://github.com/uditgoenka/autoresearch (manual install per its README).

- `skills/autoresearch/` — SKILL.md + reference files
- `commands/autoresearch.md` + `commands/autoresearch/` — `/autoresearch` and 13 subcommands
  (plan, debug, fix, security, ship, scenario, predict, learn, reason, improve, probe, evals, regression)
