# Brand rubric (v0)

Five binary (pass/fail) criteria, applied per generated variant. No 1–5 scales —
per Hamel Husain's [LLM-as-a-judge guide](https://hamel.dev/blog/posts/llm-judge/),
a graded scale hides disagreement about what actually matters and nobody can act on
"3.5". Every fail must come with a one-sentence critique: specific enough that
someone who has never seen the variant understands exactly what to fix.

This is v0. Expect "criteria drift" (Shankar et al., cited in Hamel's guide): the
bars below will move once I've labelled ~15–20 real variants and found failure
modes I didn't anticipate here. Revise this file when that happens — don't fork it.

## How each criterion gets graded

Per Anthropic's [grading guidance](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)
("code-based > LLM-based > human — pick the fastest reliable method") and Eugene
Yan's "[one evaluator per dimension](https://eugeneyan.com/writing/product-evals/)"
rule, each criterion below is graded independently, not folded into one judge call.

| #   | Criterion      | Reads                                | Grading method                                                                                                             |
| --- | -------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| 1   | Tone           | `headline`, `body`                   | LLM judge (subjective, needs few-shot)                                                                                     |
| 2   | Claims         | `headline`, `body`, `cta`            | Code first (string match on `avoid`), LLM judge for unverified-superlative / we_are_not cases the string match can't catch |
| 3   | Call to action | `cta`                                | Code (length + presence) + LLM judge (does it contradict the offer?)                                                       |
| 4   | Length         | `headline`, `body`, `cta`            | Code only (word count)                                                                                                     |
| 5   | Visual fit     | generated image + base product image | Vision LLM judge                                                                                                           |

Three of five criteria are cheap and deterministic. Only Tone, the qualitative half
of Claims, and Visual fit need a model call — that's where the labelling effort
should go.

---

## 1. Tone

**Pass bar:** the copy reads like the brief's `tone.voice_words` and
`tone.we_are` list, at the register of `tone.example_line` — not like the
`tone.we_are_not` list or a competitor's brief.

**Fails when:**

- It matches a `we_are_not` line (e.g. hyperbolic sound-quality claims for
  Velara, a "wellness ritual" framing for Verdan, "brewed with passion"-style
  cliché for Riverbend).
- It could be swapped into a different brand's ad with no edits — genericness is
  a tone failure, not a pass with a shrug.
- It ignores every `vocabulary.use` term and every `we_are` line in favor of
  generic ad-speak.

**Calibration anchor:** `tone.reference_brands` in each brief (e.g. Velara →
Apple, B&O; Verdan → Bob's Red Mill, Simple Mills; Riverbend → Patagonia
Provisions, Fjällräven). If it doesn't sound like it could sit next to those
brands' copy, that's the tell.

## 2. Claims

**Pass bar:** every factual or superlative claim is either (a) directly
supported by `product.proof_points` / stated numbers in the brief (battery
hours, ALC/VOL, Omega ratio, batch size), or (b) absent — no claim, no risk.

**Fails when:**

- Any literal term from `tone.vocabulary.avoid` appears (code catches this —
  strip the `(unverified)` / `(overused)` annotations before matching, they're
  notes to you, not part of the string).
- A synonym of an avoid-term or a `we_are_not` line appears even without the
  literal word (e.g. "life-changing" for Velara reads as "revolutionary" even
  though it isn't the listed string — an LLM judge is needed here, code alone
  will miss it).
- A number is invented or inflated beyond what the brief states (claiming "50
  hours" for Velara's 40-hour battery, or implying stronger ANC than "reads your
  environment in real time").
- Verdan copy references cannabis, CBD, or "highs" in any form, even jokingly —
  this is the one brand where a Claims fail is closest to a compliance issue,
  not just a brand-voice miss.

## 3. Call to action

**Pass bar:** the variant has exactly one clear, action-oriented CTA line that
does not contradict `offer.call_to_action` or `offer.core_offer` — it does not
have to be the literal brief string, but it can't promise something the offer
doesn't (inventing "free shipping," a discount percentage that isn't
`offer.pricing_packaging`, or a guarantee stronger than `offer.guarantee`).

**Fails when:**

- `cta` is empty, or is a restatement of the headline with no directive verb.
- It invents an offer detail not present in the brief.
- It's tonally off from criterion 1 in a way that undercuts the action (e.g. an
  apologetic or hedgy CTA for Riverbend's "Grab a 4-pack" energy).

## 4. Length

**Pass bar** (word counts, checked by code):

| Field    | Pass                       | Basis                                                                                                                                  |
| -------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Headline | ≤ 12 words                 | The three briefs' `tone.example_line` run 8, 10, and 11 words — this is that length plus a small buffer, not an arbitrary round number |
| Body     | ≤ 2 sentences, ≤ ~40 words | `generate_copy.py`'s own prompt already asks for "a 1-2 sentence body" — this just makes that instruction checkable                    |
| CTA      | ≤ 6 words                  | All three briefs' `offer.call_to_action` strings are exactly 3 words — 6 gives headroom without letting the CTA become a sentence      |

**Fails when:** any field is empty, or over its bound. This is the one
criterion with zero judgment calls — if it's failing, the count is wrong, full
stop.

## 5. Visual fit

**Pass bar:** the product itself (shape, label text, logo, printed numbers like
`330 mL` / `6.5% ALC./VOL.` / `500 ml`) is unchanged and legible from the base
product photo — `generate_ad_image_brand.py`'s prompt already asks for this —
and the new background/setting/lighting matches `brand.personality` and does
not read as one of the `tone.we_are_not` lines.

`gpt-image-2` also tends to render the ad headline (and sometimes other brief
text) directly onto the image as on-image typography, even though the prompt
only asks it to use the headline as scene inspiration. This project treats
that as a feature, not a bug — the output is meant to be a finished, postable
ad, not just re-staged product photography — so on-image text is graded here
too, under three additional checks.

**Fails when:**

- Label text, logo, or printed stats are altered, blurred past legibility, or
  warped.
- The scene contradicts the brief: a bar/taproom interior for Riverbend
  (explicitly "not staged lifestyle shots," positioned against the taproom in
  its own differentiation statement), a cluttered or loud scene for Velara
  ("Refined," "Calm," "uncluttered" voice), any cannabis-use imagery (smoking,
  bongs, rolling papers) for Verdan beyond the hemp-leaf motif that's already
  part of its own label art.
- **Visual restraint:** the amount and prominence of on-image typography
  doesn't match the restraint the brief's `tone.reference_brands` and
  `brand.personality` call for. Velara's references are Apple and Bang &
  Olufsen ("restrained, product-led copy," "design-forward, unhurried") and
  its personality includes "Refined" and "Uncluttered" — a large block of
  promotional copy or a price-off callout laid over the product fails this
  check even if every word in it would pass Tone and Claims on its own,
  because the brief is asking for product-forward images with minimal type,
  not just on-brand type. A brand whose reference brands don't carry that
  same restraint (Verdan's Bob's Red Mill and Simple Mills are "plainspoken"
  and "everyday," not minimal) can carry more on-image text without failing
  this check.
- **On-image text content:** any text rendered onto the image would itself
  fail criterion 1 (Tone) or criterion 2 (Claims) if graded as copy — it
  drifts from the brief's voice, or states a claim the brief doesn't support.
  Don't assume this is automatically covered by grading `headline`/`body`/
  `cta` separately — the model sometimes renders more than just the headline
  onto the image (brand personality words showed up unprompted in one pilot
  variant), so the on-image text has to be read off the image itself, not
  assumed to match the CSV row.
- **Typography consistency:** on-image text doesn't match the typeface used for the
  brand's own name/logotype on the product (not just any typeface visible somewhere
  on the label — some labels, like Riverbend's and Verdan's, print the product name
  in a different typeface than the brand name or descriptors, and only the brand
  logotype's font is the anchor), or doesn't match the font used in this brand's
  other variants. A generic default (e.g. a plain serif like Times New Roman)
  appearing with no basis in the brand's actual packaging is always a fail — it
  reads as an unstyled placeholder, not a finished ad.

---

## Applying it: one worked example

Two synthetic Riverbend variants, graded against `riverbend_tide_and_treetop_brandbrief.json`:

**Variant A**

> Headline: "Bright hops, built for the trail."
> Body: "Tide & Treetop is a clean, crisp IPA that travels as easily as you do — from the dock to the campsite."
> CTA: "Grab a 4-pack"

| Criterion      | Judgment                                | Critique                                                                                                                                 |
| -------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Tone           | **Pass**                                | Matches "Easygoing, Crisp, Grounded" and the `we_are` line about real outdoor moments; no cliché from `we_are_not`.                      |
| Claims         | **Pass**                                | "Clean, crisp" and "travels easily" are supported by `proof_points` (dry-hopped twice, 330 mL can built for carry); no invented numbers. |
| Call to action | **Pass**                                | CTA matches `offer.call_to_action` exactly and doesn't invent offer details.                                                             |
| Length         | **Pass**                                | Headline 6 words, body 22 words / 1 sentence, CTA 3 words — all within bounds.                                                           |
| Visual fit     | _(graded on the image, not shown here)_ | —                                                                                                                                        |

**Variant B**

> Headline: "The most extreme hoppy bomb you'll ever crush on the trail, guaranteed."
> Body: "Hand-crafted with passion by real brewers who love what they do, this beer is basically a lifestyle."
> CTA: "Buy now and save 20% before it's gone forever"

| Criterion      | Judgment                                | Critique                                                                                                                                                                                                      |
| -------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tone           | **Fail**                                | "Basically a lifestyle" reads as staged-lifestyle marketing, which `we_are_not` explicitly rules out.                                                                                                         |
| Claims         | **Fail**                                | Contains three literal `avoid` terms — "extreme," "hoppy bomb," "crush" (close enough to "crushable" to flag) — plus "hand-crafted...with passion," which `tone.vocabulary.avoid` lists verbatim as overused. |
| Call to action | **Fail**                                | Invents a 20% discount; the brief's offer is a free bottle opener and carabiner with a 4-pack, not a price cut.                                                                                               |
| Length         | **Fail**                                | Headline is 12 words (borderline pass) but CTA is 9 words — well past the 6-word bound, and reads as urgency copy rather than a directive.                                                                    |
| Visual fit     | _(graded on the image, not shown here)_ | —                                                                                                                                                                                                             |

Variant B is a deliberately bad example to show every failure mode in one place —
real generated copy will usually fail one or two criteria, not all four.
