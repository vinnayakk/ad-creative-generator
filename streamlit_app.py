"""
Local prototype UI for the ad creative generator.

This is a prototype, not a public tool: it only ever talks to a FastAPI
server running on YOUR OWN machine, using YOUR OWN .env key.

Run the backend first, in one terminal:
    uvicorn ad_creative_generator.main:app --reload

Then, in another terminal:
    streamlit run streamlit_app.py
"""
import json
import tempfile
from pathlib import Path

import requests
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Ad Creative Generator", layout="wide")
st.title("Ad Creative Generator — prototype")
st.caption(
    f"Talks only to your own local API at {API_URL}. Nothing here is public."
)

with st.form("generate_form"):
    photo = st.file_uploader("Product photo", type=["png", "jpg", "jpeg"])
    brief_text = st.text_area(
        "Brand brief (paste the full JSON)",
        height=300,
        placeholder='{"brand": {...}, "product": {...}, "tone": {...}, "offer": {...}}',
    )
    count = st.slider(
        "Variants to generate",
        min_value=1,
        max_value=10,
        value=3,
        help=(
            "Each variant is one copy call, one image call, and five judge "
            "calls -- all real, paid model calls. Start low."
        ),
    )
    submitted = st.form_submit_button("Generate")

if submitted:
    if not photo:
        st.error("Upload a product photo first.")
        st.stop()
    if not brief_text.strip():
        st.error("Paste a brand brief first.")
        st.stop()

    try:
        brief = json.loads(brief_text)
    except json.JSONDecodeError as e:
        st.error(f"That brief isn't valid JSON: {e}")
        st.stop()

    try:
        image_filename = brief["product"]["image_file"]
    except KeyError:
        st.error(
            'The brief is missing brief["product"]["image_file"] -- the '
            "pipeline needs this to know what to name the uploaded photo."
        )
        st.stop()

    # The pipeline expects the brief JSON and its product photo to sit in
    # the same folder, with the photo named exactly what the brief says
    # (product.image_file). Recreate that layout in a fresh temp dir per
    # request so nothing collides across runs.
    work_dir = Path(tempfile.mkdtemp(prefix="ad_creative_ui_"))
    (work_dir / image_filename).write_bytes(photo.getvalue())
    brief_path = work_dir / "brief.json"
    brief_path.write_text(json.dumps(brief))

    with st.spinner(f"Generating and judging {count} variant(s) — real, paid model calls..."):
        try:
            response = requests.post(
                f"{API_URL}/generate",
                json={"brief_path": str(brief_path), "count": count},
                timeout=600,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            st.error(
                f"Couldn't reach {API_URL}. Is the backend running? Start it with:\n\n"
                "`uvicorn ad_creative_generator.main:app --reload`"
            )
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"The API returned an error: {e}\n\n{response.text}")
            st.stop()

    result = response.json()
    st.success(
        f"Done — {result['variant_count']} variants generated. "
        f'Best: "{result["best_variant_headline"]}" '
        f'(judge score {result["best_judge_score"]}/5).'
    )

    # /generate only returns the winner; the full sorted list lives in
    # manifest.json on disk. This UI and the API run on the same machine in
    # this prototype, so we can just read it back.
    manifest_path = Path(result["output_dir"]) / "manifest.json"
    if not manifest_path.exists():
        st.warning(
            f"Results were saved to {result['output_dir']}, but I couldn't "
            "find manifest.json there to show a preview."
        )
        st.stop()

    with open(manifest_path) as f:
        manifest = json.load(f)

    st.subheader("All variants, best judge score first")
    criteria = ["tone_pass", "claims_pass", "cta_pass", "length_pass", "visual_fit_pass"]

    for variant in manifest["variants"]:
        score = variant.get("judge_score", "?")
        with st.expander(f"{variant['headline']} — score {score}/5", expanded=(score == 5)):
            image_col, text_col = st.columns([1, 2])

            image_path = Path(result["output_dir"]) / variant["image_file"]
            if image_path.exists():
                image_col.image(str(image_path))

            with text_col:
                st.write(f"**Body:** {variant['body']}")
                st.write(f"**CTA:** {variant['cta']}")
                for key in criteria:
                    icon = "✅" if variant.get(key) else "❌"
                    label = key.replace("_pass", "").replace("_", " ").title()
                    st.write(f"{icon} {label}")
                if variant.get("critique"):
                    st.caption(variant["critique"])