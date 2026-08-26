# Changelog

## 0.2.0 - Privacy-safe sanitization

- Add `POST /api/v1/sanitize` for selected privacy EXIF cleanup.
- Add the CLI `sanitize` command and a Streamlit privacy-sanitization tab.
- Preserve XMP, IPTC, software metadata, and C2PA provenance blocks.
- Leave C2PA-bearing files byte-for-byte unchanged and report why.
- Add before/after pixel comparison and a structured sanitization report.
