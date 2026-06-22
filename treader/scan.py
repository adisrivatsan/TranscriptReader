import json
import sys
from datetime import date
from importlib import resources
from pathlib import Path

from treader.llm import call_structured
from treader.transcript import preprocess_transcript
from treader.vault import append_item, load_roster, write_review


def _load_skill() -> str:
    return (resources.files("treader") / "skills" / "scan.md").read_text()


def _build_prompt(skill: str, roster: list, transcript_text: str) -> str:
    roster_block = json.dumps(roster, indent=2) if roster else "(empty — no stakeholders configured)"
    return skill.replace("{roster}", roster_block).replace("{transcript}", transcript_text)


def _is_auto_route(item: dict) -> bool:
    return item.get("confidence") == "high" and item.get("authority") == "owner"


def _qa_fact(item: dict) -> str:
    return (
        f'\n[FACT?] "{item.get("claim", "")}"'
        f' ({item.get("stated_by", "")} — {item.get("authority", "")}, confidence: {item.get("confidence", "")})\n'
        f'  Source: "{item.get("source_span", "")}"\n'
        f"  → [f]act  [h]yp  [s]kip to review: "
    )


def _qa_hyp(item: dict) -> str:
    return (
        f'\n[HYP?] "{item.get("theory", "")}"'
        f' ({item.get("held_by", "")} — confidence: {item.get("confidence", "")})\n'
        f'  Source: "{item.get("source_span", "")}"\n'
        f"  → [f]act  [h]yp  [s]kip to review: "
    )


def _qa_meeting(item: dict) -> str:
    return (
        f'\n[MEETING?] "{item.get("purpose", "")}"'
        f' (convener: {item.get("convener", "unknown")}, attendees: {item.get("attendees", [])})\n'
        f'  Source: "{item.get("source_span", "")}"\n'
        f"  → [m]eeting  [s]kip to review: "
    )


def run_scan(
    vault_path: Path,
    source_path: Path,
    yes: bool = False,
    config_override: str = None,
) -> None:
    today = date.today().isoformat()
    source_name = source_path.name

    transcript_text = preprocess_transcript(source_path)
    roster = load_roster(vault_path)
    skill = _load_skill()
    prompt = _build_prompt(skill, roster, transcript_text)

    print("Scanning transcript... ", end="", flush=True)
    extracted = call_structured(prompt, config_override=config_override, vault_path=vault_path)
    print("done.")

    facts_confirmed = hyps_confirmed = mtgs_confirmed = 0
    skipped_facts, skipped_hyps, skipped_mtgs = [], [], []

    for item in extracted.get("facts", []):
        item["source"] = source_name
        if _is_auto_route(item):
            append_item(vault_path, "facts.json", item, today)
            facts_confirmed += 1
        elif yes:
            skipped_facts.append(item)
        else:
            answer = input(_qa_fact(item)).strip().lower()
            if answer == "f":
                append_item(vault_path, "facts.json", item, today)
                facts_confirmed += 1
            elif answer == "h":
                hyp = {
                    "theory": item.get("claim", ""),
                    "held_by": item.get("stated_by", ""),
                    "confidence": item.get("confidence", "low"),
                    "would_confirm": "",
                    "source": source_name,
                    "source_span": item.get("source_span", ""),
                }
                append_item(vault_path, "hypotheses.json", hyp, today)
                hyps_confirmed += 1
            else:
                skipped_facts.append(item)

    for item in extracted.get("hypotheses", []):
        item["source"] = source_name
        if yes:
            skipped_hyps.append(item)
        else:
            answer = input(_qa_hyp(item)).strip().lower()
            if answer == "f":
                fact = {
                    "claim": item.get("theory", ""),
                    "stated_by": item.get("held_by", ""),
                    "authority": "unknown",
                    "confidence": item.get("confidence", "low"),
                    "source": source_name,
                    "source_span": item.get("source_span", ""),
                }
                append_item(vault_path, "facts.json", fact, today)
                facts_confirmed += 1
            elif answer == "h":
                append_item(vault_path, "hypotheses.json", item, today)
                hyps_confirmed += 1
            else:
                skipped_hyps.append(item)

    for item in extracted.get("meetings", []):
        item["source"] = source_name
        item.setdefault("status", "open")
        if yes:
            skipped_mtgs.append(item)
        else:
            answer = input(_qa_meeting(item)).strip().lower()
            if answer == "m":
                append_item(vault_path, "meetings.json", item, today)
                mtgs_confirmed += 1
            else:
                skipped_mtgs.append(item)

    review_flags = extracted.get("review_flags", [])
    alias_flags = extracted.get("alias_flags", [])

    if skipped_facts or skipped_hyps or skipped_mtgs or review_flags:
        out_path = write_review(
            vault_path, today, source_name,
            skipped_facts, skipped_hyps, skipped_mtgs, review_flags,
        )
        review_note = str(out_path.relative_to(vault_path))
    else:
        review_note = None

    for af in alias_flags:
        if af.get("needs_review"):
            variants = ", ".join(af.get("variants", []))
            resolved = af.get("resolved_to", "?")
            print(f"WARNING: resolved '{variants}' → '{resolved}' — verify in roster.yaml", file=sys.stderr)

    total_skipped = len(skipped_facts) + len(skipped_hyps) + len(skipped_mtgs)
    print(
        f"\n{facts_confirmed} facts confirmed, "
        f"{hyps_confirmed} hypotheses confirmed, "
        f"{mtgs_confirmed} meetings confirmed, "
        f"{total_skipped} items → review"
    )
    if review_note:
        print(f"  Review file: {review_note}")
