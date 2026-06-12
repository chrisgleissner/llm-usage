from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any

from . import common


APP_NAME = "llm-usage"
TOOL_COL_WIDTH = 14
TABLE_GAP_WIDTH = 3


USAGE = """Usage: llm-usage [--json] [--watch SECONDS] [--show-copilot-credits] [--statusline] [--no-header] [--log-only]

Shows remaining percentage for:
  - Codex current session / 5-hour window
  - Codex Spark current session / 5-hour window
  - Codex weekly / 7-day window
  - Codex Spark weekly / 7-day window
  - Claude Code current session / 5-hour window
  - Claude Code weekly / 7-day window
  - Copilot monthly usage
  - Copilot AI credits (optional, with --show-copilot-credits)

Options:
  --json              Emit JSON instead of a table.
  -w, --watch SECONDS  Refresh repeatedly.
  --show-copilot-credits  Show Copilot AI credits row.
  --show-source         Show Source column. By default, Source is hidden.
  --hide-source         Hide Source column (default).
  --show-remaining-time  Show Remaining Time column (default).
  --hide-remaining-time Hide Remaining Time column.
  --show-codex-spark    Show Codex Spark rows (default).
  --hide-codex-spark    Hide Codex Spark rows.
  --copilot-monthly-reset-offset-days DAYS  Day offset from month start for Copilot monthly reset (default: 0).
  --statusline        Read Claude Code statusline JSON from stdin, cache it, print compact line.
  --log-only          Sample providers and append to the usage log without printing a table.
  --no-header         Omit table header.
  -h, --help          Show this help.
"""


class Config:
    def __init__(self) -> None:
        env = os.environ
        self.watch_interval = "0"
        self.json_output = False
        self.statusline_mode = False
        self.log_only = False
        self.no_header = False
        self.show_copilot_credits = False
        self.show_source = env.get("LLM_USAGE_SHOW_SOURCE", "0") == "1"
        self.show_remaining_time = env.get("LLM_USAGE_SHOW_REMAINING_TIME", "1") != "0"
        self.show_codex_spark = env.get("LLM_USAGE_SHOW_CODEX_SPARK", "1") != "0"
        self.color_enabled = sys.stdout.isatty() and not env.get("LLM_USAGE_NO_COLOR") and env.get("TERM") != "dumb"


def parse_args(argv: list[str]) -> Config:
    cfg = Config()
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            cfg.json_output = True
            i += 1
        elif arg in ("-w", "--watch"):
            if i + 1 >= len(argv):
                common.err(f"{arg} requires seconds")
                raise SystemExit(2)
            cfg.watch_interval = argv[i + 1]
            i += 2
        elif arg == "--show-copilot-credits":
            cfg.show_copilot_credits = True
            i += 1
        elif arg == "--show-source":
            cfg.show_source = True
            i += 1
        elif arg == "--hide-source":
            cfg.show_source = False
            i += 1
        elif arg == "--show-remaining-time":
            cfg.show_remaining_time = True
            i += 1
        elif arg == "--hide-remaining-time":
            cfg.show_remaining_time = False
            i += 1
        elif arg == "--show-codex-spark":
            cfg.show_codex_spark = True
            i += 1
        elif arg == "--hide-codex-spark":
            cfg.show_codex_spark = False
            i += 1
        elif arg == "--copilot-monthly-reset-offset-days":
            if i + 1 >= len(argv):
                common.err("--copilot-monthly-reset-offset-days requires DAYS")
                raise SystemExit(2)
            os.environ["LLM_USAGE_COPILOT_MONTHLY_RESET_OFFSET_DAYS"] = argv[i + 1]
            i += 2
        elif arg == "--statusline":
            cfg.statusline_mode = True
            i += 1
        elif arg == "--log-only":
            cfg.log_only = True
            i += 1
        elif arg == "--no-header":
            cfg.no_header = True
            i += 1
        elif arg in ("-h", "--help"):
            print(USAGE, end="")
            raise SystemExit(0)
        else:
            common.err(f"unknown option: {arg}")
            print(USAGE, end="", file=sys.stderr)
            raise SystemExit(2)
    if not re_int(os.environ.get("LLM_USAGE_COPILOT_MONTHLY_RESET_OFFSET_DAYS", "0"), allow_negative=True):
        common.err("--copilot-monthly-reset-offset-days expects an integer")
        raise SystemExit(2)
    if cfg.watch_interval != "0" and not common.is_number(cfg.watch_interval):
        common.err("--watch requires numeric seconds")
        raise SystemExit(2)
    return cfg


