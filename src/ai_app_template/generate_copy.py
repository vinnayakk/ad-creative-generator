import csv
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic
from pydantic import BaseModel

load_dotenv()


class CopyVariant(BaseModel):
    variant_number: int
    headline: str
    body: str
    cta: str


class CopyVariants(BaseModel):
    variants: list[CopyVariant]


def build_prompt(brief: dict, count: int) -> str:
    brand = brief["brand"]
    tone = brief["tone"]
    offer = brief["offer"]

    return f"""Using this brand brief, write {count} distinct ad copy variants.

Brand: {brand['name']}
Positioning: {brand['positioning_statement']}
Personality: {', '.join(brand['personality'])}

Voice: {', '.join(tone['voice_words'])}
We are: {', '.join(tone['we_are'])}
We are not: {', '.join(tone['we_are_not'])}
Use words like: {', '.join(tone['vocabulary']['use'])}
Avoid words like: {', '.join(tone['vocabulary']['avoid'])}

Offer: {offer['core_offer']}
Call to action: {offer['call_to_action']}

Each variant needs a short headline, a 1-2 sentence body, and a CTA line.
Vary the angle across variants (benefit-led, curiosity-led, proof-led, urgency-led, etc).
Number them 1 through {count} in order."""


def generate_copy(brief: dict, count: int = 20) -> list[CopyVariant]:
    client = Anthropic()

    response = client.messages.parse(
        model="claude-sonnet-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": build_prompt(brief, count)}],
        output_format=CopyVariants,
    )

    variants = response.parsed_output.variants
    if len(variants) != count:
        print(f"Warning: expected {count} variants, got {len(variants)}")

    return variants


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_copy.py <brief.json>")
        sys.exit(1)

    brief_path = sys.argv[1]
    with open(brief_path) as f:
        brief = json.load(f)

    variants = generate_copy(brief, count=20)

    output_path = Path(brief_path).stem + "_copy_variants.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["variant_number", "headline", "body", "cta"])
        writer.writeheader()
        for v in variants:
            writer.writerow(v.model_dump())

    print(f"Wrote {len(variants)} variants to {output_path}")


if __name__ == "__main__":
    main()