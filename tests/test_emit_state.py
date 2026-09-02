"""Tests for scripts/emit_state.py — the STATE_CONTRACT emission.

Most of the emission is a copy, and the tests for a copy are about the two ways
a copy goes wrong: it emits a guess when a key is renamed or null, or it emits a
stale file after a failed run.

The exception is `regime_risk_reduction`, which applies this repo's combined
rule rather than copying a field:

    (Lens 1 elevated OR Lens 2 armed) AND Lens 3 confirming

That rule is currently implemented in TWO places — here, and independently in
the private consumer that reads this. Duplicated logic drifts, so the truth
table below is enumerated in full rather than spot-checked: all 3 x 2 x 3
combinations of the three lens states, with the expected combined value written
out. If someone changes the firing rule in one place, one of these fails.

NOTE: since 2026-09-02 the refresh and digest workflows run the suite under
pytest, so these gate them. Before that they were a local guard only: unittest
discovery imported this module but collected none of its tests.

Synthetic payloads stand in for the on-disk JSON, so the tests do not move with
the market. Python datetime months are 1-indexed (January = 1).
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import emit_state  # noqa: E402

REQUIRED = {"as_of", "state", "value", "zone", "role", "horizon",
            "evidence_grade", "licence", "action_hint", "source_file"}
OPTIONAL = {"computed_at", "cadence"}
SIGNALS = {"regime_lens1", "regime_lens2", "regime_lens3", "regime_risk_reduction"}


def _lens1(status="watch", extra=None):
    inds = [
        {"id": "curve", "status": status, "as_of": "2026-08-24"},
        {"id": "claims", "status": "benign", "as_of": "2026-08-23"},
        # A `context` row. Excluded from the worst-of by the documented rule —
        # if it ever counted, an `elevated` valuation would fire the lens.
        {"id": "valuation", "status": "context", "as_of": "2026-08-25"},
    ]
    if extra:
        inds.extend(extra)
    return {"indicators": inds, "updated_at": "2026-08-25T23:49:38Z"}


def _lens2(alarm_state="below"):
    return {
        "composite": {"share_pct": 37.5, "alarm_state": alarm_state,
                      "triggered_count": 3, "gauge_count": 8, "alarm_share_pct": 62.5},
        "indicators": [{"id": "a", "as_of": "2026-08-25"}, {"id": "b", "as_of": "2026-08-24"}],
        "updated_at": "2026-08-25T23:49:38Z",
    }


def _lens3(status="benign"):
    return {
        "indicators": [{"name": "50-day vs 150-day", "status": status,
                        "value": 7457.69, "as_of": "2026-08-24"}],
        "updated_at": "2026-08-25T23:49:38Z",
    }


@pytest.fixture
def files(monkeypatch):
    store = {"lens1.json": _lens1(), "lens2.json": _lens2(), "lens3.json": _lens3()}

    def fake_load(name):
        if name not in store:
            raise emit_state.EmitError(f"source file not found: {name}")
        return store[name]

    monkeypatch.setattr(emit_state, "load", fake_load)
    return store


# --- the combined rule, enumerated in full ----------------------------------

@pytest.mark.parametrize("l1,l2,l3", itertools.product(
    ["benign", "watch", "elevated"], ["below", "armed"],
    ["benign", "watch", "elevated"]))
def test_combined_rule_truth_table(monkeypatch, l1, l2, l3):
    """(L1 elevated OR L2 armed) AND L3 confirming, where confirming means the
    trend lens is at watch or elevated."""
    store = {"lens1.json": _lens1(l1), "lens2.json": _lens2(l2), "lens3.json": _lens3(l3)}
    monkeypatch.setattr(emit_state, "load", lambda n: store[n])

    expected = "ON" if ((l1 == "elevated" or l2 == "armed")
                        and l3 in ("watch", "elevated")) else "OFF"
    got = emit_state.build()["signals"]["regime_risk_reduction"]["state"]
    assert got == expected, f"L1 {l1}, L2 {l2}, L3 {l3}: expected {expected}, got {got}"


def test_lens1_at_watch_alone_does_not_arm_the_combined_read(monkeypatch):
    """The bar is `elevated`, not `watch`. Kept explicit because it is the
    single most tempting place to loosen the rule by accident."""
    store = {"lens1.json": _lens1("watch"), "lens2.json": _lens2("below"),
             "lens3.json": _lens3("elevated")}
    monkeypatch.setattr(emit_state, "load", lambda n: store[n])
    assert emit_state.build()["signals"]["regime_risk_reduction"]["state"] == "OFF"


def test_armed_without_confirmation_stays_off(monkeypatch):
    store = {"lens1.json": _lens1("elevated"), "lens2.json": _lens2("armed"),
             "lens3.json": _lens3("benign")}
    monkeypatch.setattr(emit_state, "load", lambda n: store[n])
    assert emit_state.build()["signals"]["regime_risk_reduction"]["state"] == "OFF"


# --- Lens 1's worst-of, and the context exclusion ---------------------------

def test_context_rows_are_excluded_from_the_worst_of(files):
    """The valuation row is `context` and sits at a LATER date than the scored
    rows, so a bug that included it would show up in both state and as_of."""
    s = emit_state.build()["signals"]["regime_lens1"]
    assert s["state"] == "watch"
    assert s["as_of"] == "2026-08-24"      # not the context row's 2026-08-25
    assert s["zone"] == "0 elevated / 1 watch of 2"


def test_worst_of_takes_the_most_severe_not_the_most_recent(files):
    files["lens1.json"] = _lens1("benign", extra=[
        {"id": "spreads", "status": "elevated", "as_of": "2026-08-20"}])
    s = emit_state.build()["signals"]["regime_lens1"]
    assert s["state"] == "elevated"
    assert s["zone"] == "1 elevated / 0 watch of 3"


def test_a_lens1_with_only_context_rows_is_refused(files):
    files["lens1.json"] = {"indicators": [{"id": "v", "status": "context",
                                           "as_of": "2026-08-25"}]}
    with pytest.raises(emit_state.EmitError, match="context"):
        emit_state.build()


# --- shape ------------------------------------------------------------------

def test_emits_exactly_the_four_regime_signals(files):
    assert set(emit_state.build()["signals"]) == SIGNALS


def test_every_block_carries_the_required_fields_and_nothing_unknown(files):
    for sid, block in emit_state.build()["signals"].items():
        assert REQUIRED <= set(block), f"{sid} missing {REQUIRED - set(block)}"
        assert set(block) <= REQUIRED | OPTIONAL, f"{sid} has {set(block) - REQUIRED - OPTIONAL}"


def test_no_score_or_weight_field_is_emitted(files):
    banned = {"score", "weight", "composite", "rank"}
    for block in emit_state.build()["signals"].values():
        assert not (banned & set(block))


def test_lens_values_are_copied_from_the_source_files(files):
    s = emit_state.build()["signals"]
    assert s["regime_lens2"]["value"] == 37.5
    assert s["regime_lens2"]["zone"] == "3 of 8 triggered"
    assert s["regime_lens2"]["as_of"] == "2026-08-25"   # freshest indicator
    assert s["regime_lens3"]["value"] == 7457.69
    assert s["regime_lens3"]["zone"] == "50-day vs 150-day"


def test_the_combined_read_carries_the_freshest_lens_date(files):
    s = emit_state.build()["signals"]
    assert s["regime_risk_reduction"]["as_of"] == max(
        s["regime_lens1"]["as_of"], s["regime_lens2"]["as_of"], s["regime_lens3"]["as_of"])


def test_action_hint_follows_the_state(files):
    s = emit_state.build()["signals"]
    assert s["regime_lens1"]["action_hint"] == "watch"     # watch
    assert s["regime_lens3"]["action_hint"] == "none"      # benign
    assert s["regime_risk_reduction"]["action_hint"] == "none"


# --- never emit a guess ------------------------------------------------------

def test_a_missing_lens2_composite_key_stops_the_emission(files):
    del files["lens2.json"]["composite"]["alarm_state"]
    with pytest.raises(emit_state.EmitError, match="alarm_state"):
        emit_state.build()


def test_an_alarm_state_outside_its_vocabulary_is_refused(files):
    files["lens2.json"]["composite"]["alarm_state"] = "maybe"
    with pytest.raises(emit_state.EmitError, match="maybe"):
        emit_state.build()


def test_a_lens3_status_outside_its_vocabulary_is_refused(files):
    files["lens3.json"]["indicators"][0]["status"] = "on-fire"
    with pytest.raises(emit_state.EmitError, match="on-fire"):
        emit_state.build()


def test_an_empty_lens3_indicator_list_is_refused(files):
    files["lens3.json"]["indicators"] = []
    with pytest.raises(emit_state.EmitError, match="out of range"):
        emit_state.build()


def test_indicators_without_as_of_dates_are_refused(files):
    files["lens2.json"]["indicators"] = [{"id": "a"}, {"id": "b"}]
    with pytest.raises(emit_state.EmitError, match="as_of"):
        emit_state.build()


def test_a_null_share_pct_is_refused_rather_than_emitted(files):
    files["lens2.json"]["composite"]["share_pct"] = None
    with pytest.raises(emit_state.EmitError, match="null"):
        emit_state.build()


# --- a failed run must not leave a half-written file -------------------------

def test_a_failed_run_writes_nothing_and_exits_non_zero(files, monkeypatch, tmp_path, capsys):
    out = tmp_path / "state.json"
    out.write_text('{"previous": "emission"}', encoding="utf-8")
    monkeypatch.setattr(emit_state, "OUT", out)
    files["lens3.json"]["indicators"][0]["status"] = "nonsense"

    assert emit_state.main([]) == 1
    assert json.loads(out.read_text(encoding="utf-8")) == {"previous": "emission"}
    assert "FAILED" in capsys.readouterr().err


def test_an_unchanged_state_is_not_rewritten(files, monkeypatch, tmp_path):
    out = tmp_path / "state.json"
    monkeypatch.setattr(emit_state, "OUT", out)
    assert emit_state.main([]) == 0
    first = out.read_text(encoding="utf-8")
    assert emit_state.main([]) == 0
    assert out.read_text(encoding="utf-8") == first, "unchanged state was rewritten"


def test_a_changed_state_IS_rewritten(files, monkeypatch, tmp_path):
    out = tmp_path / "state.json"
    monkeypatch.setattr(emit_state, "OUT", out)
    assert emit_state.main([]) == 0
    files["lens2.json"]["composite"]["alarm_state"] = "armed"
    assert emit_state.main([]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["signals"] \
        ["regime_lens2"]["state"] == "armed"


def test_check_mode_writes_nothing(files, monkeypatch, tmp_path):
    out = tmp_path / "state.json"
    monkeypatch.setattr(emit_state, "OUT", out)
    assert emit_state.main(["--check"]) == 0
    assert not out.exists()
