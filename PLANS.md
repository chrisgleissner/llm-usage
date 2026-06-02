llm-scheduler implementation plan

Status: complete.

1. Baseline and refactor scope
   - Inspect `llm-usage`, `llm-usage-tests.sh`, `README.md`, and licence style only.
   - Identify reusable non-UI functions for time, provider reads/normalization, Copilot capture, and JSON construction.
   - Preserve existing `llm-usage` option semantics, JSON keys, and table behaviour.

2. Shared Bash library
   - Add `lib/llm-common.sh` with no CLI argument parsing and minimal global side effects.
   - Move reusable detection/capture helpers from `llm-usage` into the library.
   - Keep presentation, colour, table rendering, and watch dispatch in `llm-usage`.
   - Add library seams for deterministic tests without real providers.

3. llm-usage compatibility
   - Update `llm-usage` to source the shared library.
   - Keep existing fast checks working.
   - Ensure `llm-usage --json` keeps top-level keys `generated_at`, `codex`, `claude`, `copilot`.

4. New `llm-scheduler`
   - Add executable root-level Bash script with project licence style.
   - Implement required CLI options: provider, prompt/prompt-file validation, timing, windows, threshold, polling, retry, cwd, fresh/tmux, command-template, auto-confirm toggles, log-dir, dry-run, wake, wake-test, help.
   - Use shared usage logic directly or through compatible library helpers, without duplicating provider parsers.
   - Implement provider adapters for Codex, Claude Code, and GitHub Copilot with safe defaults plus `--command-template`.
   - Preserve prompt file newlines and safely pass prompt content without `eval` in default paths.
   - Implement bounded PTY execution for interactive CLIs, recognised safe auto-confirm prompts only, full output capture, and meaningful exit codes.
   - Implement retry defaults exactly `60,180,600`, configurable and disableable.
   - Implement fresh foreground execution by default and tmux execution with clean skip/failure behaviour when tmux is absent.
   - Implement best-effort wake diagnostics and scheduling without requiring root or modifying system state.

5. Logging
   - Create default logs under `${XDG_CACHE_HOME:-$HOME/.cache}/llm-scheduler/logs`.
   - Use directory mode `700` and log file mode `600` where practical.
   - Log normalized args, prompt source, prompt SHA-256, full prompt, usage snapshots, wait decisions, command plans, CLI output, exit codes, retries, and final status.
   - Write a JSONL event log.

6. Tests
   - Extend Bash tests using temporary HOME/PATH fixtures and no network/provider calls.
   - Cover `llm-usage` JSON/table compatibility and library sourcing without UI execution.
   - Cover scheduler help and validation failures.
   - Cover immediate submit, exhausted usage dry-run/wait decision, Codex/Claude multi-window gating, retries fail/succeed, prompt file preservation, template metacharacters, safe auto-confirm, tmux skip, and wake dry-run/capability test.
   - Run `./llm-usage --json | jq . >/dev/null`, table check, `./llm-usage-tests.sh`, and `shellcheck` if installed.

7. Documentation
   - Update `README.md` to document both tools, install steps, dependencies, examples, limitations, command templates, logs, tmux, and best-effort wake behaviour.

Acceptance criteria

- Complete: `llm-scheduler` exists, is executable, and `--help` works.
- Complete: Codex, Claude, and Copilot provider selection is supported.
- Complete: Prompt text and prompt files are accepted, with exactly one required.
- Complete: Scheduler waits or dry-runs based on shared local usage data.
- Complete: Existing provider parsers are factored into shared code and not duplicated.
- Complete: `llm-usage` remains compatible after refactor.
- Complete: Retry defaults are exactly `60,180,600`.
- Complete: Logs capture prompt, usage, command plan, output, exit code, retries, and final status.
- Complete: Fresh-process execution is default; tmux mode is supported.
- Complete: Recognised safe confirmation prompts are acknowledged automatically by default and can be disabled.
- Complete: Wake support is best effort, safe, and documented.
- Complete: README and tests cover the user-visible behaviour.
- Complete: All available tests pass; `shellcheck` was skipped because it is not installed.
