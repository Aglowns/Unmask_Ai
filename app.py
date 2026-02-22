"""
AI Media Authenticity Detection System
Main FastAPI Application — HackUNCP 2026

HOW THIS FILE WORKS:
  This is the "front door" of your backend.
  When someone sends an image to your API, the request comes here first.
  It then calls each detection layer (metadata, forensics, AI) in order,
  collects their results (called "signals"), and returns a final risk score.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time

# Import our service layers (each file = one detection layer)
from services.metadata_analyzer import analyze_metadata
from services.forensics_checker import run_forensics
from services.ai_classifier import classify_image
from services.scoring_engine import calculate_risk_score, calculate_layer_scores

# ─────────────────────────────────────────────────────────────────────────────
# 1. CREATE THE FASTAPI APP
#    Think of this like creating your web server.
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Media Authenticity Detector",
    description="Detects AI-generated images using multi-layer analysis",
    version="1.0.0"
)

# ─────────────────────────────────────────────────────────────────────────────
# 2. CORS MIDDLEWARE
#    CORS = Cross-Origin Resource Sharing.
#    Without this, your Next.js frontend (on Vercel) can't talk to this backend
#    (on Render) because browsers block cross-site requests by default.
# ─────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ⚠️ For production, replace "*" with your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 3. HEALTH CHECK ENDPOINT
#    URL: GET https://your-app.onrender.com/
#    Render pings this to verify your server started correctly.
#    If this returns a 200 OK, Render marks your service as "Live".
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "AI Authenticity Detector is running!"
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN ANALYSIS ENDPOINT
#    URL: POST https://your-app.onrender.com/api/analyze
#    This is the core of the system. Upload an image → get back a risk score.
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/analyze")
async def analyze_media(file: UploadFile = File(...)):
    """
    Accepts an image upload and runs it through all 4 detection layers.
    Returns a risk score (0-100) with a full evidence breakdown.

    Parameters:
      file — the uploaded image (JPEG, PNG, or WebP)

    Returns:
      JSON with risk_score, classification, and a list of signals
    """

    # ── Validate file type ─────────────────────────────────────────────────
    ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file: '{file.content_type}'. Please upload JPEG, PNG, or WebP."
        )

    # ── Read image bytes into memory ───────────────────────────────────────
    # We work with raw bytes so we don't need to save files to disk
    start_time = time.time()
    image_bytes = await file.read()

    # ── Run detection layers and collect signals ───────────────────────────
    # Each layer returns a list of "signal" dicts that describe what it found
    signals = []

    # LAYER 3a: Metadata Analysis — checks EXIF data (camera info, GPS, etc.)
    metadata_signals = analyze_metadata(image_bytes)
    signals.extend(metadata_signals)

    # LAYER 3b: Forensics — checks for ELA anomalies, noise patterns, etc.
    forensics_signals = run_forensics(image_bytes)
    signals.extend(forensics_signals)

    # LAYER 4: AI Classifier — runs image through a Hugging Face ML model
    ai_signals = classify_image(image_bytes)
    signals.extend(ai_signals)

    # ── Calculate the final weighted risk score ────────────────────────────
    risk_score, classification = calculate_risk_score(signals)

    # ── Calculate per-layer breakdown for frontend charts ─────────────────
    layer_scores = calculate_layer_scores(signals)

    # ── Extract AI detection metadata ─────────────────────────────────────
    # Find the main AI detection signal (SightEngine or HF Ensemble)
    ai_signal = next(
        (s for s in signals
         if s.get("layer") == "ai_detection" and s.get("models_used") is not None),
        None
    )
    models_used = ai_signal.get("models_used", []) if ai_signal else []
    models_failed = ai_signal.get("models_failed", []) if ai_signal else []
    ensemble_confidence = ai_signal.get("confidence", None) if ai_signal else None

    # ── Return the full result ─────────────────────────────────────────────
    return {
        "file_name": file.filename,
        "type": "image",
        "risk_score": risk_score,                     # 0–100
        "classification": classification,             # "low_risk", "medium_risk", "high_risk"
        "confidence": ensemble_confidence,            # AI model ensemble confidence
        "signals": signals,                           # detailed evidence list
        "layer_scores": layer_scores,                 # per-layer sub-scores
        "models_used": models_used,                   # which AI models contributed
        "models_failed": models_failed,               # which AI models errored
        "processing_time_ms": int((time.time() - start_time) * 1000),
        "recommendation": _build_recommendation(risk_score)
    }


def _build_recommendation(risk_score: int) -> str:
    """Turns a numeric risk score into a plain-English recommendation."""
    if risk_score <= 30:
        return "✅ Low Risk — This image shows strong indicators of authenticity."
    elif risk_score <= 65:
        return "⚠️ Medium Risk — Mixed signals detected. Verify from original source."
    else:
        return "🚨 High Risk — Multiple red flags. This image is likely AI-generated."


# ─────────────────────────────────────────────────────────────────────────────
# 5. LOCAL DEV RUNNER
#    Run this file directly on your laptop: python app.py
#    Render does NOT use this — it uses the start command in render.yaml instead.
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