def re_int(value: str, allow_negative: bool = False) -> bool:
    import re

    return bool(re.fullmatch(r"-?[0-9]+" if allow_negative else r"[0-9]+", value or ""))


def colorize_percent(value: str, cfg: Config) -> str:
    if not cfg.color_enabled or value in {"-", "unavailable", "unknown", ""}:
        return value
    try:
        integer = int(float(value.rstrip("%")))
    except ValueError:
        return value
    if integer < 10:
        return f"\033[0;31m{value}\033[0m"
    if integer < 30:
        return f"\033[0;33m{value}\033[0m"
    return f"\033[0;32m{value}\033[0m"


def visible_len(text: str) -> int:
    import re

    return len(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text))


def cell(width: int, text: str, gap: bool = False) -> str:
    pad = max(0, width - visible_len(text))
    return text + (" " * pad) + (" " * TABLE_GAP_WIDTH if gap else "")


def rule(width: int, gap: bool = False) -> str:
    return "-" * width + (" " * TABLE_GAP_WIDTH if gap else "")


def format_tool_name(name: str) -> str:
    if name == "GPT-5.3-Codex-Spark" or ("GPT-5.3" in name and "Codex" in name and "Spark" in name):
        return "GPT-5.3 Spark"
    return name


def print_value_row(cfg: Config, provider: str, window: str, remaining: str, remaining_time: str, reset_text: str, time_to_reset: str, source: str) -> None:
    parts = [
        cell(TOOL_COL_WIDTH, provider, True),
        cell(12, window, True),
        cell(11, colorize_percent(remaining, cfg), True),
    ]
    if cfg.show_remaining_time:
        parts.append(cell(14, remaining_time, True))
    parts.append(cell(16, reset_text, True))
    if cfg.show_source:
        parts.append(cell(12, time_to_reset, True))
        parts.append(source)
    else:
        parts.append(cell(12, time_to_reset, False))
    print("".join(parts))


def print_row(cfg: Config, provider: str, window: str, used: Any, reset: Any, source: str, display_provider: str | None = None) -> None:
    remaining = common.remaining_from_used(used)
    remaining_text = common.fmt_pct(remaining) if remaining is not None else "-"
    if remaining_text not in {"-", "unknown"}:
        remaining_text += "%"
    remaining_time = "-"
    if cfg.show_remaining_time:
        remaining_time = common.estimate_remaining_time_from_log(provider, window, remaining)
    reset_text = common.fmt_reset(reset) or "-"
    print_value_row(cfg, display_provider or provider, window, remaining_text, remaining_time, reset_text, common.time_until(reset), source)


def log_and_print_row(cfg: Config, provider: str, window: str, used: Any, reset: Any, source: str, display_provider: str | None = None) -> None:
    remaining = common.remaining_from_used(used)
    common.log_usage_sample(provider, window, remaining)
    print_row(cfg, provider, window, used, reset, source, display_provider)


def print_unavailable_rows(cfg: Config, provider: str) -> None:
    rem_time = "-" if cfg.show_remaining_time else ""
    print_value_row(cfg, provider, "5h", "-", rem_time, "-", "-", "no local data")
    print_value_row(cfg, provider, "weekly", "-", rem_time, "-", "-", "no local data")


