from __future__ import annotations

from io import BytesIO

from PIL import ExifTags, Image

from app.analyzers.metadata import extract_metadata


def test_pillow_fallback_reads_camera_and_capture_time(monkeypatch) -> None:
    monkeypatch.setattr("app.analyzers.metadata.shutil.which", lambda _: None)
    image = Image.new("RGB", (12, 12), "white")
    exif = image.getexif()
    make_tag = next(tag for tag, name in ExifTags.TAGS.items() if name == "Make")
    model_tag = next(tag for tag, name in ExifTags.TAGS.items() if name == "Model")
    capture_tag = next(tag for tag, name in ExifTags.TAGS.items() if name == "DateTimeOriginal")
    exif[make_tag] = "ExampleCam"
    exif[model_tag] = "Model 1"
    exif[capture_tag] = "2026:08:20 15:32:11"
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())

    metadata = extract_metadata(buffer.getvalue())

    assert metadata.exif is True
    assert metadata.camera == "ExampleCam Model 1"
    assert metadata.captured_at is not None
    assert metadata.captured_at.year == 2026
