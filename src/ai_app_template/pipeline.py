import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from ai_app_template.generate_copy import generate_copy
from ai_app_template.generate_ad_image_brand import generate_image

load_dotenv()


def run_pipeline(brief_path: str, count: int = 5):
    with open(brief_path) as f:
        brief = json.load(f)

    brand_name = brief["brand"]["name"]
    safe_name = brand_name.lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = Path("outputs") / f"{safe_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = generate_copy(brief, count=count)

    rows = []
    for variant in variants:
        print(f"Generating image for variant {variant.variant_number}...")
        image_path = generate_image(brief, variant.model_dump())

        destination = output_dir / Path(image_path).name
        shutil.move(image_path, destination)

        row = variant.model_dump()
        row["image_file"] = destination.name
        rows.append(row)

    csv_path = output_dir / "results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["variant_number", "headline", "body", "cta", "image_file"]
        )
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "brand": brand_name,
        "brief_file": brief_path,
        "generated_at": datetime.now().isoformat(),
        "variant_count": len(rows),
        "variants": rows,
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Done. Saved {len(rows)} variants to {output_dir}/")
    return output_dir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m ai_app_template.pipeline <brief.json>")
        sys.exit(1)

    run_pipeline(sys.argv[1])