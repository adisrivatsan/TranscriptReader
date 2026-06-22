import json
import pytest
import yaml
from pathlib import Path

from treader.vault import init_vault, load_roster, append_item, write_review


# ── init_vault ───────────────────────────────────────────────────────────────

def test_init_vault_creates_expected_files(tmp_path):
    init_vault(tmp_path)
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / "roster.yaml").exists()
    assert (tmp_path / "facts.json").exists()
    assert (tmp_path / "hypotheses.json").exists()
    assert (tmp_path / "meetings.json").exists()
    assert (tmp_path / "review").is_dir()


def test_init_vault_writes_config(tmp_path):
    init_vault(tmp_path, project_name="Q3 Strategy")
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert cfg["project_name"] == "Q3 Strategy"
    assert "llm_backend" in cfg
    assert "llm_timeout_seconds" in cfg


def test_init_vault_creates_empty_json_stores(tmp_path):
    init_vault(tmp_path)
    assert json.loads((tmp_path / "facts.json").read_text()) == []
    assert json.loads((tmp_path / "hypotheses.json").read_text()) == []
    assert json.loads((tmp_path / "meetings.json").read_text()) == []


def test_init_vault_refuses_existing_vault(tmp_path):
    init_vault(tmp_path)
    with pytest.raises(FileExistsError, match="already contains config.yaml"):
        init_vault(tmp_path)
    assert json.loads((tmp_path / "facts.json").read_text()) == []


# ── load_roster ──────────────────────────────────────────────────────────────

def test_load_roster_empty_vault(tmp_path):
    init_vault(tmp_path)
    assert load_roster(tmp_path) == []


def test_load_roster_reads_people(tmp_path):
    init_vault(tmp_path)
    roster_data = {"people": [
        {"name": "Sarah Klein", "role": "CFO", "domains": ["finance"], "aliases": ["Sarah"]}
    ]}
    (tmp_path / "roster.yaml").write_text(yaml.dump(roster_data))
    people = load_roster(tmp_path)
    assert len(people) == 1
    assert people[0]["name"] == "Sarah Klein"
    assert people[0]["domains"] == ["finance"]


def test_load_roster_missing_file_returns_empty(tmp_path):
    assert load_roster(tmp_path) == []


# ── append_item ──────────────────────────────────────────────────────────────

def test_append_item_mints_fact_id(tmp_path):
    init_vault(tmp_path)
    item = {
        "claim": "Q2 cost up 9%",
        "stated_by": "Sarah Klein",
        "authority": "owner",
        "confidence": "high",
        "source_span": "Sarah: Q2 cost up",
        "source": "meeting.txt",
    }
    result = append_item(tmp_path, "facts.json", item, today="2026-06-22")
    assert result["id"] == "fact-2026-06-22-0000"
    assert result["created"] == "2026-06-22"


def test_append_item_sequential_ids(tmp_path):
    init_vault(tmp_path)
    base = {"claim": "", "stated_by": "", "authority": "owner", "confidence": "high", "source_span": "", "source": "f.txt"}
    r1 = append_item(tmp_path, "facts.json", {**base, "claim": "First"}, today="2026-06-22")
    r2 = append_item(tmp_path, "facts.json", {**base, "claim": "Second"}, today="2026-06-22")
    assert r1["id"] == "fact-2026-06-22-0000"
    assert r2["id"] == "fact-2026-06-22-0001"


def test_append_item_hyp_prefix(tmp_path):
    init_vault(tmp_path)
    item = {"theory": "Unbundling boosts conversion", "held_by": "Dev", "confidence": "med", "would_confirm": "", "source_span": "", "source": "f.txt"}
    result = append_item(tmp_path, "hypotheses.json", item, today="2026-06-22")
    assert result["id"].startswith("hyp-2026-06-22-")


def test_append_item_mtg_prefix(tmp_path):
    init_vault(tmp_path)
    item = {"purpose": "Align on Q3 cost", "convener": "Sarah", "attendees": [], "target_timing": "", "source_span": "", "source": "f.txt", "status": "open"}
    result = append_item(tmp_path, "meetings.json", item, today="2026-06-22")
    assert result["id"].startswith("mtg-2026-06-22-")


def test_append_item_persists_to_store(tmp_path):
    init_vault(tmp_path)
    item = {"claim": "Revenue up", "stated_by": "Sarah", "authority": "owner", "confidence": "high", "source_span": "", "source": "f.txt"}
    append_item(tmp_path, "facts.json", item, today="2026-06-22")
    stored = json.loads((tmp_path / "facts.json").read_text())
    assert len(stored) == 1
    assert stored[0]["claim"] == "Revenue up"


# ── write_review ─────────────────────────────────────────────────────────────

def test_write_review_creates_file(tmp_path):
    init_vault(tmp_path)
    path = write_review(tmp_path, "2026-06-22", "meeting.txt", [], [], [], [])
    assert path.exists()
    assert path.name == "2026-06-22-review.md"


def test_write_review_skipped_facts_appear(tmp_path):
    init_vault(tmp_path)
    facts = [{"claim": "margins fine", "stated_by": "Dev", "authority": "non_owner", "confidence": "low", "source_span": "Dev: margins fine"}]
    path = write_review(tmp_path, "2026-06-22", "meeting.txt", facts, [], [], [])
    content = path.read_text()
    assert "margins fine" in content
    assert "## Skipped hypotheses" in content
    assert "(none)" in content


def test_write_review_flags_appear(tmp_path):
    init_vault(tmp_path)
    flags = ["near-discard: vague aside about SLA — dropped because no owner"]
    path = write_review(tmp_path, "2026-06-22", "meeting.txt", [], [], [], flags)
    assert "near-discard" in path.read_text()
