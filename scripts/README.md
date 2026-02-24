# Scripts

## Pipeline evaluation

To tune thresholds and weights using your own labeled images:

1. Create a folder (e.g. `evaluation_samples/`) with two subfolders:
   - `real/` — images you know are real/camera photos
   - `fake/` — images you know are AI-generated

2. Run from the **repo root**:
   ```bash
   python scripts/run_evaluation.py --samples-dir evaluation_samples --output evaluation_results.json
   ```

3. The script runs the full pipeline (metadata, forensics, AI classifier, scoring) on each image, prints risk score and classification per file, and writes detailed results to the JSON file. Use the output to adjust constants in:
   - `services/metadata_analyzer.py`
   - `services/forensics_checker.py` (ELA_*, NOISE_*, FFT_*, GRID_*)
   - `services/ai_classifier.py` (AI_PROB_*, WEIGHT_*)
   - `services/scoring_engine.py` (BASE_SCORE, BAND_*, BONUS_*, UNCERTAINTY_*)

Options:
- `--list-only` — only list sample paths, do not run the pipeline
- `--output path` — write results JSON to `path`
