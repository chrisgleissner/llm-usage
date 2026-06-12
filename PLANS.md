# Python Migration Plan

## Current Understanding

This repository provides three Linux CLI tools for local LLM provider usage and orchestration:

- `llm-usage`: renders provider quota/usage information in table, JSON, watch, and Claude statusline modes.
- `llm-scheduler`: waits until a selected provider appears usable, then launches the provider CLI with prompt handling, retry, logging, optional tmux, and optional wake/suspend behavior.
- `ralph-robin`: rotates across configured providers and delegates launch/wait behavior to `llm-scheduler`.
- `llm_tools/common.py`: shared Python helper library for provider readers, normalization, cache paths, time formatting, prompt/argv helpers, subprocess execution, and JSON conversion.

The requested end state is Python-only for the three tools and shared helper library, with all visible behavior preserved.

## Inventory

Repository files discovered:

- Executables: `llm-usage`, `llm-scheduler`, `ralph-robin`
- Shared helper: `llm_tools/common.py`
- Test suite: `tests/`
- User docs: `README.md`
- Internal instructions: `AGENTS.md`
- Planning artifacts: `PLANS.md`, `WORKLOG.md`
- CI: `.github/workflows/test.yml`, Ubuntu, Python 3.11, installs package plus pytest/coverage, runs coverage-enforced tests.
- Packaging: `pyproject.toml` with console scripts for `llm-usage`, `llm-scheduler`, and `ralph-robin`.
- Public command files are Python entry scripts that allow direct checkout usage.

## Observable Behaviours To Preserve

- CLI names, option names, defaults, validation, usage/help output, exit statuses, stdout/stderr split, and ordering.
- Provider reader behavior for Codex, Claude Code/API/cache/statusline/local data, and GitHub Copilot.
- Cache locations and migration from legacy cache directories.
- JSON top-level keys and unavailable shapes.
- Table layout, color behavior, missing-value rendering, remaining-time estimation, and source display.
- Scheduler prompt loading, prompt file permissions, logs, run directory layout, provider command construction, retry decisions, attached/headless behavior, tmux behavior, wake/suspend behavior, and signal handling.
- Ralph Robin provider rotation, state file behavior, logging, delegation to scheduler, and exact provider stdout passthrough.
- Environment variables documented in `AGENTS.md` and any additional variables discovered in code.

Discovery details:

- Direct provider commands: `codex`, `claude`, `copilot`, `github-copilot`.
- External commands used by the Python implementation where relevant: provider CLIs (`codex`, `claude`, `copilot`/`github-copilot`), `date` fallback parsing/formatting, `script` for attached terminal mode, `tmux`, `systemd-run`, `systemctl`, `rtcwake`, and `sync`.
- Environment variables read include: `XDG_CACHE_HOME`, `HOME`, `PATH`, `TERM`, `LLM_USAGE_NO_COLOR`, `LLM_USAGE_SHOW_SOURCE`, `LLM_USAGE_SHOW_REMAINING_TIME`, `LLM_USAGE_SHOW_CODEX_SPARK`, `LLM_USAGE_NOW_EPOCH`, `LLM_USAGE_MAX_FILES`, `LLM_USAGE_TAIL_LINES`, `LLM_USAGE_LOG_TAIL_LINES`, `LLM_USAGE_REMAINING_TIME_STALE_MULTIPLIER`, `LLM_USAGE_REMAINING_TIME_MAX_STALE_SECONDS`, `LLM_USAGE_DISABLE_COPILOT`, `LLM_USAGE_COPILOT_TIMEOUT`, `LLM_USAGE_COPILOT_CAPTURE_TEXT`, `LLM_USAGE_COPILOT_CAPTURE_CMD`, `LLM_USAGE_COPILOT_CACHE_TTL`, `LLM_USAGE_COPILOT_REFRESH_WAIT`, `LLM_USAGE_COPILOT_CWD`, `LLM_USAGE_COPILOT_CAPTURE_CWD`, `LLM_USAGE_COPILOT_MONTHLY_RESET_OFFSET_DAYS`, `LLM_SCHEDULER_PRE_SUSPEND_CONFIRMATION_SECONDS`, `LLM_SCHEDULER_NO_STREAM`, `LLM_SCHEDULER_HEADLESS`, `LLM_SCHEDULER_USAGE_JSON`, `LLM_SCHEDULER_NO_ACTUAL_SUSPEND`, `LLM_SCHEDULER_PTY_TIMEOUT`, `LLM_SCHEDULER_IDLE_TIMEOUT`, `LLM_SCHEDULER_QUESTION_IDLE_TIMEOUT`, `LLM_SCHEDULER_TMUX_TIMEOUT`, `LLM_SCHEDULER_WAKE_MIN_LEAD`, `LLM_SCHEDULER_SUSPEND_MIN_LEAD`.
- Files read: Codex JSONL under `~/.codex/sessions`, Claude credentials/cache/status/project JSONL, Copilot cache, prompt files, run-dir prompt copy/state/log files.
- Files written: usage log/cache files under `llm-tools/llm-usage`, scheduler run logs/events/prompt/attempt status/output files, Ralph Robin run logs/state, latest symlinks, Copilot refresh lock/cache temp files.
- Stdout behavior: `llm-usage` table/JSON/statusline/watch frames; `llm-scheduler` dry-run/success/scheduled lines plus streamed child output unless suppressed; `ralph-robin` selection/log notices plus streamed scheduler/provider output.
- Stderr behavior: validation errors, scheduler autonomy abort/failure lines, suspend scheduling fallback warnings, Ralph Robin autonomy-blocked/failure lines.

