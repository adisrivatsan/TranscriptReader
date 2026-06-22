import argparse
import sys
from pathlib import Path


def cmd_init(args) -> None:
    from treader.vault import init_vault
    vault = Path(args.vault)
    project_name = input("Project name: ").strip() or "My Project"
    print("\nAdd stakeholders (leave name blank to finish).\n")
    people = []
    while True:
        name = input(f"Stakeholder {len(people) + 1} name: ").strip()
        if not name:
            break
        role = input("  Role: ").strip()
        domains_raw = input("  Domains they own (comma-sep): ").strip()
        domains = [d.strip() for d in domains_raw.split(",") if d.strip()]
        aliases_raw = input("  Aliases (comma-sep, or blank): ").strip()
        aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]
        people.append({"name": name, "role": role, "domains": domains, "aliases": aliases})
        again = input("Add another stakeholder? [y/N]: ").strip().lower()
        if again != "y":
            break

    init_vault(vault, project_name=project_name)

    if people:
        import yaml
        (vault / "roster.yaml").write_text(
            yaml.dump({"people": people}, default_flow_style=False, allow_unicode=True)
        )

    print(f"\nVault created: {vault.resolve()}")
    print(f"  config.yaml     — project settings")
    print(f"  roster.yaml     — {len(people)} stakeholder(s) (edit to add more)")
    print(f"  facts.json      — empty")
    print(f"  hypotheses.json — empty")
    print(f"  meetings.json   — empty")


def cmd_scan(args) -> None:
    from treader.scan import run_scan
    run_scan(
        vault_path=Path(args.vault),
        source_path=Path(args.source),
        yes=args.yes,
        config_override=args.backend,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="treader",
        description="Transcript Reader — lightweight meeting extractor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize a vault")
    p_init.add_argument("vault", help="Path to vault directory")
    p_init.set_defaults(func=cmd_init)

    p_scan = sub.add_parser("scan", help="Extract facts, hypotheses, and meetings from a transcript")
    p_scan.add_argument("vault", help="Path to vault directory")
    p_scan.add_argument("--source", required=True, metavar="FILE", help=".vtt or .txt transcript file")
    p_scan.add_argument("--yes", action="store_true", help="Skip Q&A; send non-auto-confirmed items to review file")
    p_scan.add_argument("--backend", choices=["claude", "codex"], default=None)
    p_scan.set_defaults(func=cmd_scan)

    args = parser.parse_args()
    try:
        args.func(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
