"""
Local dev:  streamlit run streamlit_app.py
Deployed (Hugging Face Spaces): same command — this app runs the pipeline
in-process, no separate API server. Visitors paste their own Anthropic +
OpenAI keys; nothing here reads a key from the environment or writes a key
to disk.
"""
import json
import sys
import tempfile
from pathlib import Path

import streamlit as st

# Makes `ad_creative_generator` importable whether this file runs from the
# repo root locally or from a Space deploy — both keep `src/` next to this
# file. See the deploy guide for the Space's file layout.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ad_creative_generator.pipeline import run_pipeline  # noqa: E402

st.set_page_config(page_title="Ad Creative Generator", page_icon="🎨")

st.title("Ad Creative Generator")
st.caption(
    "Generates on-brand ad copy + images from a product photo and a brand "
    "brief, then grades every variant against five brand-fit criteria."
)

with st.expander("About the API keys", expanded=False):
    st.markdown(
        "This demo doesn't use a shared key — **you bring your own**. Your "
        "keys are used only in memory for this one run, to call Anthropic "
        "and OpenAI directly on your behalf. They are never stored, logged, "
        "or written to disk, and this app has no database.\n\n"
        "As with pasting any API key into any web app, only use a key "
        "you're comfortable temporarily exposing to a server you don't "
        "control — if that doesn't sit right with you, clone the repo and "
        "run this locally instead, with the key in your own `.env`.\n\n"
        "- Get an Anthropic key at [console.anthropic.com](https://console.anthropic.com)\n"
        "- Get an OpenAI key at [platform.openai.com](https://platform.openai.com)"
    )

with st.form("generate_form"):
    anthropic_key = st.text_input(
        "Your Anthropic API key", type="password", placeholder="sk-ant-..."
    )
    openai_key = st.text_input(
        "Your OpenAI API key", type="password", placeholder="sk-..."
    )

    photo = st.file_uploader("Product photo", type=["png", "jpg", "jpeg"])
    brief_text = st.text_area(
        "Brand brief (paste JSON)", height=240, placeholder='{"brand": {...}, ...}'
    )
    count = st.slider("Number of variants", min_value=1, max_value=10, value=3)
    st.caption(
        "Each variant makes several Anthropic calls plus one OpenAI image "
        "call — cost scales with this number, on your own key."
    )

    submitted = st.form_submit_button("Generate")

if submitted:
    errors = []
    if not anthropic_key.strip():
        errors.append("Anthropic API key is required.")
    if not openai_key.strip():
        errors.append("OpenAI API key is required.")
    if not photo:
        errors.append("Please upload a product photo.")

    brief = None
    if not brief_text.strip():
        errors.append("Please paste a brand brief.")
    else:
        try:
            brief = json.loads(brief_text)
        except json.JSONDecodeError as e:
            errors.append(f"Brief isn't valid JSON: {e}")

    if errors:
        for e in errors:
            st.error(e)
    else:
        with tempfile.TemporaryDirectory(prefix="ad_creative_ui_") as tmp_dir:
            tmp_dir = Path(tmp_dir)

            image_filename = photo.name
            (tmp_dir / image_filename).write_bytes(photo.getvalue())

            brief["product"]["image_file"] = image_filename
            brief_path = tmp_dir / "brief.json"
            brief_path.write_text(json.dumps(brief))

            with st.spinner(f"Generating {count} variant(s) — this can take a few minutes..."):
                try:
                    output_dir = run_pipeline(
                        str(brief_path),
                        count=count,
                        anthropic_api_key=anthropic_key.strip(),
                        openai_api_key=openai_key.strip(),
                    )
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.stop()

            with open(Path(output_dir) / "manifest.json") as f:
                manifest = json.load(f)

        st.success(f"Generated {manifest['variant_count']} variant(s), best first.")

        criteria = ["tone", "claims", "cta", "length", "visual_fit"]
        for i, variant in enumerate(manifest["variants"]):
            with st.expander(
                f"Variant {variant['variant_number']} — "
                f"score {variant['judge_score']}/5 — {variant['headline']}",
                expanded=(i == 0),
            ):
                image_path = Path(output_dir) / variant["image_file"]
                if image_path.exists():
                    st.image(str(image_path))
                st.write(f"**Body:** {variant['body']}")
                st.write(f"**CTA:** {variant['cta']}")

                cols = st.columns(len(criteria))
                for col, criterion in zip(cols, criteria):
                    passed = variant[f"{criterion}_pass"]
                    col.write(f"{'✅' if passed else '❌'} {criterion.replace('_', ' ').title()}")

                if variant["critique"]:
                    st.caption(variant["critique"])