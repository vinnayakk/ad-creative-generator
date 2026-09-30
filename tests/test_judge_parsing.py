"""
Tests for how judge.py parses (and fails to parse) model output.

Like test_generate_scoring.py, these never call a real model. _judge_call
takes its Anthropic client as a plain function argument (not something it
constructs itself), so mocking it is simpler than pipeline.py's case: no
patch-target juggling, just pass in a stand-in object shaped like the real
client's response.

"""
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from ad_creative_generator.judge import (
    CriterionResult,
    _clean_avoid_terms,
    _judge_call,
    grade_claims_code,
    grade_cta_llm,
    grade_length,
)


# ---------- _judge_call: the actual "output parsing" logic ----------

def test_judge_call_returns_parsed_output_on_success():
    expected = CriterionResult(passed=True, critique="")
    mock_response = MagicMock(parsed_output=expected)
    mock_client = MagicMock()
    mock_client.messages.parse.return_value = mock_response

    result = _judge_call(mock_client, "system prompt", "user content")

    assert result is expected
    # also check it's actually asking for CriterionResult back, not just
    # that it happens to work when we hand it one
    _, kwargs = mock_client.messages.parse.call_args
    assert kwargs["output_format"] is CriterionResult
    assert kwargs["model"] == "claude-sonnet-5"


def test_judge_call_wraps_validation_error_with_a_clear_message():
    # A real ValidationError, not a hand-built one -- CriterionResult.critique
    # has no default, so constructing one without it raises exactly the kind
    # of error client.messages.parse() raises internally on truncated JSON.
    # (Python drops the exception variable itself once an except block ends,
    # so capture it via pytest.raises rather than an except-as binding.)
    with pytest.raises(ValidationError) as exc_info:
        CriterionResult(passed=True)
    real_error = exc_info.value

    mock_client = MagicMock()
    mock_client.messages.parse.side_effect = real_error

    with pytest.raises(RuntimeError, match="max_tokens"):
        _judge_call(mock_client, "system", "content", max_tokens=500)


def test_judge_call_raises_when_parsed_output_is_none():
    mock_response = MagicMock(parsed_output=None, stop_reason="max_tokens")
    mock_client = MagicMock()
    mock_client.messages.parse.return_value = mock_response

    with pytest.raises(RuntimeError, match="no structured output"):
        _judge_call(mock_client, "system", "content")


# ---------- grade_length: code only, no model involved ----------

def test_grade_length_passes_within_bounds():
    result = grade_length("Short headline", "One sentence body.", "Act now")
    assert result.passed is True
    assert result.critique == ""


def test_grade_length_fails_long_headline():
    long_headline = " ".join(["word"] * 13)  # 13 > 12-word bound
    result = grade_length(long_headline, "Fine.", "Act now")
    assert result.passed is False
    assert "headline is 13 words" in result.critique


def test_grade_length_fails_empty_fields_and_lists_all_of_them():
    result = grade_length("", "", "")
    assert result.passed is False
    assert "headline is empty" in result.critique
    assert "body is empty" in result.critique
    assert "cta is empty" in result.critique


# ---------- claims: the code-only pre-filter ----------

def test_clean_avoid_terms_strips_annotations_and_lowercases():
    assert _clean_avoid_terms(["Extreme", "superfood (unverified)"]) == [
        "extreme",
        "superfood",
    ]


def test_grade_claims_code_catches_avoid_terms_case_insensitively():
    hits = grade_claims_code(
        "Nothing EXTREME here", "just a good beer", "Grab one",
        avoid_terms=["extreme", "hoppy bomb"],
    )
    assert hits == ["extreme"]


def test_grade_claims_code_clean_when_no_avoid_terms_present():
    hits = grade_claims_code(
        "Bright hops, clean finish", "built for outside", "Grab a 4-pack",
        avoid_terms=["extreme", "hoppy bomb"],
    )
    assert hits == []


# ---------- grade_cta_llm: the empty-CTA short-circuit ----------

def test_grade_cta_llm_short_circuits_on_empty_cta_without_calling_the_model():
    mock_client = MagicMock()

    # brief is deliberately empty -- if this reached the model-call path it
    # would KeyError on brief["offer"] before the mock even mattered, which
    # is exactly the point: an empty CTA should never get that far.
    result = grade_cta_llm(mock_client, brief={}, cta="   ")

    assert result.passed is False
    assert "empty" in result.critique
    mock_client.messages.parse.assert_not_called()