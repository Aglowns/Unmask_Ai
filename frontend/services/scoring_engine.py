"""
SCORING ENGINE (Enhanced v2)
─────────────────────────────────────────────────────────────────────────────
What this does:
  Collects all the signals from every detection layer and combines them into
  one final risk score between 0 and 100.

  KEY FEATURES:
  1. Confidence-weighted scoring — signals with higher confidence count more
  2. Layer agreement bonus — multiple layers agreeing amplifies the signal
  3. Forensics amplification — when AI models are unavailable, forensics
     signals are boosted to compensate (so we still get strong scores)
  4. Per-layer sub-scores — enables frontend breakdown charts
  5. Metadata trust gate — metadata can ONLY influence the score when BOTH
     forensics AND ai_detection actively confirm the image is real. If they
     disagree, both flag AI, or either layer has no data, metadata is excluded

Score interpretation:
  0–30  → Green  — Low Risk (likely authentic)
  31–65 → Yellow — Medium Risk (mixed signals, proceed with caution)
  66–100 → Red   — High Risk (likely AI-generated)
"""


def _is_layer_clean(signals: list[dict], layer_name: str) -> bool:
    """
    Returns True ONLY if the given layer actively confirms the image is real.
    Requires at least one non-neutral flag, with clean signals outnumbering
    suspicious ones. If the layer has no data, timed out, or returned only
    neutral signals, this returns False — meaning we can't confirm authenticity.
    """
    flags = [s.get("flag", "neutral") for s in signals if s.get("layer") == layer_name]
    non_neutral = [f for f in flags if f != "neutral"]
    if not non_neutral:
        return False  # no usable data = can't confirm real
    clean_count = sum(1 for f in non_neutral if f == "clean")
    suspicious_count = sum(1 for f in non_neutral if f == "suspicious")
    return clean_count > suspicious_count


def calculate_risk_score(signals: list[dict]) -> tuple[int, str]:
    """
    Main function called by app.py.

    Args:
        signals: list of signal dicts from all layers

    Returns:
        Tuple of (risk_score: int, classification: str)
        e.g. (78, "high_risk")
    """

    BASE_SCORE = 25
    total_adjustment = 0

    # ── Metadata trust gate: metadata can ONLY influence the score when BOTH
    #    forensics AND ai_detection actively confirm the image is real.
    #    If they disagree, both flag AI, or either has no usable data,
    #    metadata is completely excluded to prevent easily-faked EXIF from
    #    skewing results.
    forensics_clean = _is_layer_clean(signals, "forensics")
    ai_clean = _is_layer_clean(signals, "ai_detection")
    if not (forensics_clean and ai_clean):
        signals = [s for s in signals if s.get("layer") != "metadata"]

    # ── Check if AI models failed (so we can amplify forensics) ────────────
    ai_models_failed = any(
        s.get("all_failed", False) for s in signals
        if s.get("layer") == "ai_detection"
    )

    # ── Group signals by layer for agreement analysis ──────────────────────
    layer_signals = {}
    for signal in signals:
        layer = signal.get("layer", "unknown")
        weight = signal.get("weight", 0)
        confidence = signal.get("confidence", None)
        flag = signal.get("flag", "neutral")

        # Confidence-weighted scoring
        if confidence is not None and isinstance(confidence, (int, float)):
            confidence_multiplier = 0.5 + (confidence * 0.5)
            adjusted_weight = weight * confidence_multiplier
        else:
            adjusted_weight = weight

        # ── FORENSICS AMPLIFICATION ────────────────────────────────────────
        # When AI models are down, forensics and metadata signals carry more
        # weight to compensate for the missing AI detection layer.
        if ai_models_failed and layer in ("forensics", "metadata"):
            amplification = 1.5  # 50% boost
            adjusted_weight *= amplification

        total_adjustment += adjusted_weight

        # Track flags per layer
        if layer not in layer_signals:
            layer_signals[layer] = []
        layer_signals[layer].append(flag)

    # ── Layer agreement bonus ──────────────────────────────────────────────
    suspicious_layers = 0
    clean_layers = 0

    for layer, flags in layer_signals.items():
        non_neutral = [f for f in flags if f != "neutral"]
        if not non_neutral:
            continue

        suspicious_count = sum(1 for f in non_neutral if f == "suspicious")
        clean_count = sum(1 for f in non_neutral if f == "clean")

        if suspicious_count > clean_count:
            suspicious_layers += 1
        elif clean_count > suspicious_count:
            clean_layers += 1

    # Cross-layer agreement bonuses
    if suspicious_layers >= 3:
        total_adjustment += 10
    elif suspicious_layers >= 2:
        total_adjustment += 5

    if clean_layers >= 3:
        total_adjustment -= 8
    elif clean_layers >= 2:
        total_adjustment -= 3

    # ── Extra boost when AI models are down and forensics are suspicious ──
    # This ensures we still get meaningful high scores for AI images
    if ai_models_failed and suspicious_layers >= 2:
        total_adjustment += 8  # extra push since we're missing AI layer

    # ── Final score calculation ────────────────────────────────────────────
    raw_score = BASE_SCORE + total_adjustment
    risk_score = max(0, min(100, int(round(raw_score))))

    classification = _classify_score(risk_score)

    return risk_score, classification


def calculate_layer_scores(signals: list[dict]) -> dict:
    """
    Calculates per-layer sub-scores for the frontend breakdown chart.
    """
    layer_weights = {}

    for signal in signals:
        layer = signal.get("layer", "unknown")
        weight = signal.get("weight", 0)

        if layer not in layer_weights:
            layer_weights[layer] = 0
        layer_weights[layer] += weight

    layer_scores = {}
    for layer, total_weight in layer_weights.items():
        normalized = max(0, min(100, int(30 + total_weight * 1.75)))
        layer_scores[layer] = normalized

    return layer_scores


def _classify_score(score: int) -> str:
    """Converts a numeric score into a string classification label."""
    if score <= 30:
        return "low_risk"
    elif score <= 65:
        return "medium_risk"
    else:
        return "high_risk"
