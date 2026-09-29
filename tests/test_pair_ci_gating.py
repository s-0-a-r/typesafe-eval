"""Unit tests for pair CI gating, grouping, caching, retries, and feasibility check (#42)."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import pytest
from unittest.mock import MagicMock

from typesafe_eval.models import (
    DocumentEvalResult,
    ScoreResult,
    NoulResult,
    PresetConfig,
    QuestionConfig,
)
from typesafe_eval.client import TypeSafeEvaluator, _is_transient_error
from typesafe_eval.validator import (
    get_t_crit_95,
    compute_ci_95,
    run_validation,
    ValidationLabelsConfig,
    ValidationPairExpectation,
    ValidationCriteria,
    load_labels_file,
)
from scripts.feasibility_check import run_feasibility


class FakeEvaluator:
    """Fake evaluator that returns predetermined scores or tracks call counts."""

    def __init__(self, score_map: Optional[Dict[str, float]] = None):
        self.score_map = score_map or {}
        self.call_count = 0
        self.call_log = []

    def evaluate_document(
        self,
        filepath: str,
        preset: PresetConfig,
        mask_secrets: bool = True,
        max_chars: int = 25000,
        dry_run: bool = False,
    ) -> DocumentEvalResult:
        self.call_count += 1
        path = Path(filepath)
        self.call_log.append(str(path))
        score_val = self.score_map.get(str(path), self.score_map.get(path.name, 0.5))

        scores = {}
        for q_id, q_cfg in preset.questions.items():
            if q_cfg.type == "score":
                s = self.score_map.get((str(path), q_id), score_val)
                scores[q_id] = ScoreResult(
                    score=s,
                    max_score=1.0,
                    normalized_score=s,
                    confidence=0.9,
                    probabilities={},
                )
        if not scores:
            scores["clarity"] = ScoreResult(
                score=score_val,
                max_score=1.0,
                normalized_score=score_val,
                confidence=0.9,
                probabilities={},
            )

        return DocumentEvalResult(
            filepath=str(path),
            filename=path.name,
            preset_name=preset.name,
            scores=scores,
            passed_thresholds=True,
            was_truncated=False,
        )


def _make_preset(question_id: str = "clarity") -> PresetConfig:
    return PresetConfig(
        name="quality",
        title="Quality",
        description="Quality preset",
        questions={
            question_id: QuestionConfig(
                type="score",
                label="Clarity",
                instructions="Score clarity",
                criteria=["Low", "Medium", "High"],
                weight=1.0,
            )
        },
    )


# --- 1. get_t_crit_95 Acceptance Tests ---

def test_t_crit_degrees_of_freedom():
    assert get_t_crit_95(11) >= 2.20
    assert get_t_crit_95(13) >= 2.16
    assert get_t_crit_95(1) == 12.706
    assert get_t_crit_95(30) == 2.042
    # Intermediate fallback to smaller key (conservative)
    assert get_t_crit_95(35) == 2.042


# --- 2. Run pairing & Incomplete pairs ---

def test_incomplete_pair_run_lost(tmp_path):
    """When run 2 of after side lacks clarity, deltas come from runs 1 & 3 only and pair is incomplete."""
    f_before = tmp_path / "before.md"
    f_before.write_text("before text", encoding="utf-8")
    f_after = tmp_path / "after.md"
    f_after.write_text("after text", encoding="utf-8")

    class IncompleteFakeEvaluator:
        def __init__(self):
            self.calls = {str(f_before): 0, str(f_after): 0}

        def evaluate_document(self, filepath, preset, mask_secrets=True, max_chars=25000, dry_run=False):
            self.calls[filepath] += 1
            call_idx = self.calls[filepath]  # 1, 2, or 3

            if filepath == str(f_after) and call_idx == 2:
                # Run 2 for after side lacks clarity question
                return DocumentEvalResult(
                    filepath=filepath,
                    filename=Path(filepath).name,
                    preset_name="quality",
                    scores={},
                    passed_thresholds=True,
                )

            # Assign specific scores per call
            # run 1: before=0.8, after=0.6 -> delta=-0.2
            # run 2: before=0.8, after missing
            # run 3: before=0.8, after=0.5 -> delta=-0.3
            score = 0.8 if filepath == str(f_before) else (0.6 if call_idx == 1 else 0.5)
            return DocumentEvalResult(
                filepath=filepath,
                filename=Path(filepath).name,
                preset_name="quality",
                scores={
                    "clarity": ScoreResult(
                        score=score,
                        max_score=1.0,
                        normalized_score=score,
                        confidence=0.9,
                        probabilities={},
                    )
                },
                passed_thresholds=True,
            )

    evaluator = IncompleteFakeEvaluator()
    labels_cfg = ValidationLabelsConfig(
        preset="quality",
        runs=3,
        pairs=[
            ValidationPairExpectation(
                before=str(f_before),
                after=str(f_after),
                expect={"clarity": "down"},
            )
        ],
    )

    report, has_error = run_validation(
        labels_cfg=labels_cfg,
        base_dir=tmp_path,
        evaluator=evaluator,
        preset_cfg=_make_preset("clarity"),
    )

    assert len(report.pair_results) == 1
    p = report.pair_results[0]
    assert p.incomplete is True
    assert p.incomplete_runs == 1
    # Deltas come from runs 1 and 3 only
    assert len(p.deltas) == 2
    assert pytest.approx(p.deltas[0], abs=1e-4) == -0.2
    assert pytest.approx(p.deltas[1], abs=1e-4) == -0.3
    assert report.incomplete_pairs_count == 1


# --- 3. Zero pairs must not pass criteria ---

def test_zero_down_pairs_fails_min_degradation_drop(tmp_path):
    labels_cfg = ValidationLabelsConfig(
        preset="quality",
        runs=2,
        criteria=ValidationCriteria(min_degradation_drop=0.10),
        pairs=[],  # zero pairs
    )

    report, has_error = run_validation(
        labels_cfg=labels_cfg,
        base_dir=tmp_path,
        evaluator=FakeEvaluator(),
        preset_cfg=_make_preset("clarity"),
    )

    assert report.all_passed is False
    crit = next(c for c in report.criteria_results if c.name == "min_degradation_drop")
    assert crit.passed is False


# --- 4. Truncation excluded from gating ---

def test_truncation_excluded_from_gating(tmp_path):
    f_before = tmp_path / "before.md"
    f_before.write_text("before", encoding="utf-8")
    f_after = tmp_path / "after.md"
    f_after.write_text("after", encoding="utf-8")

    class TruncatedFakeEvaluator:
        def evaluate_document(self, filepath, preset, mask_secrets=True, max_chars=25000, dry_run=False):
            return DocumentEvalResult(
                filepath=filepath,
                filename=Path(filepath).name,
                preset_name="quality",
                scores={
                    "clarity": ScoreResult(
                        score=0.2 if "after" in filepath else 0.8,
                        max_score=1.0,
                        normalized_score=0.2 if "after" in filepath else 0.8,
                        confidence=0.9,
                        probabilities={},
                    )
                },
                passed_thresholds=True,
                was_truncated=("after" in filepath),
            )

    labels_cfg = ValidationLabelsConfig(
        preset="quality",
        runs=2,
        criteria=ValidationCriteria(min_degradation_drop=0.10),
        pairs=[
            ValidationPairExpectation(
                before=str(f_before),
                after=str(f_after),
                expect={"clarity": "down"},
            )
        ],
    )

    report, has_error = run_validation(
        labels_cfg=labels_cfg,
        base_dir=tmp_path,
        evaluator=TruncatedFakeEvaluator(),
        preset_cfg=_make_preset("clarity"),
    )

    p = report.pair_results[0]
    assert p.was_truncated is True
    assert report.truncated_pairs_count == 1
    # Because the only down pair was truncated and excluded from gating, active down pairs = 0, so min_degradation_drop fails
    assert report.all_passed is False


# --- 5. Caching & Run-Major Order ---

def test_cache_and_run_major_order_264_calls(tmp_path):
    """75 pairs × 3 runs over 13 distinct base files cost (13+75)×3 = 264 evaluator calls."""
    base_files = [tmp_path / f"base_{i}.md" for i in range(13)]
    for i, bf in enumerate(base_files):
        bf.write_text(f"Base file content {i}\n", encoding="utf-8")

    after_files = [tmp_path / f"after_{j}.md" for j in range(75)]
    for j, af in enumerate(after_files):
        af.write_text(f"After variant content {j}\n", encoding="utf-8")

    pairs = []
    for j in range(75):
        bf = base_files[j % 13]
        af = after_files[j]
        pairs.append(
            ValidationPairExpectation(
                before=str(bf),
                after=str(af),
                expect={"clarity": "down"},
            )
        )

    labels_cfg = ValidationLabelsConfig(
        preset="quality",
        runs=3,
        pairs=pairs,
    )

    preset = _make_preset("clarity")
    fake_eval = FakeEvaluator()

    report, has_error = run_validation(
        labels_cfg=labels_cfg,
        base_dir=tmp_path,
        evaluator=fake_eval,
        preset_cfg=preset,
    )

    # 13 base files + 75 variant files = 88 distinct files evaluated per run × 3 runs = 264 calls
    assert fake_eval.call_count == 264

    # Changing one character of a preset question instructions must miss the cache
    preset_changed = PresetConfig(
        name="quality",
        title="Quality",
        description="Quality preset",
        questions={
            "clarity": QuestionConfig(
                type="score",
                label="Clarity",
                instructions="Score clarity!",  # exclamation added
                criteria=["Low", "Medium", "High"],
                weight=1.0,
            )
        },
    )
    fake_eval_2 = FakeEvaluator()
    report2, has_error2 = run_validation(
        labels_cfg=labels_cfg,
        base_dir=tmp_path,
        evaluator=fake_eval_2,
        preset_cfg=preset_changed,
    )
    assert fake_eval_2.call_count == 264


# --- 6. Retry transient API errors ---

def test_retry_transient_api_errors(monkeypatch):
    """A client that fails twice with 503 and then succeeds does not lose the run."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy-key")
    evaluator = TypeSafeEvaluator()

    call_count = 0

    class MockSDKClient:
        def system_one(self, state, questions):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Raise 503 transient error
                exc = Exception("503 Service Unavailable")
                exc.status = 503
                raise exc

            # 3rd attempt succeeds
            mock_ans = MagicMock()
            mock_ans.score = 2.0
            mock_ans.confidence = 0.95
            mock_ans.probabilities = {}
            mock_resp = MagicMock()
            mock_resp.scores = {"clarity": mock_ans}
            mock_resp.nouls = {q: MagicMock(noul=0.1) for q in questions if q != "clarity"}
            mock_resp.choices = {}
            mock_resp.usage = None
            mock_resp.model = "test-model"
            return mock_resp

    evaluator._client = MockSDKClient()

    # Fast backoff for testing
    import typesafe_eval.client as client_mod
    orig_call = client_mod._call_system_one_with_retry

    def fast_call(client, state, questions, max_attempts=3, initial_backoff=0.001):
        return orig_call(client, state, questions, max_attempts, initial_backoff=0.001)

    monkeypatch.setattr(client_mod, "_call_system_one_with_retry", fast_call)

    doc_p = Path("tests/fixtures/leak_sample.txt")
    assert doc_p.exists()
    preset = _make_preset("clarity")
    res = evaluator.evaluate_document(str(doc_p), preset)
    assert call_count == 3
    assert "clarity" in res.scores


