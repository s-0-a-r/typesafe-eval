"""Hypothesis property-based tests for typesafe-eval invariants.

Verifies:
1. Text chunking invariants (no lost text across window slices, chunk length limits).
2. Sensitive data masking and placeholder preservation (zero secret leakage).
3. Composite score bounds and monotonicity.
"""

from __future__ import annotations

import re

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.models import (
    NoulResult,
    PresetConfig,
    QuestionConfig,
    ScoreResult,
)
from typesafe_eval.sanitizer import (
    chunk_text,
    guard_document_length,
    is_credential_placeholder,
    mask_sensitive_data,
)

settings.register_profile("ci", database=None)
settings.load_profile("ci")

# ---------------------------------------------------------------------------
# 1. Text Chunking Invariants
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    text=st.text(min_size=1, max_size=5000),
    max_chars=st.integers(min_value=200, max_value=1000),
    overlap_ratio=st.floats(min_value=0.1, max_value=0.4),
)
def test_property_chunking_invariants(text: str, max_chars: int, overlap_ratio: float) -> None:
    """Property: Chunks must not be empty, must cover content, and respect bounds."""
    overlap = int(max_chars * overlap_ratio)
    chunks = chunk_text(text, max_chars=max_chars, overlap=overlap)

    assert len(chunks) >= 1

    # Invariant 1: No chunk should be completely empty
    for c in chunks:
        assert len(c) > 0

    # Invariant 2: If the text is shorter than max_chars, exactly 1 chunk is produced
    if len(text) <= max_chars:
        assert len(chunks) == 1
        assert chunks[0] == text

    # Invariant 3: Chunks collectively cover words of the text
    # Every word (alphanumeric sequence) in text must appear in at least one chunk
    words = [w for w in re.findall(r"\b\w+\b", text) if len(w) <= max_chars]
    for w in words[:20]:  # sample check for performance
        assert any(w in c for c in chunks), f"Word '{w}' lost during chunking"


@settings(max_examples=80)
@given(
    text=st.text(min_size=0, max_size=3000),
    max_chars=st.integers(min_value=50, max_value=1500),
)
def test_property_guard_document_length_invariants(text: str, max_chars: int) -> None:
    """Property: guard_document_length truncates strictly when len > max_chars."""
    result, was_truncated = guard_document_length(text, max_chars=max_chars)

    if len(text) <= max_chars:
        assert was_truncated is False
        assert result == text
    else:
        assert was_truncated is True
        assert len(result) <= max_chars


# ---------------------------------------------------------------------------
# 2. Sensitive Data Masking & Zero Leakage Invariants
# ---------------------------------------------------------------------------

AWS_KEY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


@st.composite
def text_with_embedded_secrets(draw: st.DrawFn) -> tuple[str, list[str]]:
    """Generates arbitrary prose text with randomly embedded valid AWS keys and emails."""
    prose_prefix = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=100))
    prose_middle = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=100))
    prose_suffix = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=100))

    # Generate a syntactically valid AWS key: AKIA + 16 uppercase/digit chars
    aws_suffix = "".join(
        draw(st.lists(st.sampled_from(AWS_KEY_ALPHABET), min_size=16, max_size=16))
    )
    raw_aws_key = f"AKIA{aws_suffix}"
    assume(not is_credential_placeholder(raw_aws_key))

    # Generate a free-mail address
    user_name = draw(st.from_regex(r"[a-z0-9]{5,10}", fullmatch=True))
    raw_email = f"{user_name}@gmail.com"

    text = (
        f"{prose_prefix} secret_key={raw_aws_key} contact={raw_email} {prose_middle} {prose_suffix}"
    )
    return text, [raw_aws_key, raw_email]


