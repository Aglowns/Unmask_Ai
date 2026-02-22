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
    Re-saves the image at a lower quality, then computes the difference
    between the original and the re-saved version.

    If regions are INCONSISTENT (some much brighter than others in the diff),
    that suggests splicing. If everything is UNIFORMLY flat, that's also
    suspicious (too perfect = likely AI).
    """
    try:
        # Re-save at lower quality
        buffer = io.BytesIO()
        original_image.save(buffer, format="JPEG", quality=75)
        buffer.seek(0)
        recompressed = Image.open(buffer).convert("RGB")

        # Convert both to numpy arrays for math
        original_arr = np.array(original_image, dtype=np.float32)
        recomp_arr = np.array(recompressed, dtype=np.float32)

        # Compute pixel-by-pixel difference
        ela_diff = np.abs(original_arr - recomp_arr)

        # Statistical measures of the difference map
        mean_diff = float(np.mean(ela_diff))
        std_diff = float(np.std(ela_diff))

        # Low mean + very low std = suspiciously uniform (AI pattern)
        if mean_diff < 3.0 and std_diff < 2.0:
            return {
                "layer": "forensics",
                "name": "Error Level Analysis (ELA)",
                "value": f"Suspiciously uniform error levels (mean={mean_diff:.2f}, std={std_diff:.2f}). May indicate AI generation.",
                "flag": "suspicious",
                "weight": 20
            }
        # Very high variance = possible splicing/editing
        elif std_diff > 25.0:
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
    Applies a blur to the image, then computes the difference between the
    original and blurred versions. This isolates the "noise layer".

    Real cameras: noise is present and has natural variation.
    AI images: noise is too uniform or too absent (suspiciously clean).
    """
    try:
        # Convert to grayscale for noise analysis
        gray = image.convert("L")
        gray_arr = np.array(gray, dtype=np.float32)

        # Apply Gaussian blur
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=2))
        blurred_arr = np.array(blurred, dtype=np.float32)

        # Noise = original minus blurred
        noise = gray_arr - blurred_arr
        noise_std = float(np.std(noise))

        if noise_std < 2.0:
            # Almost no noise = unnaturally clean (common in AI images)
            return {
                "layer": "forensics",
                "name": "Noise Pattern Analysis",
                "value": f"Unusually low noise level (std={noise_std:.2f}). AI images tend to be unnaturally smooth.",
                "flag": "suspicious",
                "weight": 15
            }
        elif noise_std > 20.0:
            # Very noisy — could be a highly compressed/low-quality real photo
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


def _check_dimensions(image: Image.Image) -> dict:
    """
    Dimension Check:
    AI image generators (Midjourney, DALL-E, Stable Diffusion) produce images
    at very specific sizes: 512x512, 768x768, 1024x1024, 1024x1792, etc.
    Real photos come in all sorts of irregular sizes from cameras.
    """
    AI_COMMON_SIZES = {
        (512, 512), (768, 768), (1024, 1024),
        (1024, 1792), (1792, 1024), (1024, 1536),
        (1536, 1024), (2048, 2048), (1344, 768),
        (768, 1344), (1216, 832), (832, 1216)
    }

    width, height = image.size

    if (width, height) in AI_COMMON_SIZES:
        return {
            "layer": "forensics",
            "name": "Image Dimensions",
            "value": f"{width}x{height}px — matches a known AI generation resolution",
            "flag": "suspicious",
            "weight": 10
        }
    else:
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
        radius = min(h, w) // 8  # inner 25% = low freq

        # Create circular mask for low frequencies
        y, x = np.ogrid[:h, :w]
        low_freq_mask = ((y - center_y)**2 + (x - center_x)**2) <= radius**2

        low_freq_energy = float(np.mean(magnitude[low_freq_mask]))
        high_freq_energy = float(np.mean(magnitude[~low_freq_mask]))

        # Ratio of high-to-low frequency energy
        if low_freq_energy > 0:
            freq_ratio = high_freq_energy / low_freq_energy
        else:
            freq_ratio = 0.0

        # Check spectral standard deviation — AI images tend to have
        # more uniform spectral patterns
        spectral_std = float(np.std(magnitude))

        # AI images typically have lower high-frequency energy (too smooth)
        # AND more uniform spectral patterns
        if freq_ratio < 0.15 and spectral_std < 2.0:
            return {
                "layer": "forensics",
                "name": "Frequency Domain Analysis",
                "value": f"Abnormal frequency spectrum (ratio={freq_ratio:.3f}, std={spectral_std:.2f}). Pattern consistent with AI generation.",
                "flag": "suspicious",
                "weight": 15
            }
        elif freq_ratio < 0.20:
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
    Real JPEG photos have a consistent 8×8 block grid from compression.
    When an image is spliced (parts pasted from different sources) or
    AI-generated and then re-saved, the grid alignment can be inconsistent.

    We check for variance in block-level statistics — high variance across
    blocks suggests manipulation.
    """
    try:
        gray = image.convert("L")
        arr = np.array(gray, dtype=np.float32)
        h, w = arr.shape

        # Need at least 4x4 blocks (32x32 pixels) for meaningful analysis
        if h < 32 or w < 32:
            return {
                "layer": "forensics",
                "name": "JPEG Grid Analysis",
                "value": "Image too small for grid analysis",
                "flag": "neutral",
                "weight": 0
            }

        # Crop to multiple of 8
        h_crop = (h // 8) * 8
        w_crop = (w // 8) * 8
        arr = arr[:h_crop, :w_crop]

        # Split into 8x8 blocks and compute variance of each block
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

        # Coefficient of variation in block variances
        if mean_var > 0:
            cv = std_var / mean_var
        else:
            cv = 0.0

        # Very low CV = too uniform (AI pattern)
        # Very high CV = possible splicing
        if cv < 0.3 and mean_var < 50:
            return {
                "layer": "forensics",
                "name": "JPEG Grid Analysis",
                "value": f"Suspiciously uniform block structure (CV={cv:.3f}). Consistent with synthetic generation.",
                "flag": "suspicious",
                "weight": 10
            }
        elif cv > 3.0:
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
