from unittest.mock import MagicMock, patch

from ad_creative_generator.judge import (
    CriterionResult,
    grade_claims_llm,
    grade_cta_llm,
    grade_tone_llm,
    grade_visual_fit_llm,
    judge_variant,
)


def _riverbend_style_brief():
    return {
        "brand": {
            "name": "Riverbend Brewing Co.",
            "positioning_statement": (
                "For people who'd rather be outside than in a taproom."
            ),
            "personality": ["Outdoorsy", "Unpretentious", "Crisp"],
            "differentiation": (
                "Brewed and packaged specifically for outdoor use, with cans built "
                "for coolers and packs."
            ),
        },
        "tone": {
            "voice_words": ["Easygoing", "Crisp", "Grounded"],
            "we_are": [
                "Focused on real outdoor moments, not staged lifestyle shots",
            ],
            "we_are_not": ["Extreme"],
            "reference_brands": ["Patagonia Provisions"],
            "vocabulary": {
                "use": ["bright hops", "built for outside"],
                "avoid": ["extreme"],
            },
            "example_line": "Bright hops, clean finish, built to fit in a pack.",
        },
        "product": {
            "key_features": ["330mL can"],
            "top_benefits": [
                "A can format that travels easily to the trail, the beach, or the dock",
            ],
            "proof_points": "Brewed in batches under 500 barrels.",
        },
        "offer": {
            "call_to_action": "Grab a 4-pack",
            "core_offer": "Buy a 4-pack, get a Riverbend bottle opener and carabiner clip free.",
            "pricing_packaging": "$14.99 per 4-pack of 330mL cans.",
            "guarantee": "Swap it for another style, no questions asked.",
            "urgency_reason": "Each release sells out within 3-4 weeks.",
        },
    }


def _client_that_captures_the_prompt():
    captured = {}

    def fake_parse(**kwargs):
        captured["messages"] = kwargs["messages"]
        return MagicMock(parsed_output=CriterionResult(passed=True, critique=""))

    client = MagicMock()
    client.messages.parse.side_effect = fake_parse
    return client, captured


# ---------- Claims ----------

def test_claims_prompt_includes_the_real_offer():
    client, captured = _client_that_captures_the_prompt()
    brief = _riverbend_style_brief()
    grade_claims_llm(
        client, brief, headline="Grab it now",
        body="Buy a 4-pack and get a free bottle opener and carabiner clip.",
        cta="Grab a 4-pack",
    )
    prompt_text = captured["messages"][0]["content"]
    assert "bottle opener and carabiner clip" in prompt_text
    assert "$14.99" in prompt_text


def test_claims_prompt_includes_top_benefits_and_differentiation():
    client, captured = _client_that_captures_the_prompt()
    brief = _riverbend_style_brief()
    grade_claims_llm(
        client, brief, headline="Built for the trail",
        body="Travels easily to the trail, the beach, or the dock.",
        cta="Grab a 4-pack",
    )
    prompt_text = captured["messages"][0]["content"]
    assert "travels easily to the trail, the beach, or the dock" in prompt_text
    assert "Brewed and packaged specifically for outdoor use" in prompt_text


# ---------- Tone ----------

def test_tone_prompt_includes_brand_personality():
    client, captured = _client_that_captures_the_prompt()
    brief = _riverbend_style_brief()
    grade_tone_llm(
        client, brief, headline="Bright hops, built for the trail.",
        body="Clean, crisp, and built to travel.",
    )
    prompt_text = captured["messages"][0]["content"]
    assert "Outdoorsy" in prompt_text
    assert "Unpretentious" in prompt_text


# ---------- CTA ----------

def test_cta_prompt_includes_urgency_reason():
    client, captured = _client_that_captures_the_prompt()
    brief = _riverbend_style_brief()
    grade_cta_llm(client, brief, cta="Grab a 4-pack before it's gone")
    prompt_text = captured["messages"][0]["content"]
    assert "sells out within 3-4 weeks" in prompt_text


# ---------- Visual fit ----------

def test_visual_fit_prompt_includes_the_real_offer(tmp_path):
    client, captured = _client_that_captures_the_prompt()
    brief = _riverbend_style_brief()
    base_image = tmp_path / "base.png"
    generated_image = tmp_path / "generated.png"
    base_image.write_bytes(b"not a real png, just needs to exist")
    generated_image.write_bytes(b"not a real png, just needs to exist")
    grade_visual_fit_llm(client, brief, base_image, generated_image)
    content_blocks = captured["messages"][0]["content"]
    prompt_text = content_blocks[-1]["text"]
    assert "bottle opener and carabiner clip" in prompt_text
    assert "330mL can" in prompt_text


def test_visual_fit_prompt_includes_voice_and_benefit_fields(tmp_path):
    client, captured = _client_that_captures_the_prompt()
    brief = _riverbend_style_brief()
    base_image = tmp_path / "base.png"
    generated_image = tmp_path / "generated.png"
    base_image.write_bytes(b"not a real png, just needs to exist")
    generated_image.write_bytes(b"not a real png, just needs to exist")
    grade_visual_fit_llm(client, brief, base_image, generated_image)
    content_blocks = captured["messages"][0]["content"]
    prompt_text = content_blocks[-1]["text"]
    # voice-consistency fields, so on-image text is graded against the same
    # vocabulary/register the Tone judge uses for written copy
    assert "real outdoor moments" in prompt_text
    assert "bright hops" in prompt_text
    assert "Bright hops, clean finish, built to fit in a pack." in prompt_text
    # top benefits / differentiation, same blind spot as Claims had
    assert "travels easily to the trail, the beach, or the dock" in prompt_text
    assert "Brewed and packaged specifically for outdoor use" in prompt_text


# ---------- judge_variant: must judge against the actual base image it's given ----------

def test_judge_variant_uses_the_caller_supplied_base_image_not_data_dir(tmp_path):
    """Regression test: judge_variant used to hardcode DATA_DIR / image_file for
    the base product photo, ignoring whatever image the caller actually used.
    That's correct for the offline batch script (run_judge, which always reads
    from data/) but silently wrong — or a crash — for the Streamlit app, where
    a visitor's own uploaded photo lives in a temp dir, not data/."""
    client = MagicMock()
    client.messages.parse.side_effect = lambda **kwargs: MagicMock(
        parsed_output=CriterionResult(passed=True, critique="")
    )

    brief = _riverbend_style_brief()
    # Deliberately NOT named after anything in data/, to prove this isn't
    # passing by filename coincidence.
    base_image = tmp_path / "some_strangers_uploaded_photo.png"
    generated_image = tmp_path / "generated.png"
    base_image.write_bytes(b"fake")
    generated_image.write_bytes(b"fake")

    row = {"headline": "H", "body": "B", "cta": "C", "image_path": str(generated_image)}

    with patch("ad_creative_generator.judge.encode_image") as mock_encode:
        mock_encode.return_value = "encoded"
        judge_variant(client, brief, row, base_image)

    encoded_paths = [call.args[0] for call in mock_encode.call_args_list]
    assert encoded_paths == [base_image, generated_image]