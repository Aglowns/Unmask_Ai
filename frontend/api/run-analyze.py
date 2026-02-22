"""
Vercel serverless API: /api/run-analyze
Runs the same analysis as the FastAPI app — metadata, forensics, AI classifier.
"""
import time
from fastapi import FastAPI, UploadFile, File, HTTPException

from services.metadata_analyzer import analyze_metadata
from services.forensics_checker import run_forensics
from services.ai_classifier import classify_image
from services.scoring_engine import calculate_risk_score, calculate_layer_scores

app = FastAPI()


def _build_recommendation(risk_score: int) -> str:
    if risk_score <= 30:
        return "✅ Low Risk — This image shows strong indicators of authenticity."
    elif risk_score <= 65:
        return "⚠️ Medium Risk — Mixed signals detected. Verify from original source."
    else:
        return "🚨 High Risk — Multiple red flags. This image is likely AI-generated."


@app.post("/")
@app.post("/api/run-analyze")
async def analyze_media(file: UploadFile = File(...)):
    ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file: '{file.content_type}'. Please upload JPEG, PNG, or WebP.",
        )

    start_time = time.time()
    image_bytes = await file.read()

    signals = []
    metadata_signals = analyze_metadata(image_bytes)
    signals.extend(metadata_signals)

    forensics_signals = run_forensics(image_bytes)
    signals.extend(forensics_signals)

    ai_signals = classify_image(image_bytes)
    signals.extend(ai_signals)

    risk_score, classification = calculate_risk_score(signals)
    layer_scores = calculate_layer_scores(signals)

    ai_signal = next(
        (
            s
            for s in signals
            if s.get("layer") == "ai_detection" and s.get("models_used") is not None
        ),
        None,
    )
    models_used = ai_signal.get("models_used", []) if ai_signal else []
    models_failed = ai_signal.get("models_failed", []) if ai_signal else []
    ensemble_confidence = ai_signal.get("confidence", None) if ai_signal else None

    return {
        "file_name": file.filename,
        "type": "image",
        "risk_score": risk_score,
        "classification": classification,
        "confidence": ensemble_confidence,
        "signals": signals,
        "layer_scores": layer_scores,
        "models_used": models_used,
        "models_failed": models_failed,
        "processing_time_ms": int((time.time() - start_time) * 1000),
        "recommendation": _build_recommendation(risk_score),
    }