# --- 7. Group CI Gating Unit Tests (7 scenarios) ---

def _setup_group_scenario(tmp_path, pairs_data, criteria_kwargs):
    """Helper to set up files, labels config, and fake evaluator for group gating tests."""
    score_map = {}
    pair_expectations = []
    for idx, (kind, exp, before_val, after_val) in enumerate(pairs_data):
        bf = tmp_path / f"{kind}_{idx}_b.md"
        af = tmp_path / f"{kind}_{idx}_a.md"
        bf.write_text(f"before {idx}", encoding="utf-8")
        af.write_text(f"after {idx}", encoding="utf-8")
        score_map[str(bf)] = before_val
        score_map[str(af)] = after_val
        pair_expectations.append(
            ValidationPairExpectation(
                before=str(bf),
                after=str(af),
                kind=kind,
                expect={"clarity": exp},
            )
        )

    labels_cfg = ValidationLabelsConfig(
        preset="quality",
        runs=3,
        criteria=ValidationCriteria(group_by="kind", **criteria_kwargs),
        pairs=pair_expectations,
    )
    evaluator = FakeEvaluator(score_map)
    preset = _make_preset("clarity")
    report, has_error = run_validation(labels_cfg, tmp_path, evaluator, preset_cfg=preset)
    return report


def test_group_gating_down_group_passes(tmp_path):
    # 6 down pairs with means around -0.22 -> CI upper <= -0.10
    pairs_data = [
        ("shuffled", "down", 0.82, 0.60),  # -0.22
        ("shuffled", "down", 0.84, 0.60),  # -0.24
        ("shuffled", "down", 0.80, 0.60),  # -0.20
        ("shuffled", "down", 0.85, 0.60),  # -0.25
        ("shuffled", "down", 0.81, 0.60),  # -0.21
        ("shuffled", "down", 0.83, 0.60),  # -0.23
    ]
    report = _setup_group_scenario(
        tmp_path, pairs_data, {"degradation_ci_upper_max": -0.10, "min_group_size": 6}
    )
    grp = report.pair_group_results[0]
    assert grp.passed is True
    assert report.all_passed is True


