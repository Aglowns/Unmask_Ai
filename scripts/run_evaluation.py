#!/usr/bin/env python3
"""
Evaluation script for the detection pipeline.
Run from repo root. Optionally place labeled images in:
  evaluation_samples/real/*.jpg
  evaluation_samples/fake/*.jpg
Then: python scripts/run_evaluation.py [--samples-dir evaluation_samples] [--output results.json]
Logs signals and scores for each image so you can tune thresholds/weights.
"""

import argparse
import json
import sys
from pathlib import Path

# Run from repo root so services are importable
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.metadata_analyzer import analyze_metadata
from services.forensics_checker import run_forensics
from services.ai_classifier import classify_image
from services.scoring_engine import calculate_risk_score, calculate_layer_scores


def run_pipeline(image_bytes: bytes) -> dict:
    """Run full pipeline and return risk score, classification, signals, layer_scores."""
    metadata_signals = analyze_metadata(image_bytes)
    forensics_signals = run_forensics(image_bytes)
    ai_signals = classify_image(image_bytes)
    signals = metadata_signals + forensics_signals + ai_signals
    risk_score, classification = calculate_risk_score(signals)
    layer_scores = calculate_layer_scores(signals)
    return {
        "risk_score": risk_score,
        "classification": classification,
        "signals": signals,
        "layer_scores": layer_scores,
    }


def main():
    parser = argparse.ArgumentParser(description="Run detection pipeline on labeled samples.")
    parser.add_argument(
        "--samples-dir",
        type=Path,
        default=REPO_ROOT / "evaluation_samples",
        help="Directory containing 'real' and 'fake' subdirs with images",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write results JSON to this path (default: stdout only)",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list sample paths; do not run pipeline",
    )
    args = parser.parse_args()

    samples_dir = args.samples_dir.resolve()
    if not samples_dir.is_dir():
        print(f"Samples dir not found: {samples_dir}", file=sys.stderr)
        print("Create evaluation_samples/real/ and evaluation_samples/fake/ and add images.", file=sys.stderr)
        sys.exit(1)

    real_dir = samples_dir / "real"
    fake_dir = samples_dir / "fake"
    real_paths = list(real_dir.glob("*.*")) if real_dir.is_dir() else []
    fake_paths = list(fake_dir.glob("*.*")) if fake_dir.is_dir() else []
    # Common image extensions
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    real_paths = [p for p in real_paths if p.suffix.lower() in exts]
    fake_paths = [p for p in fake_paths if p.suffix.lower() in exts]

    if args.list_only:
        print("Real:", len(real_paths), "files")
        for p in real_paths:
            print(" ", p)
        print("Fake:", len(fake_paths), "files")
        for p in fake_paths:
            print(" ", p)
        return

    results = []
    for label, paths in [("real", real_paths), ("fake", fake_paths)]:
        for path in paths:
            try:
                image_bytes = path.read_bytes()
            except Exception as e:
                results.append({"path": str(path), "label": label, "error": str(e)})
                continue
            out = run_pipeline(image_bytes)
            out["path"] = str(path)
            out["label"] = label
            results.append(out)
            print(f"{path.name} [{label}] -> score={out['risk_score']} {out['classification']}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Strip non-JSON-serializable or large fields for compact output
        def serialize(r):
            if "error" in r:
                return r
            return {
                "path": r["path"],
                "label": r["label"],
                "risk_score": r["risk_score"],
                "classification": r["classification"],
                "layer_scores": r["layer_scores"],
                "signals_summary": [
                    {"layer": s.get("layer"), "name": s.get("name"), "flag": s.get("flag"), "weight": s.get("weight")}
                    for s in r.get("signals", [])
                ],
            }
        args.output.write_text(json.dumps([serialize(r) for r in results], indent=2))
        print(f"Wrote {len(results)} results to {args.output}")

    # Simple accuracy summary when we have labels (strict: real<=30, fake>=66)
    if real_paths or fake_paths:
        correct_strict = 0
        for r in results:
            if "error" in r:
                continue
            score = r["risk_score"]
            if r["label"] == "real" and score <= 30:
                correct_strict += 1
            elif r["label"] == "fake" and score >= 66:
                correct_strict += 1
        total = len([r for r in results if "error" not in r])
        if total:
            print(f"Summary: {correct_strict}/{total} correct (strict: real<=30, fake>=66)")


if __name__ == "__main__":
    main()
