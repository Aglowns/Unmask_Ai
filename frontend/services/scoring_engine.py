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
     signals are boosted to compensate
  4. Per-layer sub-scores — enables frontend breakdown charts
  5. Metadata trust gate — metadata influence is reduced unless other layers
     confirm real; can be softened when only one other layer has data
  6. Uncertainty handling — when only one layer has usable data, we cap
     the adjustment so the score doesn't swing too far on a single signal

Score interpretation:
  0–30  → Green  — Low Risk (likely authentic)
  31–65 → Yellow — Medium Risk (mixed signals, proceed with caution)
  66–100 → Red   — High Risk (likely AI-generated)
"""

# ─── Configurable scoring (tune via constants or future config) ─────────────
BASE_SCORE = 25
# Band boundaries for classification
BAND_LOW_MAX = 30
BAND_MEDIUM_MAX = 65
# Layer agreement bonuses
BONUS_SUSPICIOUS_3_LAYERS = 10
BONUS_SUSPICIOUS_2_LAYERS = 5
BONUS_CLEAN_3_LAYERS = -8
BONUS_CLEAN_2_LAYERS = -3
# When AI models failed and forensics are suspicious
BONUS_FORENSICS_AMP_EXTRA = 8
# Forensics/metadata amplification when AI layer failed
FORENSICS_AMP_MULTIPLIER = 1.5
# Uncertainty: max absolute adjustment when only one layer has non-neutral data
UNCERTAINTY_SINGLE_LAYER_CAP = 25
# Metadata trust: require both forensics AND ai_detection clean to use metadata?
# If False, we only exclude metadata when BOTH other layers exist and disagree.
METADATA_REQUIRE_BOTH_CLEAN = True


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


def _count_layers_with_data(signals: list[dict]) -> int:
    """Number of layers that have at least one non-neutral flag."""
    layers_with_data = set()
    for s in signals:
        if s.get("flag", "neutral") != "neutral":
            layers_with_data.add(s.get("layer", "unknown"))
    return len(layers_with_data)


def calculate_risk_score(signals: list[dict]) -> tuple[int, str]:
    """
    Main function called by app.py.

    Args:
        signals: list of signal dicts from all layers

    Returns:
        Tuple of (risk_score: int, classification: str)
        e.g. (78, "high_risk")
    """
    total_adjustment = 0

    # ── Metadata trust gate ───────────────────────────────────────────────
    forensics_clean = _is_layer_clean(signals, "forensics")
    ai_clean = _is_layer_clean(signals, "ai_detection")
    if METADATA_REQUIRE_BOTH_CLEAN and not (forensics_clean and ai_clean):
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
        if ai_models_failed and layer in ("forensics", "metadata"):
            adjusted_weight *= FORENSICS_AMP_MULTIPLIER

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
        total_adjustment += BONUS_SUSPICIOUS_3_LAYERS
    elif suspicious_layers >= 2:
        total_adjustment += BONUS_SUSPICIOUS_2_LAYERS

    if clean_layers >= 3:
        total_adjustment += BONUS_CLEAN_3_LAYERS
    elif clean_layers >= 2:
        total_adjustment += BONUS_CLEAN_2_LAYERS

    if ai_models_failed and suspicious_layers >= 2:
        total_adjustment += BONUS_FORENSICS_AMP_EXTRA

    # ── Uncertainty: when only one layer has data, cap the adjustment ───────
    layers_with_data = _count_layers_with_data(signals)
    if layers_with_data <= 1 and layers_with_data > 0:
        total_adjustment = max(
            -UNCERTAINTY_SINGLE_LAYER_CAP,
            min(UNCERTAINTY_SINGLE_LAYER_CAP, total_adjustment)
        )

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
    if score <= BAND_LOW_MAX:
        return "low_risk"
    elif score <= BAND_MEDIUM_MAX:
        return "medium_risk"
    else:
        return "high_risk"
