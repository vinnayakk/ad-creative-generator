import base64
import csv
import json
import re
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BRIEF_PATHS = [
    DATA_DIR / "velara_headphones_brandbrief.json",
    DATA_DIR / "verdan_hempseed_oil_brandbrief.json",
    DATA_DIR / "riverbend_tide_and_treetop_brandbrief.json",
]


class CriterionResult(BaseModel):
    passed: bool
    critique: str = Field(
        description=(
            "If passed is false: exactly one sentence explaining what's wrong, specific "
            "enough that someone who has never seen the variant could fix it. If passed "
            "is true: leave this as an empty string — do not explain why it passed."
        )
    )


def load_briefs() -> dict[str, dict]:
    briefs = {}
    for path in BRIEF_PATHS:
        with open(path) as f:
            brief = json.load(f)
        briefs[brief["brand"]["name"]] = brief
    return briefs


# ---------- Shared judge-call helper ----------

def _judge_call(client: Anthropic, system: str, content, max_tokens: int = 2048) -> CriterionResult:
    try:
        response = client.messages.parse(
            model="claude-sonnet-5",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=CriterionResult,
        )
    except ValidationError as e:
        raise RuntimeError(
            f"Judge call returned incomplete structured output — max_tokens "
            f"({max_tokens}) was likely too low and the JSON got cut off mid-string. "
            f"Raise max_tokens and retry."
        ) from e

    if response.parsed_output is None:
        raise RuntimeError(
            f"Judge call completed but returned no structured output "
            f"(stop_reason={response.stop_reason!r})."
        )
    return response.parsed_output


# ---------- Criterion 4: Length — code only, no model call ----------

def grade_length(headline: str, body: str, cta: str) -> CriterionResult:
    problems = []

    hl_words = len(headline.split())
    if not headline.strip():
        problems.append("headline is empty")
    elif hl_words > 12:
        problems.append(f"headline is {hl_words} words (bound: 12)")

    body_words = len(body.split())
    body_sentences = len([s for s in re.split(r"[.!?]+", body) if s.strip()])
    if not body.strip():
        problems.append("body is empty")
    else:
        if body_sentences > 2:
            problems.append(f"body is {body_sentences} sentences (bound: 2)")
        if body_words > 40:
            problems.append(f"body is {body_words} words (bound: ~40)")

    cta_words = len(cta.split())
    if not cta.strip():
        problems.append("cta is empty")
    elif cta_words > 6:
        problems.append(f"cta is {cta_words} words (bound: 6)")

    if problems:
        return CriterionResult(passed=False, critique="; ".join(problems) + ".")
    return CriterionResult(passed=True, critique="")


# ---------- Criterion 2: Claims — code first, LLM only if code is clean ----------

def _clean_avoid_terms(avoid_terms: list[str]) -> list[str]:
    # strip annotations like "(unverified)" / "(overused)" — those are notes to
    # you in the brief, not part of the string to match against.
    return [re.sub(r"\s*\([^)]*\)\s*$", "", t).strip().lower() for t in avoid_terms]


def grade_claims_code(headline: str, body: str, cta: str, avoid_terms: list[str]) -> list[str]:
    text = f"{headline} {body} {cta}".lower()
    return [term for term in _clean_avoid_terms(avoid_terms) if term in text]


CLAIMS_JUDGE_SYSTEM = """You are grading ad copy against a brand's claims rules. You are \
looking for two things a plain string match cannot catch:
1. A synonym or rephrasing of a forbidden word or idea from the brand's "avoid" vocabulary \
or "we are not" list, even when the literal word isn't present.
2. A number, statistic, or capability claim that is invented or inflated beyond what the \
brief's proof points actually support.
Pass unless you find one of these. Be specific in your critique: name the exact phrase and \
what it implies that the brief doesn't support."""


