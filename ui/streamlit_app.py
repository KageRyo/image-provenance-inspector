"""Minimal Streamlit UI for human-readable analysis."""

from __future__ import annotations

import streamlit as st

from app.service import AnalysisService

st.set_page_config(page_title="Image Provenance Inspector", page_icon="🔎")
st.title("Image Provenance Inspector")
st.caption("Inspect metadata, Content Credentials, and editing provenance.")

uploaded = st.file_uploader(
    "Upload an image",
    type=["jpg", "jpeg", "png", "webp", "tif", "tiff"],
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

st.divider()
st.caption(
    "This tool explains available provenance evidence; it does not guarantee origin "
    "or bypass platform detection."
)
