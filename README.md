# Image Provenance Inspector

Image Provenance Inspector is an open-source tool for inspecting image metadata, C2PA Content Credentials, and editing provenance. It turns the evidence available inside an image into a small, human-readable report that can distinguish camera-origin evidence, traditional editing, AI-assisted editing, and AI-generation signals.

It is designed to answer:

> What AI-related or editing information did this image actually retain?

It is not an AI detector and it does not try to defeat platform labels. A missing manifest or metadata field is not proof that an image is original.

## What it checks

- EXIF, XMP, and IPTC presence
- Camera model, capture time, and editing software when available
- C2PA Content Credentials, claim generator, validation state, and actions
- SHA-256, dimensions, format, and file size
- Optional original-versus-edited comparison using SSIM, perceptual hash, and a difference mask

The rule-based assessment uses five intentionally conservative categories:

| Category | Meaning |
| --- | --- |
| `CAMERA_ORIGINAL` | Camera-origin metadata is present and no editing evidence was found. |
| `TRADITIONAL_EDIT` | Camera-origin metadata and conventional editing provenance were found. |
| `AI_ASSISTED_EDIT` | Camera-origin evidence and AI/generative editing evidence were found. |
| `AI_GENERATED` | AI-generation evidence was found without camera-origin evidence. |
| `UNKNOWN` | Available metadata does not support a stronger conclusion. |

These categories describe evidence, not certainty. Provenance can be stripped, lost during export, or incomplete.

## Quick start

The project targets Python 3.12 and uses `uv` for reproducible environments.

```bash
uv sync --extra dev --extra c2pa --extra ui
uv run uvicorn app.main:app --reload
```

For the optional native acceleration used by larger comparison workloads, add
the `analysis` extra. The API also has a Pillow/standard-library fallback:

```bash
uv sync --extra dev --extra c2pa --extra ui --extra analysis
```

The API is available at <http://127.0.0.1:8000>. Interactive OpenAPI documentation is at <http://127.0.0.1:8000/docs>.

For the Streamlit interface, start the API dependencies in the same environment and run:

```bash
uv run streamlit run ui/streamlit_app.py
```

ExifTool is used when installed for broader metadata coverage. Pillow is the built-in fallback, so local development and tests do not require the system executable. On Debian/Ubuntu:

```bash
sudo apt-get install libimage-exiftool-perl
```

## API

### Analyze one image

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -F "image=@photo.jpg"
```

The response is a fixed Pydantic-validated JSON contract:

```json
{
  "file": {
    "format": "JPEG",
    "width": 4032,
    "height": 3024,
    "size_bytes": 1842930,
    "sha256": "..."
  },
  "capture": {
    "camera": "Apple iPhone",
    "captured_at": "2026-08-20T15:32:11"
  },
  "metadata": {
    "exif": true,
    "xmp": true,
    "iptc": false,
    "software": "Adobe Photoshop"
  },
  "c2pa": {
    "present": true,
    "valid": true,
    "claim_generator": "Adobe Photoshop",
    "generative_edit": true
  },
  "assessment": {
    "type": "AI_ASSISTED_EDIT",
    "confidence": "high",
    "reason": [
      "Camera capture metadata detected",
      "C2PA provenance detected",
      "Generative editing action detected"
    ]
  }
}
```

`c2pa.valid` is `null` when no validation state is available. The API does not convert absent evidence into a positive or negative origin claim.

### Compare an original and edited image

```bash
curl -X POST http://127.0.0.1:8000/api/v1/compare \
  -F "original=@original.jpg" \
  -F "edited=@edited.jpg"
```

The response includes `ssim` (0–1), `phash_distance`, `changed_area_ratio` (0–1), and a base64-encoded PNG difference mask.

All validation and expected upload errors use the same Pydantic `ErrorResponse` shape:

```json
{
  "code": "invalid_image",
  "message": "The uploaded file is not a supported image.",
  "details": []
}
```

The default upload limit is 20 MiB. Set `IPI_MAX_UPLOAD_BYTES` to change it for a deployment.

## Docker

Build and run the API container:

```bash
docker build -t image-provenance-inspector .
docker run --rm -p 8000:8000 image-provenance-inspector
```

The image includes ExifTool and the API runtime. It does not store uploaded images after a request completes.

## Development

Install development and UI dependencies, then run the checks locally:

```bash
uv sync --extra dev --extra c2pa --extra ui --extra analysis
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=app --cov-report=term-missing
```

The GitHub Actions workflow runs the same lint, formatting, and test gates on Python 3.12. `uv.lock` is committed so CI and deployments resolve the same dependency graph.

The project also exposes a CLI using the same service and Pydantic result model:

```bash
uv run image-provenance-inspector photo.jpg
```

## Project layout

```text
app/
├── api/             API route helpers
├── analyzers/       image, metadata, C2PA, and comparison readers
├── models/          public Pydantic schemas
├── provenance/      explainable classification rules
├── cli.py           command-line entry point
├── main.py          FastAPI application
└── service.py       shared analysis orchestration
tests/               unit and API contract tests
ui/                  Streamlit interface
```

## Scope and limitations

This project inspects, validates, explains, and compares evidence. It deliberately does not:

- remove C2PA credentials or invisible watermarks;
- bypass Facebook, Instagram, or other platform detection;
- guarantee that an image is AI-generated or camera-original;
- infer provenance from pixels alone.

Uploaded content may contain sensitive metadata such as GPS coordinates. Run the service locally or review and sanitize metadata before sending images to a hosted deployment.

## License

Released under the MIT License. See [LICENSE](LICENSE).
