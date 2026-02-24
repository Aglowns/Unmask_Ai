"""
LAYER 3a: Metadata Analyzer
─────────────────────────────────────────────────────────────────────────────
What is EXIF metadata?
  Every real photo taken with a camera or phone contains hidden data baked
  into the image file. This includes: camera brand, lens, shutter speed, ISO,
  GPS coordinates, and the software used to create/edit the file.

  AI-generated images usually have NO EXIF data, or they contain suspicious
  software signatures like "Midjourney", "Stable Diffusion", or "Python Pillow".

What this file does:
  1. Opens the image with Pillow (Python's image library)
  2. Reads EXIF metadata using piexif
  3. Flags suspicious patterns
  4. Returns a list of "signal" dicts that the scoring engine will use
"""

import io
from datetime import datetime
from PIL import Image
import piexif

# EXIF tag that stores the software name (e.g., "Adobe Photoshop", "Midjourney")
EXIF_SOFTWARE_TAG = 305

# Known AI generation tool names — if any of these appear in EXIF, big red flag
AI_TOOL_SIGNATURES = [
    "midjourney", "stable diffusion", "dall-e", "dalle",
    "firefly", "imagen", "sdxl", "comfyui", "automatic1111",
    "novelai", "dreamstudio", "runway",
    "ideogram", "leonardo", "kling", "runway gen", "luma",
    "flux", "playground", "replicate", "fal.ai", "together",
    "openai", "gemini", "copilot", "clipdrop", "remove.bg",
    "python pillow", "pillow", "gimp", "krita",
]


