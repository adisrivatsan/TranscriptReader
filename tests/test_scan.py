import json
import yaml
from pathlib import Path
from unittest.mock import patch

from treader.vault import init_vault


# ── shared fixtures ──────────────────────────────────────────────────────────

def _vault_with_roster(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    init_vault(vault)
    roster = {"people": [
        {"name": "Sarah Klein", "role": "CFO", "domains": ["finance", "cost"], "aliases": ["Sarah", "SK"]}
    ]}
    (vault / "roster.yaml").write_text(yaml.dump(roster))
    return vault


def _txt_source(tmp_path, content="Sarah: Q2 cost-to-serve is up 9 percent"):
    src = tmp_path / "meeting.txt"
    src.write_text(content)
    return src


_OWNER_FACT_EXTRACTION = {
    "meta": {"meeting_slug": "2026-06-22-test", "date": "2026-06-22",
             "source": "meeting.txt", "attendees": ["Sarah Klein"],
             "topic": "Test", "prompt_version": "scan-v1.0"},
    "facts": [{
        "claim": "Q2 cost-to-serve up 9%",
        "stated_by": "Sarah Klein",
        "authority": "owner",
        "confidence": "high",
        "source_span": "Sarah: Q2 cost-to-serve is up 9 percent",
    }],
    "hypotheses": [],
    "meetings": [],
    "alias_flags": [],
    "review_flags": [],
}

_NON_OWNER_FACT_EXTRACTION = {
    **_OWNER_FACT_EXTRACTION,
    "facts": [{
        "claim": "margins are fine",
        "stated_by": "Dev Patel",
        "authority": "non_owner",
        "confidence": "low",
        "source_span": "Dev: I think margins are fine",
    }],
}

_HYP_EXTRACTION = {
    **_OWNER_FACT_EXTRACTION,
    "facts": [],
    "hypotheses": [{
        "theory": "Unbundling boosts conversion by 15%",
        "held_by": "Dev Patel",
        "confidence": "med",
        "would_confirm": "Run A/B test",
        "source_span": "Dev: I think if we unbundle the fee...",
    }],
}

_MTG_EXTRACTION = {
    **_OWNER_FACT_EXTRACTION,
    "facts": [],
    "meetings": [{
        "purpose": "Align Finance and CS on Q3 cost model",
        "convener": "Sarah Klein",
        "attendees": ["Sarah Klein", "Dev Patel"],
        "target_timing": "before end of next week",
        "source_span": "Let's get Finance and CS together before Thursday",
    }],
}


# ── routing tests ────────────────────────────────────────────────────────────

def test_auto_route_high_confidence_owner_fact(tmp_path):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path)

    with patch("treader.scan.call_structured", return_value=_OWNER_FACT_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=False, config_override="claude")

    facts = json.loads((vault / "facts.json").read_text())
    assert len(facts) == 1
    assert facts[0]["claim"] == "Q2 cost-to-serve up 9%"
    assert facts[0]["id"].startswith("fact-")


def test_auto_route_does_not_trigger_qa(tmp_path):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path)

    with patch("treader.scan.call_structured", return_value=_OWNER_FACT_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"), \
         patch("builtins.input") as mock_input:
        from treader.scan import run_scan
        run_scan(vault, src, yes=False, config_override="claude")

    mock_input.assert_not_called()


def test_yes_non_owner_fact_goes_to_review(tmp_path):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path, "Dev: margins are fine")

    with patch("treader.scan.call_structured", return_value=_NON_OWNER_FACT_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=True, config_override="claude")

    facts = json.loads((vault / "facts.json").read_text())
    assert facts == []
    assert len(list((vault / "review").glob("*.md"))) == 1


def test_yes_hypothesis_goes_to_review(tmp_path):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path, "Dev: I think unbundling would boost conversion")

    with patch("treader.scan.call_structured", return_value=_HYP_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=True, config_override="claude")

    hyps = json.loads((vault / "hypotheses.json").read_text())
    assert hyps == []
    assert len(list((vault / "review").glob("*.md"))) == 1


def test_yes_meeting_goes_to_review(tmp_path):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path, "Let's loop in Finance and CS before Thursday")

    with patch("treader.scan.call_structured", return_value=_MTG_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=True, config_override="claude")

    meetings = json.loads((vault / "meetings.json").read_text())
    assert meetings == []
    assert len(list((vault / "review").glob("*.md"))) == 1


def test_no_review_file_when_nothing_skipped(tmp_path):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path)

    with patch("treader.scan.call_structured", return_value=_OWNER_FACT_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=True, config_override="claude")

    assert list((vault / "review").glob("*.md")) == []


def test_summary_printed(tmp_path, capsys):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path)

    with patch("treader.scan.call_structured", return_value=_OWNER_FACT_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=True, config_override="claude")

    out = capsys.readouterr().out
    assert "1 facts confirmed" in out
    assert "0 hypotheses confirmed" in out
    assert "0 meetings confirmed" in out


def test_qa_fact_confirm_as_fact(tmp_path, monkeypatch):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path, "Dev: margins are fine")
    monkeypatch.setattr("builtins.input", lambda _: "f")

    with patch("treader.scan.call_structured", return_value=_NON_OWNER_FACT_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=False, config_override="claude")

    facts = json.loads((vault / "facts.json").read_text())
    assert len(facts) == 1


def test_qa_fact_confirm_as_hyp(tmp_path, monkeypatch):
    vault = _vault_with_roster(tmp_path)
    src = _txt_source(tmp_path, "Dev: margins are fine")
    monkeypatch.setattr("builtins.input", lambda _: "h")

    with patch("treader.scan.call_structured", return_value=_NON_OWNER_FACT_EXTRACTION), \
         patch("treader.scan._load_skill", return_value="Roster: {roster}\nTranscript: {transcript}"):
        from treader.scan import run_scan
        run_scan(vault, src, yes=False, config_override="claude")

    hyps = json.loads((vault / "hypotheses.json").read_text())
    assert len(hyps) == 1
    assert hyps[0]["theory"] == "margins are fine"
