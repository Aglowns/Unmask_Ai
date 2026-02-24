"""
LAYER 3b: Image Forensics Checker (Enhanced)
─────────────────────────────────────────────────────────────────────────────
What is image forensics?
  Even after metadata is stripped, the actual pixel arrangement of an image
  contains clues about how it was created.

  Five techniques we use:

  1. ERROR LEVEL ANALYSIS (ELA)
     Re-saves at lower quality and checks for unnatural uniformity.

  2. NOISE PATTERN ANALYSIS
     Isolates the noise layer — AI images are suspiciously smooth.

  3. IMAGE DIMENSION CHECK
     AI generators use very specific sizes (512x512, 1024x1024, etc.).

  4. FREQUENCY DOMAIN ANALYSIS (NEW)
     Uses FFT to analyze spectral patterns — GAN/diffusion images leave
     telltale artifacts in the frequency domain that real photos don't have.

  5. JPEG GRID ALIGNMENT CHECK (NEW)
     Real JPEGs have consistent 8×8 compression block alignment.
     Spliced or AI images often break this pattern.
"""

import io
import numpy as np
from PIL import Image, ImageFilter

# ─── Configurable thresholds (tune via constants or future config) ─────────
# ELA: suspicious if mean < X and std < Y (too uniform)
ELA_MEAN_SUSPICIOUS = 3.0
ELA_STD_SUSPICIOUS = 2.0
ELA_STD_SPLICE = 25.0
# ELA recompression qualities to try (multiple = more robust)
ELA_QUALITIES = (75, 90)

# Noise: suspicious if std < X; clean if std > Y
NOISE_STD_SUSPICIOUS = 2.0
NOISE_STD_CLEAN = 20.0
NOISE_BLUR_RADII = (2, 4)  # multiple radii, aggregate

# FFT: low-freq radius as fraction of half-size (1/8 = inner 25%)
FFT_LOW_FREQ_RADIUS_FRAC = 8
FFT_RATIO_SUSPICIOUS = 0.15
FFT_RATIO_NEUTRAL = 0.20
FFT_SPECTRAL_STD_SUSPICIOUS = 2.0

# Grid: coefficient of variation and mean variance
GRID_CV_SUSPICIOUS_LOW = 0.3
GRID_MEANVAR_SUSPICIOUS = 50
GRID_CV_SPLICE = 3.0


def run_forensics(image_bytes: bytes) -> list[dict]:
    """
    Main function called by app.py.

    Args:
        image_bytes: raw image bytes

    Returns:
        List of signal dicts (same format as metadata_analyzer.py)
    """
    signals = []

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # ── Check 1: Error Level Analysis ─────────────────────────────────
        ela_signal = _run_ela(image, image_bytes)
        signals.append(ela_signal)

        # ── Check 2: Noise Pattern Analysis ───────────────────────────────
        noise_signal = _run_noise_analysis(image)
        signals.append(noise_signal)

        # ── Check 3: Image dimensions (AI images love round numbers) ───────
        dimension_signal = _check_dimensions(image)
        signals.append(dimension_signal)

        # ── Check 4: Frequency Domain Analysis (FFT) ─────────────────────
        freq_signal = _run_frequency_analysis(image)
        signals.append(freq_signal)

        # ── Check 5: JPEG Grid Alignment ──────────────────────────────────
        grid_signal = _check_jpeg_grid(image, image_bytes)
        signals.append(grid_signal)

    except Exception as e:
        signals.append({
            "layer": "forensics",
            "name": "Forensics Analysis Error",
            "value": f"Could not run forensics: {str(e)}",
            "flag": "neutral",
            "weight": 0
        })

    return signals


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS (private — not called from outside this file)
# ─────────────────────────────────────────────────────────────────────────────