def analyze_metadata(image_bytes: bytes) -> list[dict]:
    """
    Main function called by app.py.

    Args:
        image_bytes: raw bytes of the uploaded image file

    Returns:
        A list of signal dicts. Each dict looks like:
        {
          "layer": "metadata",
          "name": "Human-readable check name",
          "value": "What we found",
          "flag": "clean" | "suspicious" | "neutral",
          "weight": 0-40   ← how much this adds to the risk score
        }
    """
    signals = []

    try:
        # Open the image with Pillow
        image = Image.open(io.BytesIO(image_bytes))

        # ── Check 1: Is there any EXIF data at all? ────────────────────────
        exif_raw = image.info.get("exif")

        if exif_raw is None:
            # Missing EXIF is common in AI images (they don't have a real camera)
            signals.append({
                "layer": "metadata",
                "name": "EXIF Data Presence",
                "value": "No EXIF metadata found",
                "flag": "suspicious",
                "weight": 15   # adds 15 to risk score
            })
        else:
            # EXIF exists — now let's dig into it
            signals.append({
                "layer": "metadata",
                "name": "EXIF Data Presence",
                "value": "EXIF metadata found",
                "flag": "clean",
                "weight": -5   # subtracts 5 from risk score (good sign)
            })

            # Parse the raw EXIF bytes into a readable dictionary
            try:
                exif_dict = piexif.load(exif_raw)

                # ── Check 2: Look for camera make/model ───────────────────
                ifd = exif_dict.get("0th", {})
                make = ifd.get(piexif.ImageIFD.Make, b"").decode("utf-8", errors="ignore").strip()
                model = ifd.get(piexif.ImageIFD.Model, b"").decode("utf-8", errors="ignore").strip()

                if make or model:
                    signals.append({
                        "layer": "metadata",
                        "name": "Camera Info",
                        "value": f"{make} {model}".strip() or "Unknown camera",
                        "flag": "clean",
                        "weight": -10   # real camera = authenticity signal
                    })
                else:
                    signals.append({
                        "layer": "metadata",
                        "name": "Camera Info",
                        "value": "No camera make/model found",
                        "flag": "suspicious",
                        "weight": 10
                    })

                # ── Check 3: Look for AI software signatures ───────────────
                software_bytes = ifd.get(EXIF_SOFTWARE_TAG, b"")
                software = software_bytes.decode("utf-8", errors="ignore").lower().strip()

                if software:
                    ai_match = next(
                        (tool for tool in AI_TOOL_SIGNATURES if tool in software),
                        None
                    )
                    if ai_match:
                        signals.append({
                            "layer": "metadata",
                            "name": "Software Signature",
                            "value": f"AI tool detected: '{software}'",
                            "flag": "suspicious",
                            "weight": 30   # very strong signal
                        })
                    else:
                        signals.append({
                            "layer": "metadata",
                            "name": "Software Signature",
                            "value": f"Software: {software}",
                            "flag": "clean",
                            "weight": 0
                        })

                # ── Check 4: GPS data (optional but interesting) ───────────
                gps_ifd = exif_dict.get("GPS", {})
                if gps_ifd:
                    signals.append({
                        "layer": "metadata",
                        "name": "GPS Data",
                        "value": "GPS coordinates found — real-world capture location present",
                        "flag": "clean",
                        "weight": -5
                    })

                # ── Check 5: DateTime consistency (capture before file time) ───
                exif_ifd = exif_dict.get("Exif", {})
                dt_original = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal, b"").decode("utf-8", errors="ignore").strip()
                ifd_0th = exif_dict.get("0th", {})
                dt_file = ifd_0th.get(piexif.ImageIFD.DateTime, b"").decode("utf-8", errors="ignore").strip()
                if dt_original and dt_file:
                    try:
                        # EXIF format: "YYYY:MM:DD HH:MM:SS"
                        t_orig = datetime.strptime(dt_original, "%Y:%m:%d %H:%M:%S")
                        t_file = datetime.strptime(dt_file, "%Y:%m:%d %H:%M:%S")
                        if t_orig > t_file:
                            signals.append({
                                "layer": "metadata",
                                "name": "Timestamp Consistency",
                                "value": "Capture time is after file time — inconsistent (may be edited or synthetic)",
                                "flag": "suspicious",
                                "weight": 12
                            })
                        else:
                            signals.append({
                                "layer": "metadata",
                                "name": "Timestamp Consistency",
                                "value": "Capture and file timestamps are consistent",
                                "flag": "clean",
                                "weight": -3
                            })
                    except ValueError:
                        pass

                # ── Check 6: DPI / resolution metadata ─────────────────────
                dpi = image.info.get("dpi")
                if dpi is not None and isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
                    x_dpi, y_dpi = float(dpi[0]), float(dpi[1])
                    # Common AI export DPIs: 72, 96, 144; cameras often 72, 180, 300, 350
                    if x_dpi in (72, 96) and y_dpi in (72, 96) and image.format == "PNG":
                        signals.append({
                            "layer": "metadata",
                            "name": "Resolution Metadata",
                            "value": f"DPI {x_dpi}x{y_dpi} — common for screen/export (PNG). Neutral.",
                            "flag": "neutral",
                            "weight": 2
                        })
                    elif x_dpi >= 200 or y_dpi >= 200:
                        signals.append({
                            "layer": "metadata",
                            "name": "Resolution Metadata",
                            "value": f"DPI {x_dpi}x{y_dpi} — typical of camera or print source",
                            "flag": "clean",
                            "weight": -2
                        })

                # ── Check 7: Color profile / color space ───────────────────
                icc = image.info.get("icc_profile")
                if icc is not None and len(icc) > 0:
                    signals.append({
                        "layer": "metadata",
                        "name": "Color Profile",
                        "value": "ICC profile present — suggests professional or camera workflow",
                        "flag": "clean",
                        "weight": -2
                    })

            except Exception:
                # piexif failed to parse — EXIF exists but is malformed
                signals.append({
                    "layer": "metadata",
                    "name": "EXIF Parse Error",
                    "value": "EXIF data exists but could not be parsed (may indicate manipulation)",
                    "flag": "suspicious",
                    "weight": 10
                })

    except Exception as e:
        # Couldn't even open the image — something is wrong
        signals.append({
            "layer": "metadata",
            "name": "Metadata Analysis Error",
            "value": f"Could not analyze metadata: {str(e)}",
            "flag": "neutral",
            "weight": 0
        })

    return signals