def grade_claims_llm(client: Anthropic, brief: dict, headline: str, body: str, cta: str) -> CriterionResult:
    tone, product = brief["tone"], brief["product"]
    prompt = f"""Brand: {brief['brand']['name']}

We are not: {', '.join(tone['we_are_not'])}
Avoid vocabulary: {', '.join(tone['vocabulary']['avoid'])}
Proof points (the only numbers/claims this copy may rely on): {product['proof_points']}

Ad copy to grade:
Headline: {headline}
Body: {body}
CTA: {cta}"""

    return _judge_call(client, CLAIMS_JUDGE_SYSTEM, prompt)


# ---------- Criterion 1: Tone — LLM judge, few-shot from docs/rubric.md itself ----------

TONE_FEWSHOT = """Worked example, using a different brand (Riverbend, an outdoor IPA) so you \
calibrate on the pattern, not this specific brand:

PASS — Headline: "Bright hops, built for the trail." Body: "Tide & Treetop is a clean, crisp \
IPA that travels as easily as you do — from the dock to the campsite." Why: matches the \
brand's voice words and "we are" list, no cliche from "we are not".

FAIL — Headline: "The most extreme hoppy bomb you'll ever crush on the trail, guaranteed." \
Body: "Hand-crafted with passion by real brewers who love what they do, this beer is \
basically a lifestyle." Why: "basically a lifestyle" reads as staged-lifestyle marketing, \
which that brand's "we are not" list explicitly rules out — apply the same standard using \
whichever brand you're actually grading below."""

TONE_JUDGE_SYSTEM = f"""You are grading ad copy for brand tone/voice fit. Pass only if the \
copy reads like it was written by someone who deeply internalized this brand's voice — not \
generic ad-speak that could belong to any brand in the category.

{TONE_FEWSHOT}"""


def grade_tone_llm(client: Anthropic, brief: dict, headline: str, body: str) -> CriterionResult:
    tone = brief["tone"]
    prompt = f"""Brand: {brief['brand']['name']}
Positioning: {brief['brand']['positioning_statement']}

Voice words: {', '.join(tone['voice_words'])}
We are: {', '.join(tone['we_are'])}
We are not: {', '.join(tone['we_are_not'])}
Use vocabulary like: {', '.join(tone['vocabulary']['use'])}
Example of the right register: "{tone['example_line']}"
Should read like it could sit next to: {', '.join(tone['reference_brands'])}

Ad copy to grade:
Headline: {headline}
Body: {body}"""

    return _judge_call(client, TONE_JUDGE_SYSTEM, prompt)


# ---------- Criterion 3: Call to action — does it contradict the offer? ----------

CTA_JUDGE_SYSTEM = """You are grading whether an ad's CTA line is consistent with the \
brand's actual offer. Pass unless the CTA invents an offer detail (a discount, bonus, or \
guarantee) the brief doesn't state, or is so hedgy/apologetic it undercuts the ask. The CTA \
doesn't need to be the literal offer string — a close paraphrase that doesn't overpromise \
is fine."""


def grade_cta_llm(client: Anthropic, brief: dict, cta: str) -> CriterionResult:
    if not cta.strip():
        return CriterionResult(passed=False, critique="cta is empty.")

    offer = brief["offer"]
    prompt = f"""Brand: {brief['brand']['name']}

The brief's actual offer:
Call to action: {offer['call_to_action']}
Core offer: {offer['core_offer']}
Pricing/packaging: {offer['pricing_packaging']}
Guarantee: {offer['guarantee']}

CTA to grade: "{cta}\""""

    return _judge_call(client, CTA_JUDGE_SYSTEM, prompt)


# ---------- Criterion 5: Visual fit — vision judge, two images ----------

VISUAL_JUDGE_SYSTEM = """You are grading a generated ad image against a base product photo \
and a brand brief. You will see two images: the original, untouched product photo, then the \
generated ad. Check, in order:
1. Product fidelity: is the product itself, its label text, logo, and any printed numbers \
(volumes, ABV, etc.) unchanged and legible in the generated image, compared to the original?
2. Scene fit: does the new background/setting/lighting match the brand's personality and \
avoid anything on its "we are not" list?
3. On-image text (if any is rendered onto the ad): does it read in the brand's voice and \
avoid claims the brief doesn't support — the same bar written copy is held to?
4. Typography: if there is on-image text, does its typeface plausibly match the font used \
for the brand's own name/logotype as printed on the product — not a generic, unrelated font \
with no basis in the actual packaging?
Fail if any of the four checks fails, and say which one in your critique."""


