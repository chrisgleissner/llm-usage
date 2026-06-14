"""Tests for the provider adapter module structure."""

from __future__ import annotations

import inspect

import pytest

from llm_tools import common
from llm_tools.capacity import (
    CapacityKind,
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    PROVIDER_COPILOT,
    PROVIDER_KILO,
    PROVIDER_MINIMAX,
)
from llm_tools.providers import claude, codex, copilot, kilo, minimax


def test_providers_module_exports_all_providers() -> None:
    """Every supported provider has a dedicated module under providers/."""
    for module, name in (
        (codex, "codex"),
        (claude, "claude"),
        (copilot, "copilot"),
        (kilo, "kilo"),
        (minimax, "minimax"),
    ):
        assert inspect.ismodule(module), f"providers.{name} is not a module"
        # Each adapter exposes a read(env) that returns a ProviderSnapshot.
        assert callable(getattr(module, "read", None)), f"providers.{name} missing read()"


def test_codex_snapshot_normalises_legacy_shape(env: dict[str, str], tmp_path) -> None:
    from pathlib import Path

    (Path(env["HOME"]) / ".codex" / "sessions").mkdir(parents=True, exist_ok=True)
    (Path(env["HOME"]) / ".codex" / "sessions" / "s.jsonl").write_text(
        '{"rate_limits":{"primary":{"used_percent":10,"resets_at":"2030-01-01T00:00:00Z"},"secondary":{"used_percent":20,"resets_at":"2030-01-07T00:00:00Z"}}}\n',
        encoding="utf-8",
    )
    env["LLM_USAGE_NOW_EPOCH"] = "1000"
    snap = codex.read(env)
    assert snap.provider == PROVIDER_CODEX
    assert snap.available is True
    assert {s.name for s in snap.scopes} == {"5h", "weekly"}
    for scope in snap.scopes:
        assert scope.kind == CapacityKind.RESET_WINDOW
        assert scope.remaining_percent is not None


def test_codex_snapshot_unavailable_when_no_data(env: dict[str, str], monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(env["HOME"]))
    env["LLM_USAGE_NOW_EPOCH"] = "1000"
    snap = codex.read(env)
    assert snap.available is False
    assert snap.reason == "no-local-data"


def test_claude_snapshot_unavailable_when_no_data(env: dict[str, str], monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(env["HOME"]))
    env["LLM_USAGE_NOW_EPOCH"] = "1000"
    snap = claude.read(env)
    assert snap.available is False
    assert snap.reason == "no-local-data"


def test_copilot_snapshot_unavailable_when_no_data(env: dict[str, str]) -> None:
    env["LLM_USAGE_DISABLE_COPILOT"] = "1"
    env["LLM_USAGE_NOW_EPOCH"] = "1000"
    snap = copilot.read(env)
    # copilot CLI capture is disabled → unavailable.
    assert snap.available is False


def test_kilo_snapshot_uses_env(env: dict[str, str]) -> None:
    env["LLM_USAGE_KILO_BALANCE"] = "5"
    env["LLM_USAGE_KILO_CURRENCY"] = "USD"
    snap = kilo.read(env)
    assert snap.provider == PROVIDER_KILO
    balance = next(s for s in snap.scopes if s.kind == CapacityKind.BALANCE)
    assert balance.remaining_amount == 5.0
    assert balance.currency == "USD"


def test_minimax_snapshot_uses_env(env: dict[str, str]) -> None:
    env["PATH"] = "/var/empty"
    env["LLM_USAGE_MINIMAX_5H_PERCENT"] = "75"
    env["LLM_USAGE_MINIMAX_5H_RESET_EPOCH"] = "1700000000"
    env["LLM_USAGE_MINIMAX_WEEKLY_PERCENT"] = "97"
    env["LLM_USAGE_MINIMAX_WEEKLY_RESET_EPOCH"] = "1700003600"
    snap = minimax.read(env)
    assert snap.provider == PROVIDER_MINIMAX
    assert {s.name for s in snap.scopes} == {"5h", "weekly"}
    for scope in snap.scopes:
        assert scope.kind == CapacityKind.RESET_WINDOW
        assert scope.remaining_percent is not None