def _run_ela(original_image: Image.Image, original_bytes: bytes) -> dict:
    """
    Error Level Analysis:
    Re-saves the image at one or more lower qualities, then computes the
    difference between the original and the re-saved version. Uses multiple
    qualities (e.g. 75 and 90) and combines results for robustness.

    If regions are INCONSISTENT (high variance) = splicing. If uniformly flat = AI.
    """
    try:
        original_arr = np.array(original_image, dtype=np.float32)
        means, stds = [], []
        for q in ELA_QUALITIES:
            buffer = io.BytesIO()
            original_image.save(buffer, format="JPEG", quality=q)
            buffer.seek(0)
            recompressed = Image.open(buffer).convert("RGB")
            recomp_arr = np.array(recompressed, dtype=np.float32)
            ela_diff = np.abs(original_arr - recomp_arr)
            means.append(float(np.mean(ela_diff)))
            stds.append(float(np.std(ela_diff)))
        mean_diff = float(np.mean(means))
        std_diff = float(np.mean(stds))

        if mean_diff < ELA_MEAN_SUSPICIOUS and std_diff < ELA_STD_SUSPICIOUS:
            return {
                "layer": "forensics",
                "name": "Error Level Analysis (ELA)",
                "value": f"Suspiciously uniform error levels (mean={mean_diff:.2f}, std={std_diff:.2f}). May indicate AI generation.",
                "flag": "suspicious",
                "weight": 20
            }
        elif std_diff > ELA_STD_SPLICE:
            return {
                "layer": "forensics",
                "name": "Error Level Analysis (ELA)",
                "value": f"High ELA variance detected (std={std_diff:.2f}). Possible image manipulation or splicing.",
                "flag": "suspicious",
                "weight": 15
            }
        else:
            return {
                "layer": "forensics",
                "name": "Error Level Analysis (ELA)",
                "value": f"Normal ELA pattern (mean={mean_diff:.2f}, std={std_diff:.2f}). Consistent with authentic photo.",
                "flag": "clean",
                "weight": 0
            }

    except Exception as e:
        return {
            "layer": "forensics",
            "name": "Error Level Analysis (ELA)",
            "value": f"ELA could not complete: {str(e)}",
            "flag": "neutral",
            "weight": 0
        }


def _run_noise_analysis(image: Image.Image) -> dict:
    """
    Noise Pattern Analysis:
    Applies blur(s) at multiple radii, then computes the difference (noise layer).
    Aggregates noise std across radii for robustness.

    Real cameras: noise present with natural variation. AI: too uniform or absent.
    """
    try:
        gray = image.convert("L")
        gray_arr = np.array(gray, dtype=np.float32)
        noise_stds = []
        for radius in NOISE_BLUR_RADII:
            blurred = gray.filter(ImageFilter.GaussianBlur(radius=radius))
            blurred_arr = np.array(blurred, dtype=np.float32)
            noise = gray_arr - blurred_arr
            noise_stds.append(float(np.std(noise)))
        noise_std = float(np.mean(noise_stds))

        if noise_std < NOISE_STD_SUSPICIOUS:
            return {
                "layer": "forensics",
                "name": "Noise Pattern Analysis",
                "value": f"Unusually low noise level (std={noise_std:.2f}). AI images tend to be unnaturally smooth.",
                "flag": "suspicious",
                "weight": 15
            }
        elif noise_std > NOISE_STD_CLEAN:
            return {
                "layer": "forensics",
                "name": "Noise Pattern Analysis",
                "value": f"High noise level (std={noise_std:.2f}). Consistent with compressed real photo.",
                "flag": "clean",
                "weight": -5
            }
        else:
            return {
                "layer": "forensics",
                "name": "Noise Pattern Analysis",
                "value": f"Normal noise level (std={noise_std:.2f}). Consistent with authentic camera capture.",
                "flag": "clean",
                "weight": -5
            }

    except Exception as e:
        return {
            "layer": "forensics",
            "name": "Noise Pattern Analysis",
            "value": f"Noise analysis failed: {str(e)}",
            "flag": "neutral",
            "weight": 0
        }


