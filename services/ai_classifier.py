"""
LAYER 4: AI Image Classifier — SightEngine + HuggingFace Ensemble
─────────────────────────────────────────────────────────────────────────────
What this does:
  Uses SightEngine's commercial-grade AI detection API (free tier: 2000 ops/month)
  as the PRIMARY detector, with HuggingFace models as FALLBACK.

  SightEngine specifically detects images from:
  - Nano Banana (Google Gemini)
  - Midjourney
  - DALL-E / GPT
  - Stable Diffusion / SDXL
  - Flux, Firefly, and more

API KEYS NEEDED:
  SightEngine (recommended):
    1. Sign up free at https://sightengine.com (no credit card needed)
    2. Get your api_user and api_secret from the dashboard
    3. Set environment variables:
       export SIGHTENGINE_API_USER=your_api_user
       export SIGHTENGINE_API_SECRET=your_api_secret

  HuggingFace (optional fallback):
    export HF_API_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
"""

import os
import io
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─────────────────────────────────────────────────────────────────────────────
# SIGHTENGINE CONFIG (primary detector)
# ─────────────────────────────────────────────────────────────────────────────
SIGHTENGINE_API_URL = "https://api.sightengine.com/1.0/check.json"
SIGHTENGINE_MODEL = "genai"

# Configurable probability bands for AI likelihood (tune for calibration)
# Above HIGH_AI → strong suspicious; above MODERATE_AI → moderate; above LOW_AI → neutral; else clean
AI_PROB_HIGH = 0.80
AI_PROB_MODERATE = 0.50
AI_PROB_LOW = 0.30
# Weights per band (suspicious positive, clean negative)
WEIGHT_HIGH_AI = 40
WEIGHT_MODERATE_AI = 25
WEIGHT_NEUTRAL_AI = 5
WEIGHT_CLEAN = -15

# ─────────────────────────────────────────────────────────────────────────────
# HUGGINGFACE MODELS (fallback)
# ─────────────────────────────────────────────────────────────────────────────
HF_MODELS = [
    {
        "id": "umm-maybe/AI-image-detector",
        "name": "ViT AI Detector",
        "ai_labels": ["artificial"],
        "real_labels": ["real"],
    },
    {
        "id": "Organika/sdxl-detector",
        "name": "SDXL Detector",
        "ai_labels": ["artificial", "ai"],
        "real_labels": ["real", "human"],
    },
]

HF_API_TEMPLATES = [
    "https://router.huggingface.co/hf-inference/models/{model_id}",
    "https://api-inference.huggingface.co/models/{model_id}",
]


def classify_image(image_bytes: bytes) -> list[dict]:
    """
    Main function called by app.py.
    Tries SightEngine first, falls back to HuggingFace models.
    """
    signals = []

    # ── Try SightEngine first (best accuracy) ─────────────────────────────
    se_user = os.environ.get("SIGHTENGINE_API_USER")
    se_secret = os.environ.get("SIGHTENGINE_API_SECRET")

    if se_user and se_secret:
        se_result = _call_sightengine(image_bytes, se_user, se_secret)
        signals.extend(se_result)

        # Check if SightEngine succeeded
        has_se_result = any(
            s.get("confidence") is not None for s in se_result
        )
        if has_se_result:
            return signals  # SightEngine worked — no need for HF fallback

    # ── Fallback: Try HuggingFace models ──────────────────────────────────
    hf_token = os.environ.get("HF_API_TOKEN")

    if not hf_token and not (se_user and se_secret):
        return [{
            "layer": "ai_detection",
            "name": "AI Model Ensemble",
            "value": "Skipped — No API keys set. Set SIGHTENGINE_API_USER + SIGHTENGINE_API_SECRET (recommended) or HF_API_TOKEN",
            "flag": "neutral",
            "weight": 0,
            "all_failed": True
        }]

    if hf_token:
        hf_signals = _call_hf_models(image_bytes, hf_token)
        signals.extend(hf_signals)

    # If we have no signals at all, add a failure marker
    if not signals:
        signals.append({
            "layer": "ai_detection",
            "name": "AI Model Ensemble",
            "value": "No API keys configured for AI detection.",
            "flag": "neutral",
            "weight": 0,
            "all_failed": True
        })

    return signals