def test_group_gating_down_group_fails_ci_but_all_means_negative(tmp_path):
    # 6 down pairs with means ~ -0.04 (all < 0), but CI upper > -0.10
    pairs_data = [
        ("shuffled", "down", 0.80, 0.76),  # -0.04
        ("shuffled", "down", 0.80, 0.75),  # -0.05
        ("shuffled", "down", 0.80, 0.77),  # -0.03
        ("shuffled", "down", 0.80, 0.74),  # -0.06
        ("shuffled", "down", 0.80, 0.78),  # -0.02
        ("shuffled", "down", 0.80, 0.76),  # -0.04
    ]
    report = _setup_group_scenario(
        tmp_path, pairs_data, {"degradation_ci_upper_max": -0.10, "min_group_size": 6}
    )
    grp = report.pair_group_results[0]
    assert grp.passed is False
    assert report.all_passed is False


def test_group_gating_neutral_group_inside_bound(tmp_path):
    # 6 neutral pairs with small deltas within ±0.015
    pairs_data = [
        ("paraphrase", "neutral", 0.80, 0.81),  # +0.01
        ("paraphrase", "neutral", 0.80, 0.79),  # -0.01
        ("paraphrase", "neutral", 0.80, 0.80),  # 0.00
        ("paraphrase", "neutral", 0.80, 0.81),  # +0.01
        ("paraphrase", "neutral", 0.80, 0.79),  # -0.01
        ("paraphrase", "neutral", 0.80, 0.80),  # 0.00
    ]
    report = _setup_group_scenario(
        tmp_path, pairs_data, {"neutral_ci_abs_max": 0.05, "min_group_size": 6}
    )
    grp = report.pair_group_results[0]
    assert grp.passed is True
    assert report.all_passed is True