def encode_image(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("utf-8")


def grade_visual_fit_llm(
    client: Anthropic, brief: dict, base_image_path: Path, generated_image_path: Path
) -> CriterionResult:
    brand, tone = brief["brand"], brief["tone"]
    prompt_text = f"""Brand: {brand['name']}
Personality: {', '.join(brand['personality'])}
Voice words: {', '.join(tone['voice_words'])}
We are not: {', '.join(tone['we_are_not'])}
The brand's own name/logotype text (the typography anchor): "{brand['name']}\""""

    content = [
        {"type": "text", "text": "Original product photo:"},
        {"type": "image", "source": {
            "type": "base64", "media_type": "image/png",
            "data": encode_image(base_image_path),
        }},
        {"type": "text", "text": "Generated ad image:"},
        {"type": "image", "source": {
            "type": "base64", "media_type": "image/png",
            "data": encode_image(generated_image_path),
        }},
        {"type": "text", "text": prompt_text},
    ]

    return _judge_call(client, VISUAL_JUDGE_SYSTEM, content)


# ---------- Orchestration ----------

def judge_variant(client: Anthropic, brief: dict, row: dict) -> dict:
    headline, body, cta = row["headline"], row["body"], row["cta"]

    length_result = grade_length(headline, body, cta)

    code_hits = grade_claims_code(headline, body, cta, brief["tone"]["vocabulary"]["avoid"])
    if code_hits:
        claims_result = CriterionResult(
            passed=False, critique=f"Contains avoid-listed term(s): {', '.join(code_hits)}."
        )
    else:
        claims_result = grade_claims_llm(client, brief, headline, body, cta)

    tone_result = grade_tone_llm(client, brief, headline, body)
    cta_result = grade_cta_llm(client, brief, cta)

    base_image_path = DATA_DIR / brief["product"]["image_file"]
    generated_image_path = Path(row["image_path"])
    visual_result = grade_visual_fit_llm(client, brief, base_image_path, generated_image_path)

    critiques = [
        f"{name}: {result.critique}"
        for name, result in [
            ("Tone", tone_result), ("Claims", claims_result), ("CTA", cta_result),
            ("Length", length_result), ("Visual fit", visual_result),
        ]
        if not result.passed
    ]

    return {
        **row,
        "tone_pass": tone_result.passed,
        "claims_pass": claims_result.passed,
        "cta_pass": cta_result.passed,
        "length_pass": length_result.passed,
        "visual_fit_pass": visual_result.passed,
        "critique": " | ".join(critiques),
    }


def run_judge(
    input_path: Path = Path("dataset/all_variants.csv"),
    output_path: Path = Path("dataset/judged_variants.csv"),
) -> Path:
    client = Anthropic()
    briefs = load_briefs()

    with open(input_path, newline="") as f:
        rows = list(csv.DictReader(f))

    output_path.parent.mkdir(exist_ok=True)
    passed_count = 0

    with open(output_path, "w", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=list(rows[0].keys()))
        writer.writeheader()

        for i, row in enumerate(rows, start=1):
            print(f"Judging {i}/{len(rows)}: {row['brand']} variant {row['variant_number']}...")
            judged_row = judge_variant(client, briefs[row["brand"]], row)
            writer.writerow(judged_row)
            out_f.flush()  # write incrementally — see note below

            if all(judged_row[k] for k in (
                "tone_pass", "claims_pass", "cta_pass", "length_pass", "visual_fit_pass"
            )):
                passed_count += 1

    print(f"\nDone. {passed_count}/{len(rows)} variants passed all 5 criteria.")
    print(f"Results: {output_path}")
    return output_path


if __name__ == "__main__":
    run_judge()