def print_codex_rows(cfg: Config, codex_json: dict[str, Any] | None) -> None:
    if not codex_json:
        print_unavailable_rows(cfg, "Codex")
        return
    rows = codex_json.get("rows") if isinstance(codex_json.get("rows"), list) else []
    if not rows:
        source = codex_json.get("source", "")
        log_and_print_row(cfg, "Codex", "5h", (codex_json.get("five_hour") or {}).get("used"), (codex_json.get("five_hour") or {}).get("resets_at"), source)
        log_and_print_row(cfg, "Codex", "weekly", (codex_json.get("week") or {}).get("used"), (codex_json.get("week") or {}).get("resets_at"), source)
        return
    for row in rows:
        key = row.get("key", "codex")
        provider = row.get("name", "Codex")
        is_spark = key == "codex-spark" or "spark" in provider.lower()
        if is_spark and not cfg.show_codex_spark:
            continue
        source = row.get("source") or codex_json.get("source", "")
        log_and_print_row(cfg, provider, "5h", (row.get("five_hour") or {}).get("used"), (row.get("five_hour") or {}).get("resets_at"), source, format_tool_name(provider))
        log_and_print_row(cfg, provider, "weekly", (row.get("week") or {}).get("used"), (row.get("week") or {}).get("resets_at"), source, format_tool_name(provider))


def print_copilot_rows(cfg: Config, copilot_json: dict[str, Any] | None) -> None:
    reset_epoch = common.copilot_monthly_reset_epoch()
    reset_text = common.fmt_reset(reset_epoch) or "-"
    to_reset = common.time_until(reset_epoch)
    rem_time = "-" if cfg.show_remaining_time else ""
    if not copilot_json:
        print_value_row(cfg, "Copilot", "monthly", "unavailable", rem_time, reset_text, to_reset, "copilot cli")
        if cfg.show_copilot_credits:
            print_value_row(cfg, "Copilot", "ai-credits", "unavailable", rem_time, "-", "-", "copilot cli")
        return
    source = copilot_json.get("source", "copilot cli")
    if copilot_json.get("available") is False:
        print_value_row(cfg, "Copilot", "monthly", "unavailable", rem_time, reset_text, to_reset, source)
        if cfg.show_copilot_credits:
            print_value_row(cfg, "Copilot", "ai-credits", "unavailable", rem_time, "-", "-", source)
        return
    monthly = copilot_json.get("monthly") if isinstance(copilot_json.get("monthly"), dict) else {}
    monthly_remaining = monthly.get("remaining")
    if monthly_remaining is None:
        monthly_text = "unavailable"
    else:
        monthly_text = common.fmt_pct(monthly_remaining) + "%"
        common.log_usage_sample("copilot", "monthly", monthly_remaining)
    remaining_time = common.estimate_remaining_time_from_log("copilot", "monthly", monthly_remaining) if cfg.show_remaining_time else ""
    print_value_row(cfg, "Copilot", "monthly", monthly_text, remaining_time, reset_text, to_reset, source)
    if cfg.show_copilot_credits:
        ai = copilot_json.get("ai_credits") if isinstance(copilot_json.get("ai_credits"), dict) else {}
        ai_text = common.fmt_pct(ai.get("used")) if ai.get("used") is not None else "unknown"
        print_value_row(cfg, "Copilot", "ai-credits", ai_text, rem_time, "-", "-", source)


