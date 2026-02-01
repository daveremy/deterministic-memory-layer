"""
Demo validation script - runs demo and validates DML state after each prompt.

Usage:
    uv run python -m dml.demo.validator --script product_launch
    uv run python -m dml.demo.validator --script product_launch --dry-run  # Just show expectations
"""

import argparse
import json
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

from dml.demo.tui import load_demo_prompts


def get_db_state(db_path: str) -> dict:
    """Query current DML database state."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM events ORDER BY global_seq")
    events = cur.fetchall()

    # Parse events into facts, constraints, decisions
    facts = {}
    constraints = []
    decisions = []

    for row in events:
        seq, _turn_id, _ts, etype, payload, _caused_by, _corr_id = row
        data = json.loads(payload)

        if etype == "FactAdded":
            facts[data["key"]] = {
                "value": data["value"],
                "confidence": data.get("confidence", 1.0),
                "seq": seq,
            }
        elif etype == "ConstraintAdded":
            constraints.append({
                "text": data["text"],
                "priority": data.get("priority", "required"),
                "seq": seq,
            })
        elif etype == "DecisionMade":
            decisions.append({
                "text": data["text"],
                "status": data.get("status", "committed"),
                "seq": seq,
            })

    conn.close()
    return {
        "facts": facts,
        "constraints": constraints,
        "decisions": decisions,
        "event_count": len(events),
    }


def check_expectations(state: dict, expects: dict) -> list[str]:
    """Check if state matches expectations. Returns list of failures."""
    failures = []

    # Check expected facts (partial key matching)
    for key, expected in expects.get("facts", {}).items():
        # Find any fact key that contains the expected key (case-insensitive)
        matching_keys = [k for k in state["facts"] if key.lower() in k.lower()]
        if not matching_keys:
            failures.append(f"Missing fact containing '{key}'")
        elif expected is not None:
            # Check if any matching fact has the expected value
            found_value = False
            for mk in matching_keys:
                actual = state["facts"][mk]["value"]
                if expected.lower() in actual.lower() or actual.lower() in expected.lower():
                    found_value = True
                    break
            if not found_value:
                actuals = [state["facts"][mk]["value"] for mk in matching_keys]
                failures.append(f"Fact '{key}' (matched {matching_keys}): expected '{expected}', got {actuals}")

    # Check expected constraints (substring match)
    for expected_text in expects.get("constraints", []):
        found = any(expected_text.lower() in c["text"].lower() for c in state["constraints"])
        if not found:
            failures.append(f"Missing constraint containing: '{expected_text}'")

    # Check expected decisions (substring match)
    for expected_text in expects.get("decisions", []):
        found = any(expected_text.lower() in d["text"].lower() for d in state["decisions"])
        if not found:
            failures.append(f"Missing decision containing: '{expected_text}'")

    return failures


def run_prompt(prompt: str, demo_dir: Path, continue_session: bool = False) -> str:
    """Run a single prompt through Claude and return response."""
    # Normalize whitespace (prompts from YAML may have internal newlines)
    clean_prompt = " ".join(prompt.split())
    cmd = [
        "claude", "-p", f"/dml {clean_prompt}",
        "--dangerously-skip-permissions",
    ]
    if continue_session:
        cmd.append("-c")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=demo_dir,
        timeout=180,  # 3 minutes per prompt
    )

    # Check for errors
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error (exit {result.returncode}): {result.stderr}")

    # Combine stdout and stderr (Claude sometimes outputs to stderr)
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    return output


def validate_demo(script_name: str, dry_run: bool = False, verbose: bool = False):
    """Run demo and validate each step."""
    script = load_demo_prompts(script_name)
    prompts = script.get("prompts", [])

    print(f"=== Validating: {script.get('name', script_name)} ===")
    print(f"Prompts: {len(prompts)}")
    print()

    if dry_run:
        print("DRY RUN - showing expectations only")
        print()
        for i, p in enumerate(prompts, 1):
            print(f"[{i}] {p['prompt'][:60].strip()}...")
            if "validate" in p:
                print(f"    Expects: {p['validate']}")
            elif "expects" in p:
                print(f"    Expects type: {p['expects']}")
            print()
        return True

    # Create temp directory for demo session
    demo_dir = Path(tempfile.mkdtemp(prefix="dml-validate-"))
    db_path = Path.home() / ".dml" / "memory.db"
    backup_path = db_path.with_suffix(".db.bak")

    # Backup existing database
    had_backup = False
    if db_path.exists():
        shutil.copy(db_path, backup_path)
        had_backup = True

    print(f"Demo dir: {demo_dir}")
    print(f"Database: {db_path}")
    print()

    all_passed = True

    try:
        # Reset database for fresh start
        subprocess.run(["uv", "run", "dml", "reset", "-y"], capture_output=True)

        for i, p in enumerate(prompts, 1):
            prompt_text = p["prompt"].strip()
            expects_type = p.get("expects", "")
            validate = p.get("validate", {})

            print(f"[{i}/{len(prompts)}] Running prompt...")
            if verbose:
                print(f"    {prompt_text[:80]}...")

            # Run prompt
            try:
                response = run_prompt(prompt_text, demo_dir, continue_session=(i > 1))
            except subprocess.TimeoutExpired:
                print("    ❌ TIMEOUT")
                all_passed = False
                continue
            except Exception as e:
                print(f"    ❌ ERROR: {e}")
                all_passed = False
                continue

            # Check state
            state = get_db_state(str(db_path))

            if verbose:
                print(f"    Facts: {len(state['facts'])}, Constraints: {len(state['constraints'])}, Decisions: {len(state['decisions'])}")

            # Validate if expectations defined
            if validate:
                failures = check_expectations(state, validate)
                if failures:
                    print("    ❌ FAILED:")
                    for f in failures:
                        print(f"       - {f}")
                    all_passed = False
                else:
                    print("    ✓ Passed")
            elif expects_type:
                # Basic type check
                if expects_type == "facts" and state["facts"]:
                    print(f"    ✓ Facts recorded ({len(state['facts'])} total)")
                elif expects_type == "constraint" and state["constraints"]:
                    print(f"    ✓ Constraints recorded ({len(state['constraints'])} total)")
                elif expects_type == "decision" and state["decisions"]:
                    print(f"    ✓ Decisions recorded ({len(state['decisions'])} total)")
                elif expects_type == "blocked":
                    # Check if response indicates blocking
                    block_indicators = ["conflict", "violate", "can't", "cannot", "wait", "hold on",
                                       "before we", "need to", "legal", "review", "constraint", "blocked"]
                    found = [ind for ind in block_indicators if ind in response.lower()]
                    if found:
                        print(f"    ✓ Appears blocked (found: {', '.join(found[:3])})")
                    else:
                        print("    ⚠ Expected blocked, unclear if it was")
                else:
                    print(f"    ? No validation for expects={expects_type}")
            else:
                print("    - No expectations defined")

            # Small delay between prompts
            time.sleep(0.5)

        print()
        if all_passed:
            print("✓ All validations passed!")
        else:
            print("❌ Some validations failed")

    finally:
        # Cleanup temp directory
        shutil.rmtree(demo_dir, ignore_errors=True)

        # Restore original database if we had one
        if had_backup and backup_path.exists():
            shutil.move(backup_path, db_path)
            print("(Restored original database)")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Validate DML demo scripts")
    parser.add_argument("--script", required=True, help="Demo script name")
    parser.add_argument("--dry-run", action="store_true", help="Just show expectations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    success = validate_demo(args.script, dry_run=args.dry_run, verbose=args.verbose)
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
