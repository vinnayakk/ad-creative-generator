# Ad Creative Generator

A brief and a product photo go in; scored ad variants come out. Copy and image
variants are generated together, and each one is graded against the brand's
own rules by an LLM judge before a human ever sees it.

![Demo](demo.gif)

**TRY IT:** [ad-creative-generator-withjudge.streamlit.app](https://ad-creative-generator-withjudge.streamlit.app/) (bring your own Anthropic + OpenAI API keys).

## The problem

Teams running paid ad campaigns need many on-brand variants to test, but
hand-writing them doesn't scale, and naive LLM generation drifts off-brand
fast. Early, un-evaluated output from this project showed exactly that: every
variant reused the same CTA, copy kept repeating the brand's mission
statement instead of its actual product facts, and most variants ignored the
brief's stated offer and tone rules entirely. This project isn't just a
generator. It's a generator that scores its own output against the brief
before a human wastes time reviewing it.

## How it works

```
brand brief (JSON) + product photo
        │
        ▼
  copy variants ──────────► Claude (Sonnet), structured output, Pydantic-validated
        │
        ▼
  ad images ──────────────► OpenAI gpt-image-2, edits the product photo per variant
        │
        ▼
  judge (5 criteria) ─────► code checks + Claude as a text/vision judge
        │
        ▼
  scored, ranked variants (CSV + manifest.json)
```

1. `generate_copy.py` turns one brand brief into N distinct copy variants
   (headline / body / CTA) in a single structured-output call to Claude,
   validated with Pydantic.
2. `generate_ad_image_brand.py` edits the uploaded product photo per variant
   via OpenAI's `gpt-image-2`, keeping the product itself unchanged and only
   adjusting the scene.
3. `judge.py` grades every variant against 5 independent criteria: tone,
   claims, call to action, length, and visual fit. It mixes cheap code
   checks (word counts, forbidden-term matching) with Claude-as-judge calls
   for anything that needs real judgment. Full rubric: [`docs/rubric.md`](docs/rubric.md).
4. `pipeline.py` orchestrates all three steps, sorts variants best-score-first,
   and writes `results.csv` + `manifest.json`.
5. `main.py` (FastAPI) exposes this as `POST /generate`. `streamlit_app.py`
   is the public front-end: visitors bring their own Anthropic + OpenAI
   keys, used only in memory for their one request and never stored.

## Evaluation

The judge is measured against my own hand labels, not trusted on faith.

**Method:** generated 90 variants across 3 brands (30 each), labelled all 90
myself pass/fail per criterion, then compared the judge's verdicts to mine.

| Criterion                           | Agreement, v1 | Agreement, v2 (after one prompt fix) |
| ----------------------------------- | ------------- | ------------------------------------ |
| Tone                                | 78.9%         | 80.0%                                |
| Claims                              | 73.3%         | 75.6%                                |
| Call to action                      | 95.6%         | 95.6%                                |
| Length                              | 98.9%         | 98.9%                                |
| Visual fit                          | 57.8%         | 60.0%                                |
| **Overall (per-criterion average)** | **80.9%**     | **82.0%**                            |

**Variant-level agreement** (judge's "fully approved, all 5 pass" matches
mine) went **66.7% → 61.1%**. It went _down_, even though every individual
criterion improved. Not a contradiction: fixing Claims stopped it from
wrongly flagging real, brief-supported claims as invented, so several
variants that used to fail on Claims alone now pass it, but some of those
same variants still fail on Tone or a new visual-restraint check, for
unrelated reasons. They flip from "judge fails, I fail" (agreement) to
"judge passes, I fail" (a new disagreement). Five independent pass/fail
checks ANDed into one verdict means improving one axis can expose
disagreement on another, not just hide it. (Judge-too-lenient rows went
17→21; judge-too-strict went 13→14.)

**Cost and time:** around $5 or less per 20-variant batch, and up to 30 to
40 minutes, often faster, for Claude copy generation and judging plus
gpt-image-2 images.

## Results

- 90 variants generated and hand-labeled across 3 brands (headphones,
  cooking oil, craft beer).
- 51/90 variants (56.7%) passed all 5 judge criteria outright in the full run.
- 82.0% average per-criterion judge-vs-human agreement (up from 80.9% before
  one prompt fix).
- Public demo deployed, bring-your-own-key, tested end-to-end from a phone
  over mobile data.

## Stack

Python · FastAPI · Pydantic · Anthropic Claude (copy generation + judge) ·
OpenAI `gpt-image-2` (images) · Streamlit (front-end) · Docker · GitHub
Actions (CI, runs the full pytest suite on every push). Built from a
personal [FastAPI + Docker + CI template](https://github.com/vinnayakk/ai-app-template).

## How to run

```bash
git clone https://github.com/vinnayakk/ad-creative-generator && cd ad-creative-generator
cp .env.example .env   # fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
pip install -r requirements.txt
python -m ad_creative_generator.pipeline data/velara_headphones_brandbrief.json   # CLI
streamlit run streamlit_app.py   # UI, http://localhost:8501
```

No setup needed to just try it: the [live demo](https://ad-creative-generator-withjudge.streamlit.app/)
runs the same code, bring-your-own-key.

**Using your own data:** the 3 brands in `data/` (headphones, cooking oil,
craft beer) are made-up brands with made-up briefs and product photos, not
real companies. Swap in your own brief and product photo freely, made up or
real. A brief just needs to follow the same JSON structure as the ones in
`data/` (brand, tone, offer, and product sections). A more formal, detailed
brief, one that spells out logo placement, brand colors, text/copy rules,
sizing, and font or typeface, gives the judge tighter constraints to check
against, which tends to produce more reliable scoring.

## Known limitations and next steps

- Variant-level (all-5-must-pass) agreement sits at ~61% even though every
  individual criterion is 75%+. A strict AND-gate across 5 independent
  judges compounds disagreement. A weighted score instead of pass/fail-all
  would likely track human judgment more closely.
- Visual fit is the weakest single criterion (~60% agreement). It's the only
  vision-based judge of the five, and the hardest to calibrate. More
  few-shot examples, or splitting it into sub-checks, is the next move.
- No shared trial key: every visitor brings their own Anthropic + OpenAI
  keys. Deliberate, to keep this project's cost exposure at exactly zero.
  A rate-limited shared key is a natural follow-up, not a blocker.
- A handful of judge correctness bugs (missing brief fields in a few
  prompts, an image-path bug, a concurrent-run file collision) were found
  and fixed through real usage after the agreement numbers above were
  recorded. They reflect the judge as of that eval, not line-for-line the
  current code. Re-running the 90-variant comparison against the current
  judge is the natural next step before leaning on these numbers long-term.
