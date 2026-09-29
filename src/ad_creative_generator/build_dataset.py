import csv
import json
from pathlib import Path

from ad_creative_generator.pipeline import run_pipeline

PACKAGE_DIR = Path(__file__).parent

BRIEF_PATHS = [
    PACKAGE_DIR / "velara_headphones_brandbrief.json",
    PACKAGE_DIR / "verdan_hempseed_oil_brandbrief.json",
    PACKAGE_DIR / "riverbend_tide_and_treetop_brandbrief.json",
]

VARIANTS_PER_BRIEF = 2


def build_dataset():
    output_dirs = []
    for brief_path in BRIEF_PATHS:
        print(f"\n=== {brief_path} ===")
        output_dir = run_pipeline(brief_path, count=VARIANTS_PER_BRIEF)
        output_dirs.append(Path(output_dir))

    all_rows = []
    for output_dir in output_dirs:
        with open(output_dir / "manifest.json") as f:
            manifest = json.load(f)
        for row in manifest["variants"]:
            row = dict(row)
            row["brand"] = manifest["brand"]
            row["image_path"] = str(output_dir / row["image_file"])
            all_rows.append(row)

    dataset_path = Path("dataset") / "all_variants.csv"
    dataset_path.parent.mkdir(exist_ok=True)

    fieldnames = [
        "brand", "variant_number", "headline", "body", "cta", "image_path",
        "tone_pass", "claims_pass", "cta_pass", "length_pass", "visual_fit_pass",
        "critique",
    ]
    with open(dataset_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone. {len(all_rows)} variants across {len(BRIEF_PATHS)} brands -> {dataset_path}")


if __name__ == "__main__":
    build_dataset()