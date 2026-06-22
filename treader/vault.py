import json
import re
from datetime import date
from pathlib import Path

import yaml


def init_vault(vault_path: Path, project_name: str = "My Project") -> None:
    if (vault_path / "config.yaml").exists():
        raise FileExistsError(
            f"{vault_path} already contains config.yaml — refusing to overwrite "
            f"an existing vault. Delete the directory first to re-init."
        )
    vault_path.mkdir(parents=True, exist_ok=True)
    (vault_path / "review").mkdir(exist_ok=True)

    config = {
        "project_name": project_name,
        "llm_backend": None,
        "llm_timeout_seconds": 120,
    }
    (vault_path / "config.yaml").write_text(yaml.dump(config, default_flow_style=False))

    roster_template = """\
# roster.yaml — stakeholders in this project
# people:
#   - name: Sarah Klein
#     role: CFO
#     domains: [finance, cost, budget]
#     aliases: [Sarah, SK]

people: []
"""
    (vault_path / "roster.yaml").write_text(roster_template)

    for fname in ("facts.json", "hypotheses.json", "meetings.json"):
        (vault_path / fname).write_text("[]")


def load_roster(vault_path: Path) -> list:
    path = vault_path / "roster.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("people", [])


def _next_id(store: list, prefix: str, date_str: str) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}-{re.escape(date_str)}-(\d+)$")
    max_seq = -1
    for item in store:
        m = pattern.match(item.get("id", ""))
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{prefix}-{date_str}-{max_seq + 1:04d}"


_PREFIX_MAP = {
    "facts.json": "fact",
    "hypotheses.json": "hyp",
    "meetings.json": "mtg",
}


def append_item(vault_path: Path, store_name: str, item: dict, today: str = None) -> dict:
    prefix = _PREFIX_MAP[store_name]
    date_str = today or date.today().isoformat()
    path = vault_path / store_name
    store = json.loads(path.read_text())
    item = dict(item)
    item["id"] = _next_id(store, prefix, date_str)
    item["created"] = date_str
    store.append(item)
    path.write_text(json.dumps(store, indent=2))
    return item


def write_review(
    vault_path: Path,
    date_str: str,
    source: str,
    skipped_facts: list,
    skipped_hypotheses: list,
    skipped_meetings: list,
    review_flags: list,
) -> Path:
    lines = [f"# Review items — {date_str}", f"Source: {source}", ""]

    lines.append("## Skipped facts")
    if skipped_facts:
        for f in skipped_facts:
            lines.append(
                f'- "{f.get("claim", "")}"'
                f' ({f.get("stated_by", "")}, {f.get("authority", "")}, {f.get("confidence", "")})'
                f' — "{f.get("source_span", "")}"'
            )
    else:
        lines.append("(none)")

    lines += ["", "## Skipped hypotheses"]
    if skipped_hypotheses:
        for h in skipped_hypotheses:
            lines.append(
                f'- "{h.get("theory", "")}"'
                f' ({h.get("held_by", "")}, {h.get("confidence", "")})'
                f' — "{h.get("source_span", "")}"'
            )
    else:
        lines.append("(none)")

    lines += ["", "## Skipped meetings"]
    if skipped_meetings:
        for m in skipped_meetings:
            lines.append(
                f'- "{m.get("purpose", "")}"'
                f' (convener: {m.get("convener", "unknown")},'
                f' attendees: {m.get("attendees", [])})'
            )
    else:
        lines.append("(none)")

    lines += ["", "## Review flags from LLM"]
    if review_flags:
        for flag in review_flags:
            lines.append(f"- {flag}")
    else:
        lines.append("(none)")

    review_dir = vault_path / "review"
    review_dir.mkdir(exist_ok=True)
    out_path = review_dir / f"{date_str}-review.md"
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
