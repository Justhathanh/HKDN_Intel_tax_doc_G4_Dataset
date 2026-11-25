from PIL import Image

from dataset_generator.ocr.preprocessing import preprocess_image


def test_preprocessing_converts_to_grayscale_and_upscales():
    image = Image.new("RGB", (600, 800), color="white")
    result = preprocess_image(image, min_width=1200)
    assert result.mode == "L"
    assert result.width == 1200
    assert result.height == 1600
