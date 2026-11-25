
"""Image preprocessing and deskew helpers used before OCR."""

import cv2
import numpy as np

from PIL import Image, ImageFilter, ImageOps


def estimate_skew_angle(
    image: Image.Image,
    *,
    max_angle: float = 8.0,
    coarse_step: float = 0.2,
    fine_step: float = 0.05,
) -> float:
    """Estimate document skew angle using horizontal projection profiles."""

    gray = np.array(ImageOps.grayscale(image))

    height, width = gray.shape

    # Reduce image size to speed up angle estimation.
    scale = min(1.0, 1200 / max(height, width))
    if scale < 1.0:
        gray = cv2.resize(
            gray,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA,
        )

    height, width = gray.shape

    # Ignore outer margins to reduce border interference.
    margin_y = int(height * 0.03)
    margin_x = int(width * 0.03)

    gray = gray[
        margin_y:height - margin_y,
        margin_x:width - margin_x,
    ]

    if gray.size == 0:
        return 0.0

    _, binary = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    foreground_ratio = np.count_nonzero(binary) / binary.size

    if foreground_ratio < 0.0005 or foreground_ratio > 0.5:
        return 0.0

    def projection_score(angle: float) -> float:
        h, w = binary.shape

        matrix = cv2.getRotationMatrix2D(
            (w / 2, h / 2),
            angle,
            1.0,
        )

        rotated = cv2.warpAffine(
            binary,
            matrix,
            (w, h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        projection = np.sum(rotated, axis=1)
        return float(np.var(projection))

    # Coarse search.
    coarse_angles = np.arange(
        -max_angle,
        max_angle + coarse_step,
        coarse_step,
    )

    coarse_scores = [
        projection_score(float(angle))
        for angle in coarse_angles
    ]

    best_angle = float(coarse_angles[int(np.argmax(coarse_scores))])

    # Fine search around the best coarse angle.
    fine_angles = np.arange(
        best_angle - coarse_step,
        best_angle + coarse_step + fine_step,
        fine_step,
    )

    fine_scores = [
        projection_score(float(angle))
        for angle in fine_angles
    ]

    best_angle = float(fine_angles[int(np.argmax(fine_scores))])

    if abs(best_angle) < 0.5:
        return 0.0

    return best_angle


def deskew_image(
    image: Image.Image,
    *,
    max_angle: float = 8.0,
) -> tuple[Image.Image, float]:
    """Rotate a skewed document image to correct its alignment."""

    angle = estimate_skew_angle(
        image,
        max_angle=max_angle,
    )

    if angle == 0.0:
        return image, angle

    corrected = image.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor="white",
    )

    return corrected, angle


def preprocess_image(
    image: Image.Image,
    *,
    min_width: int = 1800,
) -> Image.Image:
    """Prepare a document image without destructive binarization."""

    prepared = ImageOps.grayscale(image)
    prepared = ImageOps.autocontrast(prepared, cutoff=1)

    if prepared.width < min_width:
        scale = min_width / prepared.width
        prepared = prepared.resize(
            (
                min_width,
                max(1, round(prepared.height * scale)),
            ),
            Image.Resampling.LANCZOS,
        )

    return prepared.filter(
        ImageFilter.UnsharpMask(
            radius=1.2,
            percent=130,
            threshold=3,
        )
    )
