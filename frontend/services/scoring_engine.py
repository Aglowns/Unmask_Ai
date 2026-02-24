"""
SCORING ENGINE (v3 — Majority Vote)
─────────────────────────────────────────────────────────────────────────────
What this does:
  Collects all the signals from every detection layer and combines them into
  one final risk score between 0 and 100.

  KEY FEATURES:
  1. Per-layer sub-scores — each layer (metadata, forensics, AI) gets its own
     score that determines its "verdict" (low / medium / high)
  2. Majority vote — the final classification is decided by what 2 out of 3
     layers agree on. If 2+ say low → low. If 2+ say high → high.
  3. AI detection as tiebreaker — when all 3 disagree, AI detection decides
     because it's the most purpose-built detector
  4. Confidence-weighted scoring — signals with higher confidence count more
  5. Forensics amplification — when AI models are unavailable, forensics
     signals are boosted to compensate
  6. All layers always participate — metadata is never thrown away

Score interpretation:
  0–30  → Green  — Low Risk (likely authentic)
  31–65 → Yellow — Medium Risk (mixed signals, proceed with caution)
  66–100 → Red   — High Risk (likely AI-generated)
"""

# ─── Configurable scoring ───────────────────────────────────────────────────
BASE_SCORE = 25
BAND_LOW_MAX = 30
BAND_MEDIUM_MAX = 65

# Forensics amplification when AI layer failed
FORENSICS_AMP_MULTIPLIER = 1.5

# Layer sub-score normalization: raw weight sum → 0–100 via (30 + sum * 1.75)
LAYER_SCORE_BASE = 30
LAYER_SCORE_SCALE = 1.75

# The three detection layers that participate in the majority vote
VOTE_LAYERS = ("metadata", "forensics", "ai_detection")


def _layer_verdict(score: int) -> str:
    """Classify a single layer's sub-score into low / medium / high."""
    if score <= BAND_LOW_MAX:
        return "low"
    elif score <= BAND_MEDIUM_MAX:
        return "medium"
    else:
        return "high"


def calculate_layer_scores(signals: list[dict]) -> dict:
    """
    Calculates per-layer sub-scores for the frontend breakdown chart.
    Each layer's signal weights are summed and normalized to 0–100.
    """
    layer_weights: dict[str, float] = {}

    for signal in signals:
        layer = signal.get("layer", "unknown")
        weight = signal.get("weight", 0)
        if layer not in layer_weights:
            layer_weights[layer] = 0
        layer_weights[layer] += weight

    layer_scores = {}
    for layer, total_weight in layer_weights.items():
        normalized = max(0, min(100, int(LAYER_SCORE_BASE + total_weight * LAYER_SCORE_SCALE)))
        layer_scores[layer] = normalized

    return layer_scores


def _majority_vote(layer_scores: dict) -> tuple[str, str | None]:
    """
    Determines the majority verdict across the three detection layers.

    Returns:
        (majority_verdict, tiebreaker_source)
        - majority_verdict: "low", "medium", "high", or "mixed"
        - tiebreaker_source: which layer broke the tie, or None
    """
    verdicts = {}
    for layer in VOTE_LAYERS:
        score = layer_scores.get(layer)
        if score is not None:
            verdicts[layer] = _layer_verdict(score)

    if not verdicts:
        return "medium", None

    counts = {"low": 0, "medium": 0, "high": 0}
    for v in verdicts.values():
        counts[v] += 1

    # 2+ layers agree → that's the answer
    if counts["low"] >= 2:
        return "low", None
    if counts["high"] >= 2:
        return "high", None
    if counts["medium"] >= 2:
        return "medium", None

    # All 3 disagree (one low, one medium, one high) → AI detection breaks tie
    ai_verdict = verdicts.get("ai_detection")
    if ai_verdict:
        return ai_verdict, "ai_detection"

    # AI layer missing — fall back to metadata, then forensics
    for fallback in ("metadata", "forensics"):
        if fallback in verdicts:
            return verdicts[fallback], fallback

    return "medium", None


def calculate_risk_score(signals: list[dict]) -> tuple[int, str]:
    """
    Main function called by app.py.

    Args:
        signals: list of signal dicts from all layers

    Returns:
        Tuple of (risk_score: int, classification: str)
        e.g. (78, "high_risk")
    """
    # ── Step 1: Compute per-layer sub-scores ──────────────────────────────
    layer_scores = calculate_layer_scores(signals)

    # ── Step 2: Compute numeric score from signal weights ─────────────────
    ai_models_failed = any(
        s.get("all_failed", False) for s in signals
        if s.get("layer") == "ai_detection"
    )

    total_adjustment = 0.0
    for signal in signals:
        layer = signal.get("layer", "unknown")
        weight = signal.get("weight", 0)
        confidence = signal.get("confidence", None)

        if confidence is not None and isinstance(confidence, (int, float)):
            adjusted_weight = weight * (0.5 + confidence * 0.5)
        else:
            adjusted_weight = weight

        if ai_models_failed and layer in ("forensics", "metadata"):
            adjusted_weight *= FORENSICS_AMP_MULTIPLIER

        total_adjustment += adjusted_weight

    raw_score = BASE_SCORE + total_adjustment
    numeric_score = max(0, min(100, int(round(raw_score))))

    # ── Step 3: Majority vote across layers ───────────────────────────────
    majority, _tiebreaker = _majority_vote(layer_scores)

    # ── Step 4: Clamp the numeric score to match the majority verdict ─────
    if majority == "low":
        risk_score = min(numeric_score, BAND_LOW_MAX)
        classification = "low_risk"
    elif majority == "high":
        risk_score = max(numeric_score, BAND_MEDIUM_MAX + 1)
        classification = "high_risk"
    else:
        # Medium or mixed — let the numeric score decide within the medium band
        risk_score = max(BAND_LOW_MAX + 1, min(BAND_MEDIUM_MAX, numeric_score))
        classification = "medium_risk"

    return risk_score, classification


def _classify_score(score: int) -> str:
    """Converts a numeric score into a string classification label."""
    if score <= BAND_LOW_MAX:
        return "low_risk"
    elif score <= BAND_MEDIUM_MAX:
        return "medium_risk"
    else:
        return "high_risk"
