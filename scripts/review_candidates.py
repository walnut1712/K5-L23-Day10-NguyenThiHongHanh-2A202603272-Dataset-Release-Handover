#!/usr/bin/env python3
"""Interactively review cross-check candidates and update review_log.csv."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Review candidates one at a time")
    parser.add_argument("run", type=Path)
    parser.add_argument("--reviewer", required=True, help="reviewer name or team member")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, help="number of candidates to review")
    parser.add_argument("--zoom", type=int, default=3)
    args = parser.parse_args()
    run = args.run
    delivery = run / "delivery"
    candidates_path = run / "candidates.json"
    review_path = run / "review_log.csv"
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"]
    stop = len(candidates) if args.count is None else min(len(candidates), args.start + args.count)
    if args.start < 0 or args.start >= len(candidates):
        parser.error(f"--start must be between 0 and {len(candidates) - 1}")

    rows = {}
    if review_path.is_file() and review_path.stat().st_size > 0:
        with open(review_path, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows[(row["image"], row["type"])] = row

    overlay_dir = run / "review_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    for index in range(args.start, stop):
        candidate = candidates[index]
        image_id = candidate["image"]
        candidate_type = candidate["type"]
        key = (image_id, candidate_type)
        print(f"\n[{index - args.start + 1}/{stop - args.start}] {image_id} {candidate_type}")
        print(candidate["reason"])
        if key in rows:
            print("Already reviewed:", rows[key]["verdict"], "-", rows[key]["note"])

        overlay = overlay_dir / f"{index:03d}_{image_id}_{candidate_type}.png"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "view_candidate.py"),
                str(delivery),
                str(candidates_path),
                "--index",
                str(index),
                "--zoom",
                str(args.zoom),
                "--save",
                str(overlay),
            ],
            check=True,
        )
        if hasattr(os, "startfile"):
            os.startfile(str(overlay))
        else:
            print("Open overlay:", overlay)

        while True:
            verdict = input("Verdict (confirmed/rejected): ").strip().lower()
            if verdict in {"confirmed", "rejected"}:
                break
            print("Enter exactly confirmed or rejected.")

        while True:
            observation = input("What did you see (include at least 20 characters): ").strip()
            note = f"Reviewer {args.reviewer}: {observation}"
            if len(observation) >= 20:
                break
            print("Observation is too short.")

        rows[key] = {
            "image": image_id,
            "type": candidate_type,
            "verdict": verdict,
            "note": note,
        }
        with open(review_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["image", "type", "verdict", "note"])
            writer.writeheader()
            writer.writerows(rows.values())
        print("Saved.")

    print(f"\nReview complete through candidate index {stop - 1}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