def test_group_gating_neutral_group_ci_crosses_bound(tmp_path):
    # 6 neutral pairs with deltas ~ +0.045, CI upper crosses 0.05
    pairs_data = [
        ("paraphrase", "neutral", 0.80, 0.84),  # +0.04
        ("paraphrase", "neutral", 0.80, 0.85),  # +0.05
        ("paraphrase", "neutral", 0.80, 0.83),  # +0.03
        ("paraphrase", "neutral", 0.80, 0.86),  # +0.06
        ("paraphrase", "neutral", 0.80, 0.84),  # +0.04
        ("paraphrase", "neutral", 0.80, 0.85),  # +0.05
    ]
    report = _setup_group_scenario(
        tmp_path, pairs_data, {"neutral_ci_abs_max": 0.05, "min_group_size": 6}
    )
    grp = report.pair_group_results[0]
    assert grp.passed is False
    assert report.all_passed is False


def test_group_gating_below_min_group_size_gives_null(tmp_path):
    # Only 4 pairs < min_group_size=6
    pairs_data = [
        ("small_grp", "neutral", 0.80, 0.84),
        ("small_grp", "neutral", 0.80, 0.85),
        ("small_grp", "neutral", 0.80, 0.83),
        ("small_grp", "neutral", 0.80, 0.86),
    ]
    report = _setup_group_scenario(
        tmp_path, pairs_data, {"neutral_ci_abs_max": 0.05, "min_group_size": 6}
    )
    grp = report.pair_group_results[0]
    assert grp.passed is None
    # Does not gate: all_passed remains True
    assert report.all_passed is True


def test_group_gating_report_only_kind_does_not_gate(tmp_path):
    # Group with kind 'exploratory' fails CI, but is report-only
    pairs_data = [
        ("exploratory", "down", 0.80, 0.78),
        ("exploratory", "down", 0.80, 0.77),
        ("exploratory", "down", 0.80, 0.79),
        ("exploratory", "down", 0.80, 0.78),
        ("exploratory", "down", 0.80, 0.76),
        ("exploratory", "down", 0.80, 0.77),
    ]
    report = _setup_group_scenario(
        tmp_path,
        pairs_data,
        {
            "degradation_ci_upper_max": -0.10,
            "min_group_size": 6,
            "report_only_kinds": ["exploratory"],
        },
    )
    grp = report.pair_group_results[0]
    assert grp.passed is None
    assert report.all_passed is True