@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
@given(data=text_with_embedded_secrets())
def test_property_zero_leakage_guarantee(data: tuple[str, list[str]]) -> None:
    """Property: Zero raw sensitive tokens leak into sanitized output."""
    text, raw_tokens = data
    sanitized, redaction_count, details = mask_sensitive_data(text, mask=True, return_details=True)

    assert details is not None
    # Invariant: Raw secrets and personal emails must NEVER appear in sanitized content
    for token in raw_tokens:
        assert token not in sanitized, (
            f"Raw sensitive token '{token}' leaked into sanitized content!"
        )

    # Invariant: Redaction count must match number of detected items
    assert redaction_count >= len(raw_tokens)

    # Invariant: Placeholders must follow standard pattern
    placeholders = re.findall(r"\[(?:REDACTED_[A-Z_]+|[A-Z_]+_\d+|EXAMPLE_[A-Z_]+)\]", sanitized)
    assert len(placeholders) >= len(raw_tokens)

    # Invariant: In mask=True, _raw_mapping is omitted for zero-leak security
    assert "_raw_mapping" not in details

    # Invariant: In mask=False, _raw_mapping contains raw tokens
    _, _, unmasked_details = mask_sensitive_data(text, mask=False, return_details=True)
    assert unmasked_details is not None
    raw_mapping = unmasked_details.get("_raw_mapping", {})
    all_mapped_raws = [raw for vals in raw_mapping.values() for raw in vals]
    for token in raw_tokens:
        assert token in all_mapped_raws


# ---------------------------------------------------------------------------
# 3. Composite Score Bounds & Monotonicity Invariants
# ---------------------------------------------------------------------------


@st.composite
def score_and_preset_strategy(
    draw: st.DrawFn,
) -> tuple[PresetConfig, dict[str, ScoreResult], dict[str, ScoreResult]]:
    """Generates two parallel sets of scores S1 and S2 where S1 <= S2 for all questions."""
    num_questions = draw(st.integers(min_value=1, max_value=5))
    questions: dict[str, QuestionConfig] = {}
    scores_low: dict[str, ScoreResult] = {}
    scores_high: dict[str, ScoreResult] = {}

    for i in range(num_questions):
        q_id = f"q_{i}"
        weight = draw(st.floats(min_value=0.1, max_value=10.0))
        questions[q_id] = QuestionConfig(
            type="score",
            instructions=f"Test question {i}",
            weight=weight,
            min_threshold=0.5,
        )

        s_low = draw(st.floats(min_value=0.0, max_value=0.5))
        s_high = draw(st.floats(min_value=s_low, max_value=1.0))

        scores_low[q_id] = ScoreResult(
            score=s_low * 2.0,
            max_score=2.0,
            normalized_score=s_low,
            confidence=0.9,
            probabilities={},
        )
        scores_high[q_id] = ScoreResult(
            score=s_high * 2.0,
            max_score=2.0,
            normalized_score=s_high,
            confidence=0.9,
            probabilities={},
        )

    preset = PresetConfig(name="prop_preset", questions=questions)
    return preset, scores_low, scores_high


@settings(max_examples=100)
@given(data=score_and_preset_strategy())
def test_property_composite_score_bounds_and_monotonicity(
    data: tuple[PresetConfig, dict[str, ScoreResult], dict[str, ScoreResult]],
) -> None:
    """Property: Composite scores are bounded in [0.0, 1.0] and monotonic with respect to inputs."""
    preset, scores_low, scores_high = data
    evaluator = TypeSafeEvaluator()

    nouls: dict[str, NoulResult] = {}
    comp_low, passed_low, _, _ = evaluator._evaluate_thresholds_and_composite(
        preset=preset,
        scores=scores_low,
        nouls=nouls,
        choices={},
    )
    comp_high, passed_high, _, _ = evaluator._evaluate_thresholds_and_composite(
        preset=preset,
        scores=scores_high,
        nouls=nouls,
        choices={},
    )

    assert comp_low is not None
    assert comp_high is not None

    # Invariant 1: Scores must be strictly in [0.0, 1.0]
    assert 0.0 <= comp_low <= 1.0 + 1e-9
    assert 0.0 <= comp_high <= 1.0 + 1e-9

    # Invariant 2: Monotonicity - higher question scores cannot result in a lower composite
    assert comp_high >= comp_low - 1e-9

    # Invariant 3: If scores_low had all values <= 0.5 and min_threshold is 0.5,
    # any score strictly below 0.5 must fail thresholds
    has_strictly_low = any(s.normalized_score < 0.5 for s in scores_low.values())
    if has_strictly_low:
        assert passed_low is False
