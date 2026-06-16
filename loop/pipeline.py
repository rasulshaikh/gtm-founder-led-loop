#!/usr/bin/env python3
"""
Full Pipeline Runner
Runs all 4 phases of the founder-led loop in sequence.

Usage:
    python loop/pipeline.py \
        --input raw_engagers.csv \
        --post-topic "Why most B2B teams hire SDRs before fixing the system" \
        --sender "Rasul" \
        --sender-title "GTM Engineer"
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


PHASES = [
    ("Phase 01: Signal Capture",    "loop/01_signal_capture.py"),
    ("Phase 02: Score and Route",   "loop/02_score_and_route.py"),
    ("Phase 03: Warm Outbound",     "loop/03_outbound.py"),
]


def run_phase(script: str, args_list: list[str], label: str) -> bool:
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"{'─'*60}")
    result = subprocess.run(
        [sys.executable, script] + args_list,
        capture_output=False,
        text=True,
    )
    if result.returncode != 0:
        print(f"\nPhase failed: {label}")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full founder-led loop pipeline")
    parser.add_argument("--input", required=True, help="Raw engager CSV (PhantomBuster or manual export)")
    parser.add_argument("--post-topic", default="GTM / outbound strategy",
                        help="What your post was about (adds context to outbound)")
    parser.add_argument("--sender", required=True)
    parser.add_argument("--sender-title", default="GTM Engineer")
    parser.add_argument("--sender-context", default=(
        "GTM Engineer who has built outbound systems generating $550K+ revenue and $3.5M+ pipeline. "
        "Specializes in signal-led outbound and AI-powered GTM infrastructure."
    ))
    parser.add_argument("--no-enrich", action="store_true", help="Skip Apollo enrichment in Phase 01")
    parser.add_argument("--dry-run", action="store_true", help="Skip Phase 03 AI generation (just score/route)")
    args = parser.parse_args()

    enriched = "enriched_engagers.csv"
    scored = "scored_engagers.csv"
    outbound = "outbound_sequences.csv"

    # Phase 01
    p01_args = ["--input", args.input, "--output", enriched, "--post-topic", args.post_topic]
    if args.no_enrich:
        p01_args.append("--no-enrich")
    if not run_phase("loop/01_signal_capture.py", p01_args, "Phase 01: Signal Capture"):
        sys.exit(1)

    # Phase 02
    if not run_phase("loop/02_score_and_route.py",
                     ["--input", enriched, "--output", scored],
                     "Phase 02: Score and Route"):
        sys.exit(1)

    # Phase 03 (optional)
    if not args.dry_run:
        if not run_phase("loop/03_outbound.py", [
            "--input", scored,
            "--output", outbound,
            "--sender", args.sender,
            "--sender-title", args.sender_title,
            "--sender-context", args.sender_context,
        ], "Phase 03: Warm Outbound"):
            sys.exit(1)
    else:
        print("\nDry-run: skipping Phase 03 outbound generation.")

    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Enriched:  {enriched}")
    print(f"  Scored:    {scored}")
    if not args.dry_run:
        print(f"  Outbound:  {outbound}")
    print()
    print("Next steps:")
    print("  1. Review outbound_sequences.csv")
    print("  2. Send Tier 1 emails manually (founder sends personally)")
    print("  3. Import Tier 2 emails into Smartlead/Instantly")
    print("  4. After conversations, run: python loop/04_content_miner.py --input call_notes.txt")
    print("  5. Publish the post ideas → restart the loop")


if __name__ == "__main__":
    main()
