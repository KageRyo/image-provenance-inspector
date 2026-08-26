"""Minimal Streamlit UI for human-readable analysis."""

from __future__ import annotations

import streamlit as st

from app.analyzers.sanitizer import sanitize_image
from app.models.result import SanitizationGroup
from app.service import AnalysisService

st.set_page_config(page_title="Image Provenance Inspector", page_icon="🔎")
st.title("Image Provenance Inspector")
st.caption("Inspect metadata, Content Credentials, and editing provenance.")

analyze_tab, sanitize_tab = st.tabs(["Analyze", "Privacy sanitize"])

with analyze_tab:
    uploaded = st.file_uploader(
        "Upload an image",
        type=["jpg", "jpeg", "png", "webp", "tif", "tiff"],
        key="analyze-upload",
    )
    if uploaded is not None and st.button("Analyze", type="primary"):
        try:
            result = AnalysisService().analyze(uploaded.getvalue())
        except Exception as exc:  # Streamlit should show a useful message rather than a traceback.
            st.error(str(exc))
        else:
            st.subheader("Provenance assessment")
            for label, evidence in (
                ("Origin", result.assessment.origin),
                ("Editing", result.assessment.editing),
            ):
                st.markdown(f"**{label}:** {evidence.type.value.replace('_', ' ').title()}")
                st.write(f"Confidence: **{evidence.confidence.value}**")
                st.write("; ".join(evidence.reason))
            st.json(result.model_dump(mode="json"))

with sanitize_tab:
    st.caption(
        "Removes selected privacy EXIF fields. C2PA, XMP, IPTC, software fields, "
        "and other provenance signals are preserved."
    )
    sanitize_upload = st.file_uploader(
        "Upload a JPEG, PNG, or WebP image",
        type=["jpg", "jpeg", "png", "webp"],
        key="sanitize-upload",
    )
    selected_groups = st.multiselect(
        "Privacy groups to remove",
        options=list(SanitizationGroup),
        default=list(SanitizationGroup),
        format_func=lambda group: group.value.replace("-", " ").title(),
    )
    if sanitize_upload is not None and st.button("Create privacy-sanitized copy"):
        try:
            output_data, report = sanitize_image(sanitize_upload.getvalue(), selected_groups)
        except Exception as exc:  # Streamlit should show a useful message rather than a traceback.
            st.error(str(exc))
        else:
            st.json(report.model_dump(mode="json"))
            name_parts = sanitize_upload.name.rsplit(".", 1)
            output_name = (
                f"{name_parts[0]}.sanitized.{name_parts[1]}"
                if len(name_parts) == 2
                else f"{sanitize_upload.name}.sanitized"
            )
            st.download_button(
                "Download sanitized copy",
                data=output_data,
                file_name=output_name,
                mime=sanitize_upload.type or "application/octet-stream",
            )

st.divider()
st.caption(
    "This tool explains available provenance evidence; it does not guarantee origin "
    "or bypass platform detection."
)
