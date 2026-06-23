# Transcript Reader

Lightweight meeting transcript extractor. Give it a `.vtt` or `.txt` transcript, and it extracts three things:

- **Facts** — definitive claims stated as true, attributed to their speaker
- **Hypotheses** — working theories, hunches, and speculation
- **Meetings to schedule** — explicit or implicit commitments to reconvene

High-confidence facts from domain owners are auto-confirmed to the vault. Everything else goes through a short interactive Q&A, or straight to a review file with `--yes`.

## Install

Requires Python 3.10+ and either the [Claude Code CLI](https://claude.ai/code) (`claude`) or OpenAI Codex CLI (`codex`) installed and authenticated.

```bash
git clone https://github.com/adisrivatsan/TranscriptReader.git
cd TranscriptReader
pip install -e .
```

## Quick Start

```bash
# Create a vault (interactive wizard — sets project name and stakeholder roster)
treader init my-vault/

# Scan a transcript
treader scan my-vault/ --source meeting.vtt

# Skip Q&A — send all ambiguous items to a review file instead
treader scan my-vault/ --source meeting.txt --yes

# Force a specific LLM backend
treader scan my-vault/ --source meeting.vtt --backend claude
```

## How It Works

```
transcript (.vtt or .txt)
        │
        ▼
  preprocess        Strip VTT timestamps, merge speaker lines into "Name: text" format
        │
        ▼
  LLM extract       Send roster + transcript to scan-v1.0 prompt; get back JSON
        │
        ▼
  route items
   ├─ confidence=high + authority=owner  →  auto-confirm to vault
   ├─ everything else (--yes mode)       →  review file
   └─ everything else (interactive)      →  Q&A: [f]act / [h]yp / [s]kip
        │
        ▼
   vault stores      facts.json  hypotheses.json  meetings.json  review/
```

### Authority and Confidence

Each extracted item is tagged with how reliable it is:

| authority | meaning |
|-----------|---------|
| `owner` | speaker is in the roster and owns the claim's domain |
| `non_owner` | speaker is in the roster but outside their domain |
| `unknown` | speaker not in the roster |

Only `confidence=high` + `authority=owner` items auto-route. Everything else requires a human decision.

## Vault Structure

A vault is a plain directory with no database — just files you can read, edit, or version-control.

```
my-vault/
├── config.yaml          # project name, llm_backend, llm_timeout_seconds
├── roster.yaml          # stakeholders: names, roles, domains, aliases
├── facts.json           # confirmed facts
├── hypotheses.json      # confirmed hypotheses
├── meetings.json        # confirmed meetings to schedule
└── review/
    └── YYYY-MM-DD-review.md   # skipped items + LLM review flags
```

### config.yaml

```yaml
project_name: Q3 Strategy
llm_backend: claude        # or codex (auto-detected if null)
llm_timeout_seconds: 120
```

### roster.yaml

The roster is how `treader` assigns authority. A claim made by someone in the roster about a domain they own gets `confidence: high, authority: owner` — and auto-routes.

```yaml
people:
  - name: Sarah Klein
    role: CFO
    domains: [finance, cost, budget]
    aliases: [Sarah, SK]
  - name: Dev Patel
    role: Product Manager
    domains: [product, roadmap]
    aliases: [Dev]
```

Edit it by hand between meetings to keep it current. Aliases let the LLM resolve informal names ("Sarah", "SK") back to the canonical person.

### facts.json

```json
[
  {
    "id": "fact-2026-06-22-0000",
    "claim": "Q2 cost-to-serve is up 9%",
    "stated_by": "Sarah Klein",
    "authority": "owner",
    "confidence": "high",
    "source_span": "Sarah: Q2 cost-to-serve is up 9 percent",
    "source": "q2-review.vtt",
    "created": "2026-06-22"
  }
]
```

IDs are `fact-YYYY-MM-DD-NNNN` (zero-padded, per-day sequence). Same format for `hyp-` and `mtg-`.

### review/YYYY-MM-DD-review.md

Items you skipped during Q&A, plus anything the LLM flagged as uncertain, land here. Plain markdown — open it, decide what to do, then manually add anything worth keeping to the JSON stores.

## Interactive Q&A

When a fact or hypothesis doesn't auto-route, `treader` prompts you:

```
[FACT?] "margins are fine" (Dev Patel — non_owner, confidence: low)
  Source: "Dev: I think margins are fine"
  → [f]act  [h]yp  [s]kip to review:
```

- `f` — confirm as a fact, written to `facts.json`
- `h` — demote to hypothesis, written to `hypotheses.json`
- `s` (or anything else) — skip to review file

For meetings:

```
[MEETING?] "Align Finance and CS on Q3 cost model" (convener: Sarah Klein)
  → [m]eeting  [s]kip to review:
```

## Supported Transcript Formats

| Format | Handling |
|--------|---------|
| `.vtt` (WebVTT) | Timestamps stripped, speaker tags resolved, continuation lines merged |
| `.txt` | Passed through as-is |

For `.txt`, a simple `Name: text` format per line works well with the extraction prompt.

## LLM Backends

`treader` calls the LLM via subprocess — no SDK dependency.

| Backend | Command used |
|---------|-------------|
| `claude` | `claude -p <prompt>` |
| `codex` | `codex -q <prompt>` |

Backend is auto-detected (checks `$PATH`). Override per-vault in `config.yaml` or per-run with `--backend`.

## Development

```bash
pip install -e .
pytest
```

Tests use mocked LLM calls — no live API needed to run the suite.