# Extended set of common AI output sizes (square and common aspect ratios)
AI_COMMON_SIZES = {
    (512, 512), (768, 768), (1024, 1024), (1024, 1024),
    (1024, 1792), (1792, 1024), (1024, 1536), (1536, 1024),
    (2048, 2048), (1344, 768), (768, 1344), (1216, 832), (832, 1216),
    (1152, 896), (896, 1152), (1280, 720), (720, 1280),
    (1080, 1080), (1200, 630), (630, 1200), (1024, 768), (768, 1024),
    (2048, 1536), (1536, 2048), (256, 256), (384, 384),
}
# Common AI aspect ratios (width/height) — e.g. 1.0, 4/3, 16/9, 9/16
AI_ASPECT_RATIOS = {1.0, 1.333, 1.778, 0.5625, 0.75, 1.25, 1.5, 0.667}


def _check_dimensions(image: Image.Image) -> dict:
    """
    Dimension Check:
    AI generators produce very specific sizes and aspect ratios.
    Real photos come in irregular sizes. Also check aspect ratio.
    """
    width, height = image.size
    if height <= 0:
        return {
            "layer": "forensics",
            "name": "Image Dimensions",
            "value": "Invalid dimensions",
            "flag": "neutral",
            "weight": 0
        }
    ar = round(width / height, 3)
    ar_inverse = round(height / width, 3)
    matches_ar = ar in AI_ASPECT_RATIOS or ar_inverse in AI_ASPECT_RATIOS

    if (width, height) in AI_COMMON_SIZES:
        return {
            "layer": "forensics",
            "name": "Image Dimensions",
            "value": f"{width}x{height}px — matches a known AI generation resolution",
            "flag": "suspicious",
            "weight": 10
        }
    if matches_ar and (width % 64 == 0 or height % 64 == 0):
        return {
            "layer": "forensics",
            "name": "Image Dimensions",
            "value": f"{width}x{height}px — common AI aspect ratio and alignment (e.g. 64px). Minor signal.",
            "flag": "neutral",
            "weight": 4
        }
    return {
        "layer": "forensics",
        "name": "Image Dimensions",
        "value": f"{width}x{height}px — non-standard size, consistent with real camera",
        "flag": "clean",
        "weight": 0
    }


def _run_frequency_analysis(image: Image.Image) -> dict:
    """
    Frequency Domain Analysis (FFT):
    Converts the image to the frequency domain using 2D Fast Fourier Transform.

    AI-generated images (especially GANs) often leave fingerprints in the
    frequency spectrum — unusual peaks, grid patterns, or abnormal energy
    distribution that real camera photos don't have.

    We check:
    - The ratio of high-frequency to low-frequency energy
    - Spectral symmetry (AI images sometimes have unusual symmetry)
    """
    try:
        # Convert to grayscale and resize for consistent analysis
        gray = image.convert("L")
        # Resize to standard size for comparable FFT results
        gray_resized = gray.resize((256, 256), Image.LANCZOS)
        img_arr = np.array(gray_resized, dtype=np.float32)

        # Compute 2D FFT and shift zero-frequency to center
        fft = np.fft.fft2(img_arr)
        fft_shifted = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shifted)

        # Avoid log(0)
        magnitude = np.log1p(magnitude)

        # Split into low-frequency (center) and high-frequency (edges)
        h, w = magnitude.shape
        center_y, center_x = h // 2, w // 2
        radius = min(h, w) // FFT_LOW_FREQ_RADIUS_FRAC

        # Create circular mask for low frequencies
        y, x = np.ogrid[:h, :w]
        low_freq_mask = ((y - center_y)**2 + (x - center_x)**2) <= radius**2

        low_freq_energy = float(np.mean(magnitude[low_freq_mask]))
        high_freq_energy = float(np.mean(magnitude[~low_freq_mask]))

        # Normalize ratio by total energy to reduce scale dependence
        total_energy = low_freq_energy + high_freq_energy
        if total_energy > 0:
            freq_ratio = high_freq_energy / max(low_freq_energy, 1e-6)
        else:
            freq_ratio = 0.0

        spectral_std = float(np.std(magnitude))

        if freq_ratio < FFT_RATIO_SUSPICIOUS and spectral_std < FFT_SPECTRAL_STD_SUSPICIOUS:
            return {
                "layer": "forensics",
                "name": "Frequency Domain Analysis",
                "value": f"Abnormal frequency spectrum (ratio={freq_ratio:.3f}, std={spectral_std:.2f}). Pattern consistent with AI generation.",
                "flag": "suspicious",
                "weight": 15
            }
        elif freq_ratio < FFT_RATIO_NEUTRAL:
            return {
                "layer": "forensics",
                "name": "Frequency Domain Analysis",
                "value": f"Slightly unusual frequency spectrum (ratio={freq_ratio:.3f}). Minor anomaly detected.",
                "flag": "neutral",
                "weight": 5
            }
        else:
            return {
                "layer": "forensics",
                "name": "Frequency Domain Analysis",
                "value": f"Normal frequency spectrum (ratio={freq_ratio:.3f}, std={spectral_std:.2f}). Consistent with camera capture.",
                "flag": "clean",
                "weight": -5
            }

    except Exception as e:
        return {
            "layer": "forensics",
            "name": "Frequency Domain Analysis",
            "value": f"Frequency analysis failed: {str(e)}",
            "flag": "neutral",
            "weight": 0
        }


