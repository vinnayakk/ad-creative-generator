import csv
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

from ad_creative_generator.generate_copy import generate_copy
from ad_creative_generator.generate_ad_image_brand import generate_image
from ad_creative_generator.judge import judge_variant

load_dotenv()

SCORE_COLUMNS = ("tone_pass", "claims_pass", "cta_pass", "length_pass", "visual_fit_pass")


def run_pipeline(
    brief_path: str,
    count: int = 5,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
):
    """
    Run the full generate -> image -> judge pipeline for one brief.

    anthropic_api_key / openai_api_key: pass these to use a caller-supplied key
    (e.g. one a visitor pasted into a public demo). Leave them as None for local
    use — the Anthropic/OpenAI SDKs then fall back to the ANTHROPIC_API_KEY /
    OPENAI_API_KEY environment variables (from .env), exactly as before.
    """
    brief_path = Path(brief_path)
    with open(brief_path) as f:
        brief = json.load(f)

    product_image_path = brief_path.parent / brief["product"]["image_file"]

    brand_name = brief["brand"]["name"]
    safe_name = brand_name.lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # The timestamp alone isn't unique enough: two visitors hitting a public
    # demo for the same brand within the same second would otherwise get the
    # same output_dir and silently clobber each other's files.
    run_id = uuid.uuid4().hex[:8]

    output_dir = Path("outputs") / f"{safe_name}_{timestamp}_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    anthropic_client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else Anthropic()
    openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else OpenAI()

    variants = generate_copy(anthropic_client, brief, count=count)

    rows = []
    for variant in variants:
        print(f"Generating image for variant {variant.variant_number}...")
        image_path = generate_image(
            openai_client, brief, variant.model_dump(), product_image_path, output_dir
        )

        row = variant.model_dump()
        row["image_file"] = Path(image_path).name
        # judge_variant reads the image from disk itself, so it needs the full
        # path — image_file above is just the filename for the CSV/manifest.
        row["image_path"] = str(image_path)

        print(f"Judging variant {variant.variant_number}...")
        row = judge_variant(anthropic_client, brief, row, product_image_path)
        row["judge_score"] = sum(row[col] for col in SCORE_COLUMNS)
        del row["image_path"]  # was only needed to locate the file for judging

        rows.append(row)

    # Best variant first, so callers see the strongest option without having
    # to sort client-side.
    rows.sort(key=lambda r: r["judge_score"], reverse=True)

    csv_path = output_dir / "results.csv"
    fieldnames = [
        "variant_number", "headline", "body", "cta", "image_file",
        "judge_score", *SCORE_COLUMNS, "critique",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "brand": brand_name,
        "brief_file": str(brief_path),
        "generated_at": datetime.now().isoformat(),
        "variant_count": len(rows),
        "variants": rows,  # sorted best judge_score first
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Done. Saved {len(rows)} variants to {output_dir}/")
    return output_dir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m ad_creative_generator.pipeline <brief.json>")
        sys.exit(1)

    run_pipeline(sys.argv[1])