def test_group_gating_pair_guard_failing_on_one_extreme_pair(tmp_path):
    # 6 neutral pairs: 5 are 0.01, but 1 has delta = +0.15 > 0.10
    pairs_data = [
        ("paraphrase", "neutral", 0.80, 0.81),
        ("paraphrase", "neutral", 0.80, 0.81),
        ("paraphrase", "neutral", 0.80, 0.79),
        ("paraphrase", "neutral", 0.80, 0.80),
        ("paraphrase", "neutral", 0.80, 0.81),
        ("paraphrase", "neutral", 0.80, 0.95),  # delta = +0.15 fails pair guard 0.10
    ]
    report = _setup_group_scenario(
        tmp_path,
        pairs_data,
        {"pair_guard_neutral_abs_max": 0.10, "min_group_size": 6},
    )
    assert report.all_passed is False
    # Check that the extreme pair's own passed is False
    extreme_p = next(p for p in report.pair_results if pytest.approx(p.mean_delta, abs=1e-3) == 0.15)
    assert extreme_p.passed is False
    crit = next(c for c in report.criteria_results if c.name == "pair_guard_neutral_abs_max")
    assert crit.passed is False


def test_per_pair_kinds_passes_and_fails_overall_criteria(tmp_path):
    """per_pair_kinds with runs=10 gates on own run CI inside group_by: kind without min_group_size."""
    # Group: 'shuffled' (6 pairs, down, CI upper < -0.10)
    pairs_data = [
        ("shuffled", "down", 0.82, 0.60),
        ("shuffled", "down", 0.84, 0.60),
        ("shuffled", "down", 0.80, 0.60),
        ("shuffled", "down", 0.85, 0.60),
        ("shuffled", "down", 0.81, 0.60),
        ("shuffled", "down", 0.83, 0.60),
    ]
    pair_expectations = []
    score_map = {}
    for idx, (kind, exp, b_val, a_val) in enumerate(pairs_data):
        bf = tmp_path / f"{kind}_{idx}_b.md"
        af = tmp_path / f"{kind}_{idx}_a.md"
        bf.write_text(f"before {idx}", encoding="utf-8")
        af.write_text(f"after {idx}", encoding="utf-8")
        score_map[str(bf)] = b_val
        score_map[str(af)] = a_val
        pair_expectations.append(
            ValidationPairExpectation(
                before=str(bf),
                after=str(af),
                kind=kind,
                expect={"clarity": exp},
            )
        )

    # Add 1 paraphrase pair with runs=10
    para_b = tmp_path / "para_b.md"
    para_a = tmp_path / "para_a.md"
    para_b.write_text("before para", encoding="utf-8")
    para_a.write_text("after para", encoding="utf-8")
    score_map[str(para_b)] = 0.80
    score_map[str(para_a)] = 0.81
    pair_expectations.append(
        ValidationPairExpectation(
            before=str(para_b),
            after=str(para_a),
            kind="paraphrase",
            doc_id="doc_para",
            runs=10,
            expect={"clarity": "neutral"},
        )
    )

    labels_cfg = ValidationLabelsConfig(
        preset="quality",
        runs=3,
        criteria=ValidationCriteria(
            group_by="kind",
            degradation_ci_upper_max=-0.10,
            neutral_ci_abs_max=0.05,
            min_group_size=6,
            per_pair_kinds=["paraphrase"],
        ),
        pairs=pair_expectations,
    )
    evaluator = FakeEvaluator(score_map)
    preset = _make_preset("clarity")
    report = run_validation(labels_cfg, tmp_path, evaluator, preset_cfg=preset)[0]

    # Check rows in pair_group_results
    assert len(report.pair_group_results) == 2
    shuffled_grp = next(g for g in report.pair_group_results if g.kind == "shuffled")
    assert shuffled_grp.passed is True
    para_grp = next(g for g in report.pair_group_results if g.kind == "paraphrase")
    assert para_grp.n == 10
    assert para_grp.passed is True
    assert "[doc_para]" in para_grp.worst_pair_path
    assert report.all_passed is True

    # Now if paraphrase CI crosses 0.05 (e.g. delta = +0.06 > 0.05)
    score_map[str(para_a)] = 0.86
    evaluator_fail = FakeEvaluator(score_map)
    report_fail = run_validation(labels_cfg, tmp_path, evaluator_fail, preset_cfg=preset)[0]
    para_grp_fail = next(g for g in report_fail.pair_group_results if g.kind == "paraphrase")
    assert para_grp_fail.passed is False
    assert report_fail.all_passed is False


def test_labels_extra_keys_forbid_exits_2(tmp_path):
    """Labels file with typo in criteria or pair exits 2 before evaluation and names unknown key."""
    from click.testing import CliRunner
    from typesafe_eval.cli import main

    labels_content = """preset: design-doc
criteria:
  degradaton_ci_upper_max: -0.1
pairs:
  - before: foo.md
    after: bar.md
    expcet:
      clarity: down
"""
    labels_file = tmp_path / "bad_labels.yaml"
    labels_file.write_text(labels_content, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file), "--dry-run"])
    assert result.exit_code == 2
    assert "degradaton_ci_upper_max" in result.output
    assert "criteria" in result.output