# ─────────────────────────────────────────────────────────────────────────────
# SIGHTENGINE INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

def _call_sightengine(image_bytes: bytes, api_user: str, api_secret: str) -> list[dict]:
    """
    Calls SightEngine's genai model to detect AI-generated images.

    Returns a signal with the AI probability score.
    Response format: {"type": {"ai_generated": 0.95}, "status": "success"}
    """
    try:
        params = {
            "models": SIGHTENGINE_MODEL,
            "api_user": api_user,
            "api_secret": api_secret,
        }
        files = {"media": ("image.jpg", io.BytesIO(image_bytes), "image/jpeg")}

        response = requests.post(
            SIGHTENGINE_API_URL,
            files=files,
            data=params,
            timeout=30
        )

        if response.status_code != 200:
            return [{
                "layer": "ai_detection",
                "name": "SightEngine AI Detector",
                "value": f"API error: HTTP {response.status_code}",
                "flag": "neutral",
                "weight": 0
            }]

        result = response.json()

        if result.get("status") != "success":
            error_msg = result.get("error", {}).get("message", "Unknown error")
            return [{
                "layer": "ai_detection",
                "name": "SightEngine AI Detector",
                "value": f"API error: {error_msg}",
                "flag": "neutral",
                "weight": 0
            }]

        # Extract the AI-generated probability
        ai_prob = result.get("type", {}).get("ai_generated", 0.0)
        ai_pct = round(ai_prob * 100, 1)

        # Map to risk weight using configurable bands
        if ai_prob > AI_PROB_HIGH:
            weight = WEIGHT_HIGH_AI
            flag = "suspicious"
            verdict = f"High AI likelihood — SightEngine is {ai_pct}% confident this is AI-generated"
        elif ai_prob > AI_PROB_MODERATE:
            weight = WEIGHT_MODERATE_AI
            flag = "suspicious"
            verdict = f"Moderate AI likelihood — SightEngine is {ai_pct}% confident this is AI-generated"
        elif ai_prob > AI_PROB_LOW:
            weight = WEIGHT_NEUTRAL_AI
            flag = "neutral"
            verdict = f"Inconclusive — SightEngine shows {ai_pct}% AI probability"
        else:
            weight = WEIGHT_CLEAN
            flag = "clean"
            verdict = f"Low AI likelihood — SightEngine is {100 - ai_pct}% confident this is a real photo"

        return [{
            "layer": "ai_detection",
            "name": "SightEngine AI Detector",
            "value": verdict,
            "confidence": round(ai_prob, 3),
            "flag": flag,
            "weight": weight,
            "models_used": ["SightEngine genai"],
            "models_failed": [],
            "all_failed": False
        }]

    except requests.exceptions.Timeout:
        return [{
            "layer": "ai_detection",
            "name": "SightEngine AI Detector",
            "value": "Request timed out after 30s",
            "flag": "neutral",
            "weight": 0
        }]
    except Exception as e:
        return [{
            "layer": "ai_detection",
            "name": "SightEngine AI Detector",
            "value": f"Error: {str(e)}",
            "flag": "neutral",
            "weight": 0
        }]


# ─────────────────────────────────────────────────────────────────────────────
# HUGGINGFACE FALLBACK
# ─────────────────────────────────────────────────────────────────────────────

def _call_hf_models(image_bytes: bytes, hf_token: str) -> list[dict]:
    """Calls HF models in parallel as fallback when SightEngine isn't configured."""
    model_results = []

    with ThreadPoolExecutor(max_workers=len(HF_MODELS)) as executor:
        futures = {
            executor.submit(_call_hf_model, model, image_bytes, hf_token): model
            for model in HF_MODELS
        }
        for future in as_completed(futures):
            model = futures[future]
            try:
                result = future.result()
                model_results.append(result)
            except Exception as e:
                model_results.append({
                    "model_name": model["name"],
                    "ai_probability": None,
                    "error": str(e)
                })

    return _build_hf_ensemble_signals(model_results)


