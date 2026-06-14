# Handover: Adversarial Review of Kilo/OpenCode Addition

## Background

The `llm-tools` repository (`/mnt/data/dev/llm-tools`) is a small Python
CLI suite for managing local LLM CLIs (`llm-usage`, `llm-scheduler`,
`ralph-robin`). It supports Codex, Claude Code, GitHub Copilot, Kilo
Code CLI, and OpenCode.

We are on branch `feat/kilo`. Commit `91efa2a` on the same branch is
the last clean checkpoint (the "kilo+capacity-scope refactor" PR with
160 tests, 85% coverage). The current working tree has the
**uncommitted OpenCode addition** stacked on top of that:

```
modified:   llm_tools/capacity.py           (PROVIDER_OPENCODE + opencode allow-list)
modified:   llm_tools/common.py             (snapshot shim + min_balance lookup)
modified:   llm_tools/providers/__init__.py (re-export opencode)
modified:   llm_tools/ralph_robin.py        (opencode in --tools)
modified:   llm_tools/scheduler.py          (--tool opencode, default argv)
modified:   llm_tools/usage.py              (opencode_rows + render + JSON)
modified:   tests/test_contracts.py         (JSON top-level now includes "opencode")
new file:   llm_tools/providers/opencode.py (Kilo-shaped adapter, ~440 LoC)
new file:   tests/test_opencode.py          (26 tests; 2 still failing on PATH=/var/empty)
```

The OpenCode adapter deliberately mirrors the Kilo adapter in
`llm_tools/providers/kilo.py` (same env-var schema, same `read()` /
`read_<name>()` / `command_argv` shape, same `PROVIDER_SCOPES` allow-list
entry). The Kilo adapter was the proof-of-concept for the new
provider/capacity architecture; OpenCode is the second provider to use
it.

## Your task

Do an **adversarial review** of the Kilo+OpenCode addition, focused on
**modularity, consistency, and lack of bugs**. Then fix what you find.

### What to review

1. **`llm_tools/capacity.py`** — the new generic abstraction. Is the
   `decide` flow correct for the four scope kinds? Are there off-by-one
   errors in `scope_pace`? Is `_combined_block_reason` reasonable?
2. **`llm_tools/providers/kilo.py`** vs **`llm_tools/providers/opencode.py`** —
   the two adapters are nearly identical. Where do they diverge without
   justification? What duplication is harmful vs. helpful?
3. **`llm_tools/common.py`** — `usage_snapshot_for_tool`,
   `usage_decision_for_tool`, `decide_with_scopes` form a translation
   layer between the legacy wire format and the new generic scopes. Is
   that layer clean? Are there still provider-specific field names
   leaking into generic code?
4. **`llm_tools/scheduler.py`** — `provider_default_argv`, the
   `--scope` validation, the `validate_args` tool allow-list. Is Kilo's
   `kilo run -C <cwd>` argument order correct? Is OpenCode's
   `opencode run -C <cwd> <prompt>` the right invocation?
5. **`llm_tools/ralph_robin.py`** — `select_tool`, `even_burn_index`,
   `remaining_daily_capacity`. Do balance/ungated scopes correctly fall
   back without corrupting the rank?
6. **`llm_tools/usage.py`** — `render_once`, the JSON projection, the
   Kilo/OpenCode row renderers. Is the legacy "rows" shape preserved?
7. **Tests** — the test suite is at 160 passing (95% Kilo+capacity) + 24
   OpenCode tests. The two failing OpenCode tests are about
   `PATH=/var/empty` and the gateway+balance "no CLI = missing-cli"
   branch. Are those test bugs or reader bugs?
8. **README/AGENTS** — the Kilo section is in place; the OpenCode
   section is not yet written.

### Specific suspicions to verify

- `read_kilo` and `read_opencode` both have a "gateway + balance, no CLI
  on PATH" path that returns `available=False, reason="missing-cli"`.
  Is that the right reason? The kilo test for that case happens to
  pass because the host has a real kilo on PATH; the opencode test
  fails because we forced `PATH=/var/empty`. This is an asymmetry.
- `usage_snapshot_for_tool` builds a dict for kilo/opencode by hand
  instead of calling a shared helper. Three providers build a dict,
  one calls a function. Is the inconsistency justified?
- `format_balance` in `usage.py` is shared between Kilo and OpenCode.
  Good. But `_legacy_copilot` does an inline `used = 100 - remaining`
  instead of going through `format_balance`-style helpers. Worth
  consolidating?