def test_degradation_ci_upper_max_is_strict(tmp_path):
    """degradation_ci_upper_max uses strict < so an upper bound of exactly -0.125 fails."""
    # 1.0 - 0.125 = 0.875, exact in IEEE-754 binary floating point
    pairs_data = [
        ("shuffled", "down", 1.0, 0.875),
        ("shuffled", "down", 1.0, 0.875),
        ("shuffled", "down", 1.0, 0.875),
        ("shuffled", "down", 1.0, 0.875),
        ("shuffled", "down", 1.0, 0.875),
        ("shuffled", "down", 1.0, 0.875),
    ]
    report = _setup_group_scenario(
        tmp_path, pairs_data, {"degradation_ci_upper_max": -0.125, "min_group_size": 6}
    )
    grp = report.pair_group_results[0]
    assert grp.ci_95_upper == -0.125
    # Because < is strict, -0.125 < -0.125 is False (with <= it would be True)
    assert grp.passed is False
    assert report.all_passed is False


def test_worst_pair_path_includes_full_relative_path_and_doc_id(tmp_path):
    """worst_pair_path identifies document with relative path and doc_id."""
    sub_dir = tmp_path / "pairs" / "art_1"
    sub_dir.mkdir(parents=True)
    bf = sub_dir / "before.md"
    af = sub_dir / "after.md"
    bf.write_text("before", encoding="utf-8")
    af.write_text("after", encoding="utf-8")

    pair = ValidationPairExpectation(
        before="pairs/art_1/before.md",
        after="pairs/art_1/after.md",
        kind="paraphrase",
        doc_id="art_1",
        expect={"clarity": "neutral"},
    )
    labels_cfg = ValidationLabelsConfig(
        preset="quality",
        runs=3,
        criteria=ValidationCriteria(group_by="pair"),
        pairs=[pair],
    )
    evaluator = FakeEvaluator({str(bf): 0.80, str(af): 0.80})
    preset = _make_preset("clarity")
    report = run_validation(labels_cfg, tmp_path, evaluator, preset_cfg=preset)[0]
    grp = report.pair_group_results[0]
    assert "[art_1]" in grp.worst_pair_path
    assert "pairs/art_1/before.md" in grp.worst_pair_path
    assert "pairs/art_1/after.md" in grp.worst_pair_path


# --- 8. Feasibility Check Tests ---