def render_once(cfg: Config) -> None:
    codex = common.read_codex()
    claude = common.read_claude()
    copilot = common.read_copilot()
    if cfg.json_output:
        obj = {
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "codex": common.json_for_provider(codex, "codex"),
            "claude": common.json_for_provider(claude, "claude"),
            "copilot": common.json_for_copilot(copilot, cfg.show_copilot_credits),
        }
        print(json.dumps(obj, separators=(",", ":")))
        return
    if not cfg.no_header:
        if cfg.show_remaining_time:
            if cfg.show_source:
                print(cell(TOOL_COL_WIDTH, "Tool", True) + cell(12, "Window", True) + cell(11, "Remaining", True) + cell(14, "Remaining Time", True) + cell(16, "Resets", True) + cell(12, "Time to Reset", True) + "Source")
                print(rule(TOOL_COL_WIDTH, True) + rule(12, True) + rule(11, True) + rule(14, True) + rule(16, True) + rule(12, True) + ("-" * TABLE_GAP_WIDTH))
            else:
                print(cell(TOOL_COL_WIDTH, "Tool", True) + cell(12, "Window", True) + cell(11, "Remaining", True) + cell(14, "Remaining Time", True) + cell(16, "Resets", True) + cell(12, "Time to Reset"))
                print(rule(TOOL_COL_WIDTH, True) + rule(12, True) + rule(11, True) + rule(14, True) + rule(16, True) + rule(12))
        else:
            if cfg.show_source:
                print(cell(TOOL_COL_WIDTH, "Tool", True) + cell(12, "Window", True) + cell(11, "Remaining", True) + cell(16, "Resets", True) + "Source")
                print(rule(TOOL_COL_WIDTH, True) + rule(12, True) + rule(11, True) + rule(16, True) + ("-" * TABLE_GAP_WIDTH))
            else:
                print(cell(TOOL_COL_WIDTH, "Tool", True) + cell(12, "Window", True) + cell(11, "Remaining", True) + cell(16, "Resets"))
                print(rule(TOOL_COL_WIDTH, True) + rule(12, True) + rule(11, True) + rule(16))
    print_codex_rows(cfg, codex)
    if claude:
        source = claude.get("source", "")
        log_and_print_row(cfg, "Claude", "5h", (claude.get("five_hour") or {}).get("used"), (claude.get("five_hour") or {}).get("resets_at"), source)
        log_and_print_row(cfg, "Claude", "weekly", (claude.get("week") or {}).get("used"), (claude.get("week") or {}).get("resets_at"), source)
    else:
        print_unavailable_rows(cfg, "Claude")
    print_copilot_rows(cfg, copilot)


def statusline_mode() -> None:
    text = sys.stdin.read()
    obj = common.read_json_text(text)
    if isinstance(obj, dict) and (obj.get("rate_limits") is not None or obj.get("rateLimits") is not None):
        cache = common.usage_cache_dir() / "claude-status.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    five = None
    week = None
    if isinstance(obj, dict):
        five = common.get_path(obj, (("rate_limits", "five_hour", "used_percentage"), ("rateLimits", "fiveHour", "usedPercent")))
        week = common.get_path(obj, (("rate_limits", "seven_day", "used_percentage"), ("rateLimits", "sevenDay", "usedPercent")))
    out = "Claude"
    five_rem = common.remaining_from_used(five)
    week_rem = common.remaining_from_used(week)
    if five_rem is not None:
        out += f" 5h {common.fmt_pct(five_rem)}% left"
    if week_rem is not None:
        out += f" weekly {common.fmt_pct(week_rem)}% left"
    print(out)


def log_once(cfg: Config) -> None:
    from io import StringIO
    import contextlib

    with contextlib.redirect_stdout(StringIO()):
        render_once(cfg)
    common.prune_usage_log()


def main(argv: list[str] | None = None) -> int:
    common.migrate_legacy_cache_dirs()
    cfg = parse_args(list(sys.argv[1:] if argv is None else argv))
    common.usage_cache_dir().mkdir(parents=True, exist_ok=True)
    if cfg.statusline_mode:
        statusline_mode()
        return 0
    if cfg.log_only:
        cfg.json_output = False
        cfg.show_remaining_time = False
        if cfg.watch_interval != "0":
            while True:
                log_once(cfg)
                time.sleep(float(cfg.watch_interval))
        log_once(cfg)
        return 0
    if cfg.watch_interval != "0":
        while True:
            frame_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            from io import StringIO
            import contextlib

            buf = StringIO()
            with contextlib.redirect_stdout(buf):
                print(f"Last refreshed: {frame_time}")
                render_once(cfg)
            if sys.stdout.isatty():
                print("\033[2J\033[H", end="")
            print(buf.getvalue(), end="")
            time.sleep(float(cfg.watch_interval))
    else:
        render_once(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
