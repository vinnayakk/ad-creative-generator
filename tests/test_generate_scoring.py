"""
Tests for the judge-score wiring in /generate (pipeline.py + main.py).

These never call a real AI model. generate_copy, generate_image, and
judge_variant are all replaced with stand-ins below, so running this file
costs nothing and never touches the network. It checks the *plumbing* --
that pipeline.py calls the judge, computes judge_score, and sorts by it,
and that main.py surfaces the winner correctly. It does not check whether
the AI's output is any good -- that's a different question, and it's what
the batch judge run + human-agreement comparison is for. That one costs
real money on purpose, because it has to actually call the models.
"""
import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ad_creative_generator.generate_copy import CopyVariant
from ad_creative_generator.main import app

client = TestClient(app)


@pytest.fixture
def fake_brief_path(tmp_path):
    # Minimal brief -- just enough for pipeline.py's own code (not the
    # mocked-out functions) to read brief["brand"]["name"] and
    # brief["product"]["image_file"] without crashing.
    brief = {
        "brand": {"name": "TestBrand", "personality": ["Calm"]},
        "product": {"image_file": "product.png"},
        "tone": {
            "voice_words": ["Plain"],
            "we_are_not": [],
            "reference_brands": ["A generic reference brand"],
            "vocabulary": {"avoid": []},
        },
    }
    path = tmp_path / "brief.json"
    path.write_text(json.dumps(brief))
    return str(path)


def _fake_generate_copy(brief, count=5):
    return [
        CopyVariant(variant_number=i, headline=f"Headline {i}", body=f"Body {i}", cta="Act now")
        for i in range(1, count + 1)
    ]


def _fake_generate_image(brief, variant, product_image_path):
    # The real generate_image calls an image model and returns the path of
    # a real generated file. Stand in with a throwaway file -- pipeline.py
    # just needs something on disk it can shutil.move() into outputs/.
    scratch = Path(product_image_path).parent / f"fake_image_{variant['variant_number']}.png"
    scratch.write_bytes(b"not a real png, just needs to exist on disk")
    return str(scratch)


def _fake_judge_variant(client_, brief, row):
    # Give variants different scores so the sort has something to prove:
    # odd variant numbers "pass" visual fit, even ones "fail" it.
    visual_fit_pass = row["variant_number"] % 2 == 1
    return {
        **row,
        "tone_pass": True,
        "claims_pass": True,
        "cta_pass": True,
        "length_pass": True,
        "visual_fit_pass": visual_fit_pass,
        "critique": "" if visual_fit_pass else "Visual fit: stubbed failure for testing.",
    }


# Patch targets point at ad_creative_generator.pipeline, not the original
# modules -- mock.patch replaces the name where it's *looked up*, and
# pipeline.py imported each of these into its own namespace
# (`from ... import generate_copy`), so that's the name that has to change.
@patch("ad_creative_generator.pipeline.judge_variant", side_effect=_fake_judge_variant)
@patch("ad_creative_generator.pipeline.generate_image", side_effect=_fake_generate_image)
@patch("ad_creative_generator.pipeline.generate_copy", side_effect=_fake_generate_copy)
@patch("ad_creative_generator.pipeline.Anthropic")  # never construct a real client either
def test_generate_sorts_by_judge_score(
    mock_anthropic, mock_copy, mock_image, mock_judge, fake_brief_path, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)  # keep the outputs/ folder this creates inside tmp_path

    response = client.post("/generate", json={"brief_path": fake_brief_path, "count": 4})

    assert response.status_code == 200
    body = response.json()

    # Our stub passes visual_fit for odd variant numbers -> score 5 there,
    # 4 everywhere else. Variant 1 is the first score-5 row, and Python's
    # sort is stable, so it should win the tie over variant 3.
    assert body["best_judge_score"] == 5
    assert body["best_variant_headline"] == "Headline 1"

    # results.csv on disk should be sorted best-score-first too, not just
    # the API response.
    results_csv = Path(body["output_dir"]) / "results.csv"
    with open(results_csv) as f:
        rows = list(csv.DictReader(f))
    scores = [int(r["judge_score"]) for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert scores == [5, 5, 4, 4]