def test_feasibility_check_missing_relative_file_exits_2(tmp_path):
    """Missing relative before/after file exits with code 2 and outputs path."""
    pairs_file = tmp_path / "pairs.json"
    pairs_data = [
        {
            "id": "pair_0",
            "doc_id": "doc_0",
            "before": "nonexistent_before.md",
            "after": "nonexistent_after.md",
        }
    ]
    pairs_file.write_text(json.dumps(pairs_data), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        run_feasibility(pairs_file=pairs_file, dry_run=True)
    assert exc_info.value.code == 2


def test_feasibility_check_pairs_and_doc_mutual_exclusion():
    """C: Passing --pairs together with --doc prints message to stderr and exits with code 2."""
    import subprocess
    import sys
    cmd = [
        sys.executable,
        "scripts/feasibility_check.py",
        "--pairs", "dummy_pairs.json",
        "--doc", "dummy_doc.md",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 2
    assert "error" in res.stderr.lower()
    assert "--pairs" in res.stderr and "--doc" in res.stderr


def test_feasibility_check_explicit_splits_and_injected_evaluator(tmp_path):
    """When every pair has explicit split ('tuning'/'heldout'), skip SEED shuffle and use injected evaluator."""
    b_file = tmp_path / "doc.md"
    b_file.write_text("# Doc\nSome text content\n", encoding="utf-8")

    pairs_data = [
        {"id": "p0", "doc_id": "art_1", "before": "doc.md", "after": "doc.md", "split": "tuning"},
        {"id": "p1", "doc_id": "art_2", "before": "doc.md", "after": "doc.md", "split": "tuning"},
        {"id": "p2", "doc_id": "art_3", "before": "doc.md", "after": "doc.md", "split": "heldout"},
        {"id": "p3", "doc_id": "art_4", "before": "doc.md", "after": "doc.md", "split": "heldout"},
        {"id": "p4", "doc_id": "art_5", "before": "doc.md", "after": "doc.md", "split": "heldout"},
    ]
    pairs_file = tmp_path / "pairs.json"
    pairs_file.write_text(json.dumps(pairs_data), encoding="utf-8")

    fake_eval = FakeEvaluator()
    res = run_feasibility(pairs_file=pairs_file, dry_run=True, evaluator=fake_eval)

    # Injected evaluator was called
    assert fake_eval.call_count > 0
    # Heldout contains the 3 explicit article docs (art_3, art_4, art_5)
    holdout_ids = {p["doc_id"] for p in res["pairs"] if p["is_holdout"]}
    assert holdout_ids == {"art_3", "art_4", "art_5"}
    assert len(holdout_ids) >= 3


def test_feasibility_check_heldout_present_gives_numbers(tmp_path):
    """When held-out docs exist, held_out_roc_auc and false alarm rate are numeric."""
    doc = tmp_path / "doc.md"
    doc.write_text("sample content", encoding="utf-8")
    pairs_data = [
        {"id": "p0", "doc_id": "d0", "doc_type": "article", "before": "doc.md", "after": "doc.md", "split": "tuning"},
        {"id": "p1", "doc_id": "d1", "doc_type": "article", "before": "doc.md", "after": "doc.md", "split": "heldout"},
    ]
    pairs_file = tmp_path / "pairs.json"
    pairs_file.write_text(json.dumps(pairs_data), encoding="utf-8")

    fake_eval = FakeEvaluator()
    res = run_feasibility(pairs_file=pairs_file, dry_run=True, evaluator=fake_eval)

    assert res["held_out_roc_auc"] is not None
    assert isinstance(res["held_out_roc_auc"], (int, float))
    assert res["held_out_published_false_alarm_rate"] is not None
    assert isinstance(res["held_out_published_false_alarm_rate"], (int, float))
    assert res["by_doc_type"]["article"]["held_out_roc_auc"] is not None
    assert res["by_doc_type"]["article"]["held_out_false_alarm_rate"] is not None


def test_feasibility_check_no_heldout_gives_nulls(tmp_path):
    """When no held-out docs exist, held_out_roc_auc and false alarm rate are None (null in JSON)."""
    doc = tmp_path / "doc.md"
    doc.write_text("sample content", encoding="utf-8")
    pairs_data = [
        {"id": "p0", "doc_id": "d0", "doc_type": "article", "before": "doc.md", "after": "doc.md", "split": "tuning"},
        {"id": "p1", "doc_id": "d1", "doc_type": "article", "before": "doc.md", "after": "doc.md", "split": "tuning"},
    ]
    pairs_file = tmp_path / "pairs.json"
    pairs_file.write_text(json.dumps(pairs_data), encoding="utf-8")

    fake_eval = FakeEvaluator()
    res = run_feasibility(pairs_file=pairs_file, dry_run=True, evaluator=fake_eval)

    assert res["held_out_roc_auc"] is None
    assert res["held_out_published_false_alarm_rate"] is None
    assert res["absolute_gate_feasible"] is False
    assert res["by_doc_type"]["article"]["held_out_roc_auc"] is None
    assert res["by_doc_type"]["article"]["held_out_false_alarm_rate"] is None
    assert res["by_doc_type"]["article"]["feasible"] is False


def test_group_by_kind_two_questions(tmp_path):
    """When a pair expectation specifies two score questions, kind grouping splits them into separate groups with correct n."""
    # Synthetic two-question config to test grouping by kind across multiple score questions.
    preset = PresetConfig(
        name="two-score",
        title="Tech Spec",
        description="Tech Spec preset",
        questions={
            "technical_depth": QuestionConfig(
                type="score",
                label="Technical Depth",
                instructions="Score depth",
                criteria=["Low", "High"],
                weight=1.0,
            ),
            "edge_case_coverage": QuestionConfig(
                type="score",
                label="Edge Case Coverage",
                instructions="Score edge cases",
                criteria=["Low", "High"],
                weight=1.0,
            ),
        },
    )

    pair_expectations = []
    score_map = {}
    for idx in range(10):
        bf = tmp_path / f"rm_{idx}_b.md"
        af = tmp_path / f"rm_{idx}_a.md"
        bf.write_text(f"before {idx}", encoding="utf-8")
        af.write_text(f"after {idx}", encoding="utf-8")
        score_map[str(bf)] = 0.8
        score_map[str(af)] = 0.6
        pair_expectations.append(
            ValidationPairExpectation(
                before=str(bf),
                after=str(af),
                kind="removed_middle",
                expect={"technical_depth": "down", "edge_case_coverage": "down"},
            )
        )

    labels_cfg = ValidationLabelsConfig(
        preset="two-score",
        runs=3,
        criteria=ValidationCriteria(
            group_by="kind",
            min_group_size=6,
            degradation_ci_upper_max=-0.10,
        ),
        pairs=pair_expectations,
    )
    evaluator = FakeEvaluator(score_map)
    report, has_error = run_validation(labels_cfg, tmp_path, evaluator, preset_cfg=preset)

    assert not has_error
    assert len(report.pair_group_results) == 2
    grp_depth = next(g for g in report.pair_group_results if g.question_id == "technical_depth")
    grp_edge = next(g for g in report.pair_group_results if g.question_id == "edge_case_coverage")

    assert grp_depth.kind == "removed_middle"
    assert grp_depth.n == 10
    assert grp_depth.passed is True
    assert pytest.approx(grp_depth.mean_delta, abs=1e-4) == -0.2

    assert grp_edge.kind == "removed_middle"
    assert grp_edge.n == 10
    assert grp_edge.passed is True
    assert pytest.approx(grp_edge.mean_delta, abs=1e-4) == -0.2


def test_pair_guard_down_tolerance_default(tmp_path):
    """Default tolerance 0.0: delta = 0.000 passes (equal), delta = +0.005 fails (above)."""
    # 1. Delta = 0.000 exactly passes boundary
    pairs_data_equal = [
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.50),  # delta = 0.000 (equal to tolerance)
    ]
    dir_equal = tmp_path / "equal"
    dir_equal.mkdir()
    report_equal = _setup_group_scenario(
        dir_equal,
        pairs_data_equal,
        {"pair_guard_neutral_abs_max": 0.10, "min_group_size": 6},
    )
    p_equal = next(p for p in report_equal.pair_results if pytest.approx(p.mean_delta, abs=1e-4) == 0.0)
    assert p_equal.passed is True
    crit_equal = next(c for c in report_equal.criteria_results if c.name == "pair_guard_neutral_abs_max")
    assert crit_equal.passed is True
    assert "down <= 0.000" in crit_equal.expected
    assert report_equal.all_passed is True

    # 2. Delta = +0.005 fails (above tolerance)
    pairs_data_above = [
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.505),  # delta = +0.005
    ]
    dir_above = tmp_path / "above"
    dir_above.mkdir()
    report_above = _setup_group_scenario(
        dir_above,
        pairs_data_above,
        {"pair_guard_neutral_abs_max": 0.10, "min_group_size": 6},
    )
    slight_up_p = next(p for p in report_above.pair_results if pytest.approx(p.mean_delta, abs=1e-4) == 0.005)
    assert slight_up_p.passed is False
    crit_above = next(c for c in report_above.criteria_results if c.name == "pair_guard_neutral_abs_max")
    assert crit_above.passed is False
    assert "down <= 0.000" in crit_above.expected
    assert report_above.all_passed is False