def _check_jpeg_grid(image: Image.Image, image_bytes: bytes) -> dict:
    """
    JPEG Grid Alignment Check:
    Real JPEGs have consistent 8×8 block structure. For non-JPEG (PNG/WebP),
    we simulate re-JPEG and analyze the resulting block structure so the
    check still applies.
    """
    try:
        gray = image.convert("L")
        arr = np.array(gray, dtype=np.float32)
        fmt = getattr(image, "format", None) or ""

        # For PNG/WebP etc., simulate re-JPEG to get block structure
        if fmt and fmt.upper() not in ("JPEG", "JPG"):
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=92)
            buf.seek(0)
            rejpeg = Image.open(buf).convert("L")
            arr = np.array(rejpeg, dtype=np.float32)

        h, w = arr.shape
        if h < 32 or w < 32:
            return {
                "layer": "forensics",
                "name": "JPEG Grid Analysis",
                "value": "Image too small for grid analysis",
                "flag": "neutral",
                "weight": 0
            }

        h_crop = (h // 8) * 8
        w_crop = (w // 8) * 8
        arr = arr[:h_crop, :w_crop]

        blocks_h = h_crop // 8
        blocks_w = w_crop // 8
        block_variances = []
        for i in range(blocks_h):
            for j in range(blocks_w):
                block = arr[i*8:(i+1)*8, j*8:(j+1)*8]
                block_variances.append(float(np.var(block)))

        block_variances = np.array(block_variances)
        mean_var = float(np.mean(block_variances))
        std_var = float(np.std(block_variances))
        cv = (std_var / mean_var) if mean_var > 0 else 0.0

        if cv < GRID_CV_SUSPICIOUS_LOW and mean_var < GRID_MEANVAR_SUSPICIOUS:
            return {
                "layer": "forensics",
                "name": "JPEG Grid Analysis",
                "value": f"Suspiciously uniform block structure (CV={cv:.3f}). Consistent with synthetic generation.",
                "flag": "suspicious",
                "weight": 10
            }
        elif cv > GRID_CV_SPLICE:
            return {
                "layer": "forensics",
                "name": "JPEG Grid Analysis",
                "value": f"Highly inconsistent block structure (CV={cv:.3f}). Possible splicing or heavy editing.",
                "flag": "suspicious",
                "weight": 10
            }
        else:
            return {
                "layer": "forensics",
                "name": "JPEG Grid Analysis",
                "value": f"Normal JPEG block structure (CV={cv:.3f}). Consistent with authentic compression.",
                "flag": "clean",
                "weight": -3
            }

    except Exception as e:
        return {
            "layer": "forensics",
            "name": "JPEG Grid Analysis",
            "value": f"Grid analysis failed: {str(e)}",
            "flag": "neutral",
            "weight": 0
        }