## Contract-Test Matrix

Tests will be Python `pytest` black-box tests against the public CLI names. They will run first against the current Bash implementation, then against the Python implementation.

- `llm-usage`: help/usage, invalid options, JSON validity, table output, color disabling, statusline stdin/cache, provider unavailable paths, Codex/Claude/Copilot fixture parsing, source and remaining-time flags.
- `llm-scheduler`: help/usage, missing/invalid args, invalid tool/window combinations, prompt and prompt-file handling including spaces/empty/large files, dry-run command construction, usage injection, rate-limited waits bounded by test knobs, provider stdout/stderr routing, provider non-zero handling, retry/no-retry decisions, logs and run-dir creation, headless interruption paths where practical.
- `ralph-robin`: help/usage, provider selection/rotation with fake usage, delegation command construction, state/log handling, failure rotation, and byte-for-byte stdout passthrough for plain text, multiline, no trailing newline, ANSI, UTF-8, stderr progress, and non-zero after partial stdout.

## Migration Phases

- [x] Phase 1: Discovery of current implementation, docs, tests, CI, external commands, environment variables, files, stdout/stderr behavior.
- [x] Phase 2: Add black-box pytest contract tests for visible behavior.
- [x] Phase 3: Introduce Python project structure, packaging, and shared modules.
- [x] Phase 4: Port helper/tool slices and keep tests green.
- [x] Phase 5: Preserve executable names through packaging entry points and Python direct-run scripts.
- [x] Phase 6: Add coverage measurement and quality gates with at least 80 percent coverage.
- [x] Phase 7: Remove obsolete Bash implementations/helper library and stale references.

## Coverage Plan

- Use `coverage.py` through `pytest-cov` or direct `coverage run -m pytest`.
- Measure only the new Python package/modules, excluding tests and trivial wrapper glue if appropriate.
- Add focused unit tests for parser/config/provider helpers and contract tests for CLI-visible behavior.
- Enforce `--cov-fail-under=80`.

## CI Plan

- GitHub Actions uses Python 3.11, installs the package and pytest/coverage, runs `coverage run -m pytest`, combines subprocess coverage data, and enforces `coverage report --fail-under=80`.

## Risks And Mitigations

- Large Bash behavior surface: mitigate with black-box tests before porting and incremental slices.
- PTY/attached terminal semantics: keep subprocess/PTY code isolated and tested with fake CLIs.
- Exact stdout passthrough for `ralph-robin`: use byte-level tests and avoid text transformations on provider stdout.
- Time, wake, and suspend behavior: isolate system interactions behind functions with deterministic test hooks.
- Provider parsing variability: preserve fixture behavior from existing tests and add targeted tests before changing parsers.

## Current Task List

- [x] Create/update `PLANS.md` for the Python migration.
- [x] Append migration notes to `WORKLOG.md`.
- [x] Complete discovery and update this plan with concrete findings.
- [x] Add pytest contract harness and fixtures.
- [x] Confirmed tests exercise visible behavior with fake providers.
- [x] Implement Python package and entry points.
- [x] Port shared helper logic.
- [x] Port `llm-usage`.
- [x] Port `llm-scheduler`.
- [x] Port `ralph-robin`.
- [x] Remove obsolete Bash tool/helper implementations.
- [x] Update docs and CI.
- [x] Run full validation and record results.

## Explicit Termination Criteria

This task is complete only when:

- `PLANS.md` and `WORKLOG.md` are accurate.
- The three public tool names invoke Python implementations.
- No Bash implementation remains for the tools or shared helper library.
- Deterministic tests pass without live provider credentials.
- Coverage over the Python implementation is at least 80 percent.
- CI enforces tests and coverage.
- User-facing docs/help/output do not mention the implementation transition.
- No intentional visible-behavior deviations remain, or any unavoidable deviation is documented in `WORKLOG.md`.