def test_pair_guard_down_tolerance_custom(tmp_path):
    """Tolerance 0.02: delta = +0.020 passes (equal), delta = +0.021 fails (just above)."""
    # Passes with delta = +0.020 (equal to tolerance)
    pairs_data_pass = [
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.0, 0.020),  # delta = +0.020 (equal to tolerance)
    ]
    dir_pass = tmp_path / "pass"
    dir_pass.mkdir()
    report_pass = _setup_group_scenario(
        dir_pass,
        pairs_data_pass,
        {"pair_guard_neutral_abs_max": 0.10, "pair_guard_down_tolerance": 0.02, "min_group_size": 6},
    )
    p_pass = next(p for p in report_pass.pair_results if pytest.approx(p.mean_delta, abs=1e-4) == 0.02)
    assert p_pass.passed is True
    crit_pass = next(c for c in report_pass.criteria_results if c.name == "pair_guard_neutral_abs_max")
    assert crit_pass.passed is True
    assert "down <= 0.020" in crit_pass.expected
    assert report_pass.all_passed is True

    # Fails with delta = +0.021 (just above tolerance)
    pairs_data_fail = [
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.50, 0.30),
        ("shuffled", "down", 0.0, 0.021),  # delta = +0.021 (> 0.02)
    ]
    dir_fail = tmp_path / "fail"
    dir_fail.mkdir()
    report_fail = _setup_group_scenario(
        dir_fail,
        pairs_data_fail,
        {"pair_guard_neutral_abs_max": 0.10, "pair_guard_down_tolerance": 0.02, "min_group_size": 6},
    )
    p_fail = next(p for p in report_fail.pair_results if pytest.approx(p.mean_delta, abs=1e-4) == 0.021)
    assert p_fail.passed is False
    crit_fail = next(c for c in report_fail.criteria_results if c.name == "pair_guard_neutral_abs_max")
    assert crit_fail.passed is False
    assert report_fail.all_passed is False