def _call_hf_model(model: dict, image_bytes: bytes, hf_token: str) -> dict:
    """Calls a single HF model, trying multiple API endpoints."""
    headers = {"Authorization": f"Bearer {hf_token}"}

    for api_template in HF_API_TEMPLATES:
        url = api_template.format(model_id=model["id"])
        try:
            response = requests.post(url, headers=headers, data=image_bytes, timeout=30)

            if response.status_code in (401, 403, 410, 503):
                continue

            if response.status_code != 200:
                continue

            results = response.json()
            if isinstance(results, list) and len(results) > 0:
                if isinstance(results[0], list):
                    results = results[0]

            scores = {}
            for item in results:
                if isinstance(item, dict) and "label" in item and "score" in item:
                    scores[item["label"].lower()] = item["score"]

            if not scores:
                continue

            ai_prob = 0.0
            for label in model["ai_labels"]:
                if label in scores:
                    ai_prob = scores[label]
                    break
            else:
                for label in model["real_labels"]:
                    if label in scores:
                        ai_prob = 1.0 - scores[label]
                        break

            return {
                "model_name": model["name"],
                "ai_probability": round(ai_prob, 4),
                "error": None
            }
        except Exception:
            continue

    return {
        "model_name": model["name"],
        "ai_probability": None,
        "error": "All API endpoints unavailable"
    }


def _build_hf_ensemble_signals(model_results: list[dict]) -> list[dict]:
    """Builds ensemble signals from HF model results."""
    signals = []
    successful_probs = []
    models_used = []
    models_failed = []

    for result in model_results:
        name = result["model_name"]
        if result.get("error") or result.get("ai_probability") is None:
            models_failed.append(name)
            signals.append({
                "layer": "ai_detection",
                "name": f"Model: {name}",
                "value": f"Error — {result.get('error', 'Unknown')}",
                "flag": "neutral",
                "weight": 0
            })
        else:
            prob = result["ai_probability"]
            successful_probs.append(prob)
            models_used.append(name)
            signals.append({
                "layer": "ai_detection",
                "name": f"Model: {name}",
                "value": f"{round(prob * 100, 1)}% AI probability",
                "confidence": prob,
                "flag": "suspicious" if prob > 0.50 else "clean",
                "weight": 0
            })

    if not successful_probs:
        signals.insert(0, {
            "layer": "ai_detection",
            "name": "HF Model Ensemble",
            "value": f"All {len(models_failed)} HF models unavailable.",
            "flag": "neutral",
            "weight": 0,
            "models_used": [],
            "models_failed": models_failed,
            "all_failed": True
        })
    else:
        ensemble_prob = sum(successful_probs) / len(successful_probs)
        ensemble_pct = round(ensemble_prob * 100, 1)
        # Use same configurable bands as SightEngine (HF weights slightly lower)
        if ensemble_prob > AI_PROB_HIGH:
            weight, flag = 35, "suspicious"
            verdict = f"High AI likelihood — {ensemble_pct}% confident"
        elif ensemble_prob > AI_PROB_MODERATE:
            weight, flag = 20, "suspicious"
            verdict = f"Moderate AI likelihood — {ensemble_pct}% confident"
        else:
            weight, flag = -10, "clean"
            verdict = f"Low AI likelihood — {100 - ensemble_pct}% confident this is real"

        signals.insert(0, {
            "layer": "ai_detection",
            "name": "HF Model Ensemble",
            "value": verdict,
            "confidence": round(ensemble_prob, 3),
            "flag": flag,
            "weight": weight,
            "models_used": models_used,
            "models_failed": models_failed,
            "all_failed": False
        })

    return signals