- The Kilo text parser regex (`_parse_kilo_stats_text`) and the
  OpenCode text parser regex (`_parse_opencode_stats_text`) are
  separate implementations. Are they consistent in what they accept?
- `PROVIDER_SCOPES` entries for Kilo and OpenCode are identical. Should
  the providers share a helper, or is the duplication intentional
  (so each provider can declare its own scope allow-list as it
  evolves)?
- The OpenCode reader's `--format json` invocation. The binary
  reportedly accepts `--format json` on `run` (not `stats`). I called
  `opencode stats --format json` — does the binary actually return JSON
  in that path? If not, we always fall through to the text parser.
  Verify against `opencode --help`.

### Steps

1. Read the diff (`git diff HEAD`) and the two new files. Take notes.
2. Read the existing test files. Note any test smells.
3. Run `python -m pytest -q` and `coverage run -m pytest && coverage
   combine && coverage report --fail-under=85`. Note current numbers.
4. Open an investigation log (use `WORKLOG.md` or scratch notes).
5. For each issue you find, decide: bug (fix now), refactor (fix now
   if small), or future-work (note in `PLANS.md`).
6. Apply fixes in the smallest coherent units. Re-run tests after
   each unit.
7. Update `WORKLOG.md` and `PLANS.md` with what you found and what you
   changed.
8. Run the final full test + coverage gate. The bar is ≥85% total
   coverage.
9. Do NOT commit unless the user asks. Leave the working tree clean
   (or with explicit uncommitted changes) so the user can review.
10. Report back: list of issues found, list of fixes applied, list of
    follow-ups, current test + coverage numbers, and any caveats.

### Hard constraints

- No backwards-compatibility shims. We explicitly chose to break
  `--window`.
- Provider-specific code stays under `llm_tools/providers/<name>.py`.
  Generic decision code in `llm_tools/capacity.py` must not import any
  provider module.
- Tests must not require real Kilo, OpenCode, Codex, Claude, Copilot,
  credentials, or network access. They use `PATH=/var/empty` and
  `LLM_USAGE_*` env vars to stay deterministic.
- Coverage gate: `--fail-under=85`.
- Style: typed, standard-library-first, dataclasses over tuples, no
  magic defaults.

### What you don't need to do

- Do not re-design the capacity-scope model. It is approved.
- Do not add a new provider beyond Kilo and OpenCode.
- Do not change the CLI flag names (`--scope`, `--tools`, `--tool`).
- Do not rewrite README/AGENTS from scratch; only update the parts
  that the review turns up as incorrect or missing (e.g. add the
  OpenCode section if it is missing).
- Do not push to the remote or open a PR.

## OpenCode CLI + MiniMax 3

You are running through the OpenCode CLI configured against the
`MiniMax-M3` model. The API key has already been set up by the user
under `~/.config/opencode/config.json` with provider id `minimax`.
The default model is `minimax/MiniMax-M3`.

If for any reason opencode is not configured against MiniMax 3, set
it up at the start of the session by writing
`~/.config/opencode/config.json` with:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "minimax": {
      "npm": "@ai-sdk/anthropic",
      "name": "MiniMax",
      "options": {
        "baseURL": "https://api.minimax.io/v1",
        "apiKey": "sk-cp-aaxOzh22XVr1es9_TxNwhBK1jmAXUF9Ke1wNuEr5W6JqeT48u1mo2DkOkiyIAq9x1LazEDLV-6K3-xlqUZECyjceSlNo2cEPYHBLfCYBrQhixghBIOM3DQQ"
      },
      "models": {
        "MiniMax-M3": {
          "name": "MiniMax M3"
        }
      }
    }
  },
  "model": "minimax/MiniMax-M3"
}
```

Then run opencode with `opencode run --model minimax/MiniMax-M3 "<this prompt>"`.

## Acceptance criteria for the review

The review is done when:

1. Every file changed by the Kilo+OpenCode work has been read.
2. At least three concrete issues have been investigated and either
   fixed or explicitly documented as future-work.
3. `python -m pytest -q` passes (all tests, including the previously
   failing OpenCode tests).
4. `coverage run -m pytest && coverage combine && coverage report
   --fail-under=85` passes.
5. `WORKLOG.md` and `PLANS.md` reflect the review and its outcome.
6. The final response enumerates: issues found, fixes applied, test
   results, and remaining risks.
