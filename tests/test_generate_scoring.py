"""Mocked tests for the /generate endpoint's judge-scoring wiring.

No real API calls: Anthropic, OpenAI, generate_copy, generate_image, and
judge_variant are all patched. This tests plumbing (does the best-scoring
variant surface correctly, sorted first) at $0.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from ad_creative_generator.generate_copy import CopyVariant
from ad_creative_generator.main import app

client = TestClient(app)


def _fake_generate_copy(anthropic_client, brief, count=5):
    return [
        CopyVariant(
            variant_number=i,
            headline=f"Headline {i}",
            body=f"Body {i}.",
            cta="Go",
        )
        for i in range(1, count + 1)
    ]


def _make_fake_generate_image(tmp_path):
    def _fake_generate_image(openai_client, brief, variant, product_image_path, output_dir):
        image_path = Path(output_dir) / f"variant_{variant['variant_number']}.png"
        image_path.write_bytes(b"fake png bytes")
        return str(image_path)

    return _fake_generate_image


def _fake_judge_variant(anthropic_client, brief, row, base_image_path):
    # Alternate visual_fit_pass by variant parity so variants get different
    # scores, and the "best first" sort has something real to prove.
    visual_fit_pass = row["variant_number"] % 2 == 0
    return {
        **row,
        "tone_pass": True,
        "claims_pass": True,
        "cta_pass": True,
        "length_pass": True,
        "visual_fit_pass": visual_fit_pass,
        "critique": "" if visual_fit_pass else "Visual fit: scene doesn't match the brief.",
    }


@patch("ad_creative_generator.pipeline.OpenAI")
@patch("ad_creative_generator.pipeline.Anthropic")
@patch("ad_creative_generator.pipeline.judge_variant", side_effect=_fake_judge_variant)
@patch("ad_creative_generator.pipeline.generate_copy", side_effect=_fake_generate_copy)
@patch("ad_creative_generator.pipeline.generate_image")
def test_generate_sorts_variants_best_score_first(
    mock_generate_image, mock_generate_copy, mock_judge_variant, mock_anthropic, mock_openai, tmp_path
):
    mock_generate_image.side_effect = _make_fake_generate_image(tmp_path)
    mock_anthropic.return_value = MagicMock()
    mock_openai.return_value = MagicMock()

    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        '{"brand": {"name": "Test Brand"}, "product": {"image_file": "product.png"}}'
    )
    (tmp_path / "product.png").write_bytes(b"fake product photo")

    response = client.post(
        "/generate", json={"brief_path": str(brief_path), "count": 4}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["variant_count"] == 4
    # Variants 2 and 4 pass visual_fit (score 5); 1 and 3 fail it (score 4).
    assert body["best_judge_score"] == 5

    manifest_path = Path(body["output_dir"]) / "manifest.json"
    import json as _json

    manifest = _json.loads(manifest_path.read_text())
    scores = [v["judge_score"] for v in manifest["variants"]]
    assert scores == sorted(scores, reverse=True)


@patch("ad_creative_generator.pipeline.OpenAI")
@patch("ad_creative_generator.pipeline.Anthropic")
@patch("ad_creative_generator.pipeline.judge_variant", side_effect=_fake_judge_variant)
@patch("ad_creative_generator.pipeline.generate_copy", side_effect=_fake_generate_copy)
@patch("ad_creative_generator.pipeline.generate_image")
def test_generate_best_variant_headline_matches_top_score(
    mock_generate_image, mock_generate_copy, mock_judge_variant, mock_anthropic, mock_openai, tmp_path
):
    mock_generate_image.side_effect = _make_fake_generate_image(tmp_path)
    mock_anthropic.return_value = MagicMock()
    mock_openai.return_value = MagicMock()

    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        '{"brand": {"name": "Test Brand"}, "product": {"image_file": "product.png"}}'
    )
    (tmp_path / "product.png").write_bytes(b"fake product photo")

    response = client.post(
        "/generate", json={"brief_path": str(brief_path), "count": 2}
    )

    body = response.json()
    # Variant 2 is the only one that passes all 5 (visual_fit_pass on even
    # variant numbers)
    assert body["best_variant_headline"] == "Headline 2"


@patch("ad_creative_generator.pipeline.OpenAI")
@patch("ad_creative_generator.pipeline.Anthropic")
@patch("ad_creative_generator.pipeline.judge_variant", side_effect=_fake_judge_variant)
@patch("ad_creative_generator.pipeline.generate_copy", side_effect=_fake_generate_copy)
@patch("ad_creative_generator.pipeline.generate_image")
@patch("ad_creative_generator.pipeline.datetime")
def test_two_concurrent_runs_for_the_same_brand_dont_collide(
    mock_datetime, mock_generate_image, mock_generate_copy, mock_judge_variant,
    mock_anthropic, mock_openai, tmp_path,
):
    """Regression test: output_dir used to be brand + second-resolution
    timestamp only. Two visitors generating for the same brand within the
    same second used to land in the same output_dir and could clobber each
    other's files — a real risk on a public, multi-visitor demo."""
    import datetime as real_datetime

    frozen_now = real_datetime.datetime(2026, 1, 1, 12, 0, 0)
    mock_datetime.now.return_value = frozen_now  # every call sees the same second

    mock_generate_image.side_effect = _make_fake_generate_image(tmp_path)
    mock_anthropic.return_value = MagicMock()
    mock_openai.return_value = MagicMock()

    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        '{"brand": {"name": "Test Brand"}, "product": {"image_file": "product.png"}}'
    )
    (tmp_path / "product.png").write_bytes(b"fake product photo")

    from ad_creative_generator.pipeline import run_pipeline

    output_dir_1 = run_pipeline(str(brief_path), count=1)
    output_dir_2 = run_pipeline(str(brief_path), count=1)

    assert output_dir_1 != output_dir_2
    assert Path(output_dir_1).exists() and Path(output_dir_2).exists()
    assert (Path(output_dir_1) / "manifest.json").exists()
    assert (Path(output_dir_2) / "manifest.json").exists()