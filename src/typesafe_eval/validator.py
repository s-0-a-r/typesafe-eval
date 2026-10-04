"""Validation engine, statistical metrics, labels runner, and ablation helper.

Implements `typesafe-eval validate` per Issue #38.
"""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Literal

import click
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.models import DocumentEvalResult
from typesafe_eval.presets import PresetConfig, load_preset

err_console = Console(stderr=True)
console = Console()


def is_unplaced_warning(msg: str) -> bool:
    """Matches unplaced warnings specifically containing 'were not found in any of the chunks',
    'were not found in any of <N> chunks', or similar unplaced warning signature.
    """
    if "not found in any of the chunks" in msg:
        return True
    if "were not found in any of" in msg and "chunk" in msg:
        return True
    if "not found in any" in msg and "chunk" in msg:
        return True
    return False


def get_t_crit_95(df: int) -> float:
    """Returns two-tailed 95% Student's t critical value for given degrees of freedom."""
    t_table = {
        1: 12.706,
        2: 4.303,
        3: 3.182,
        4: 2.776,
        5: 2.571,
        6: 2.447,
        7: 2.365,
        8: 2.306,
        9: 2.262,
        10: 2.228,
        11: 2.201,
        12: 2.179,
        13: 2.160,
        14: 2.145,
        15: 2.131,
        16: 2.120,
        17: 2.110,
        18: 2.101,
        19: 2.093,
        20: 2.086,
        21: 2.080,
        22: 2.074,
        23: 2.069,
        24: 2.064,
        25: 2.060,
        26: 2.056,
        27: 2.052,
        28: 2.048,
        29: 2.045,
        30: 2.042,
        40: 2.021,
        50: 2.009,
        60: 2.000,
        80: 1.990,
        100: 1.984,
        120: 1.980,
    }
    if df <= 0:
        return 1.960
    if df in t_table:
        return t_table[df]
    # Fall back to next smaller key (conservative: higher t critical value)
    for k in sorted(t_table.keys(), reverse=True):
        if df >= k:
            return t_table[k]
    return 1.960


def compute_ci_95(deltas: list[float]) -> tuple[float, float, float]:
    """Computes mean delta, and lower/upper bounds of 95% confidence interval."""
    n = len(deltas)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean_val = sum(deltas) / n
    if n == 1:
        return mean_val, mean_val, mean_val
    variance = sum((x - mean_val) ** 2 for x in deltas) / (n - 1)
    std_dev = math.sqrt(variance)
    se = std_dev / math.sqrt(n)
    t_crit = get_t_crit_95(n - 1)
    margin = t_crit * se
    return mean_val, mean_val - margin, mean_val + margin


# --- Schema for labels.yaml ---


class ValidationDocumentExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    expect: dict[str, Literal["present", "absent"]]


class ValidationPairExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    before: str
    after: str
    expect: dict[str, Literal["down", "neutral"]]
    kind: str | None = None
    doc_id: str | None = None
    runs: int | None = None


class QuestionCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_detected: int | float | None = None
    max_false_alarms: int | float | None = None
    max_neutral_delta: float | None = None
    min_degradation_drop: float | None = None
    max_spread: float | None = None


class ValidationCriteria(QuestionCriteria):
    model_config = ConfigDict(extra="forbid")
    group_by: Literal["kind", "pair"] = "pair"
    degradation_ci_upper_max: float | None = None
    neutral_ci_abs_max: float | None = None
    min_group_size: int = 6
    pair_guard_neutral_abs_max: float | None = None
    pair_guard_down_tolerance: float = 0.0
    report_only_kinds: list[str] = Field(default_factory=list)
    per_pair_kinds: list[str] = Field(default_factory=list)


class ValidationLabelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: str | None = None
    config: str | None = None
    runs: int = 3
    criteria: ValidationCriteria | None = None
    documents: list[ValidationDocumentExpectation] = Field(default_factory=list)
    pairs: list[ValidationPairExpectation] = Field(default_factory=list)


# --- Results Models ---


class DocumentPresenceResult(BaseModel):
    path: str
    question_id: str
    expected: Literal["present", "absent"]
    probabilities: list[float]
    spread: float
    verdict: Literal["detected", "missed", "correct_present", "false_alarm"]


class PairScoreResult(BaseModel):
    before_path: str
    after_path: str
    question_id: str
    expected: Literal["down", "neutral"]
    kind: str | None = None
    doc_id: str | None = None
    before_scores: list[float]
    after_scores: list[float]
    deltas: list[float]
    mean_delta: float
    ci_95_lower: float
    ci_95_upper: float
    passed: bool
    incomplete: bool = False
    incomplete_runs: int = 0
    was_truncated_before: bool = False
    was_truncated_after: bool = False
    was_truncated: bool = False


class PairGroupResult(BaseModel):
    kind: str
    question_id: str | None = None
    expected: Literal["down", "neutral"]
    n: int
    mean_delta: float
    ci_95_lower: float
    ci_95_upper: float
    passed: bool | None = None
    worst_pair_path: str
    worst_pair_delta: float


class QuestionValidationStats(BaseModel):
    question_id: str
    type: Literal["noul", "score"]
    total_absent_expected: int = 0
    detected_count: int = 0
    missed_count: int = 0
    total_present_expected: int = 0
    false_alarm_count: int = 0
    max_spread: float = 0.0
    mean_delta: float | None = None
    ci_95: tuple[float, float] | None = None
    pairs_count: int = 0


class CriterionEvaluationResult(BaseModel):
    name: str
    expected: Any
    actual: Any
    passed: bool | None = None
    message: str


class ValidationReport(BaseModel):
    schema_version: str = "1.0"
    preset_name: str
    runs: int
    all_passed: bool | None = None
    summary: dict[str, Any]
    presence_results: list[DocumentPresenceResult] = Field(default_factory=list)
    pair_results: list[PairScoreResult] = Field(default_factory=list)
    pair_group_results: list[PairGroupResult] = Field(default_factory=list)
    incomplete_pairs_count: int = 0
    truncated_pairs_count: int = 0
    question_stats: dict[str, QuestionValidationStats] = Field(default_factory=dict)
    criteria_results: list[CriterionEvaluationResult] = Field(default_factory=list)
    choice_distributions: dict[str, dict[str, int]] = Field(default_factory=dict)
    unplaced_warnings: list[str] = Field(default_factory=list)
    mock: bool = False


# --- Execution Engine ---


def load_labels_file(labels_path: str | Path) -> tuple[ValidationLabelsConfig, Path]:
    """Loads and validates a labels.yaml configuration file."""
    path = Path(labels_path)
    if not path.is_file():
        raise FileNotFoundError(f"Labels file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid labels configuration in {path}: expected YAML mapping")

    # Check document label values before evaluation
    for doc in data.get("documents", []):
        if isinstance(doc, dict):
            d_path = doc.get("path", "<unknown>")
            expect_map = doc.get("expect", {})
            if isinstance(expect_map, dict):
                for q_id, val in expect_map.items():
                    if val not in ("present", "absent"):
                        raise ValueError(
                            f"Invalid expectation '{val}' for question '{q_id}' in document '{d_path}': must be 'present' or 'absent'"
                        )

    try:
        config = ValidationLabelsConfig(**data)
    except ValidationError as e:
        err_msgs = []
        for err in e.errors():
            loc_parts = [str(x) for x in err.get("loc", ())]
            loc_str = " -> ".join(loc_parts) if loc_parts else "root"
            msg = err.get("msg", "Validation error")
            err_msgs.append(f"{loc_str}: {msg}")
        raise ValueError(f"Invalid labels configuration in {path}:\n" + "\n".join(err_msgs)) from e
    return config, path.parent


def resolve_file_path(base_dir: Path, target_path: str) -> Path:
    """Resolves path relative to base_dir, falling back to CWD."""
    p = Path(target_path)
    if p.is_absolute():
        return p
    if (base_dir / p).exists():
        return base_dir / p
    return p


def validate_labels_preset(
    labels_cfg: ValidationLabelsConfig,
    base_dir: Path,
) -> PresetConfig:
    """Loads and validates preset and question IDs for a labels config."""
    target_preset = labels_cfg.config or labels_cfg.preset or "quality"
    if labels_cfg.config:
        resolved_cfg_path = resolve_file_path(base_dir, labels_cfg.config)
        preset_cfg = load_preset(str(resolved_cfg_path))
    else:
        preset_cfg = load_preset(target_preset)

    # Validate question IDs against preset
    label_q_ids = set()
    for doc_item in labels_cfg.documents:
        label_q_ids.update(doc_item.expect.keys())
    for pair_item in labels_cfg.pairs:
        label_q_ids.update(pair_item.expect.keys())

    preset_q_ids = set(preset_cfg.questions.keys())
    unknown_q_ids = sorted(label_q_ids - preset_q_ids)
    if unknown_q_ids:
        raise ValueError(
            f"Labels file contains unknown question ID(s): {', '.join(unknown_q_ids)}. "
            f"Available question ID(s) in preset '{preset_cfg.name}': {', '.join(sorted(preset_q_ids))}."
        )

    # Check for invalid labels on choice questions
    for q_id in sorted(label_q_ids):
        if q_id in preset_cfg.questions:
            q_cfg = preset_cfg.questions[q_id]
            if q_cfg.type == "choice":
                raise ValueError(
                    f"{q_id} is a choice question; its distribution is recorded automatically, do not label it"
                )

    return preset_cfg


def compute_questions_hash(preset: PresetConfig) -> str:
    """Computes a deterministic SHA256 hash of preset questions for cache keys."""
    dump = {}
    for q_id, q_cfg in sorted(preset.questions.items()):
        dump[q_id] = {
            "type": q_cfg.type,
            "instructions": q_cfg.instructions,
            "criteria": q_cfg.criteria,
            "label": q_cfg.label,
            "weight": q_cfg.weight,
            "min_threshold": q_cfg.min_threshold,
            "max_threshold": q_cfg.max_threshold,
            "preflight": q_cfg.preflight,
        }
    return hashlib.sha256(json.dumps(dump, sort_keys=True).encode("utf-8")).hexdigest()


def run_validation(
    labels_cfg: ValidationLabelsConfig,
    base_dir: Path,
    evaluator: TypeSafeEvaluator,
    runs_override: int | None = None,
    dry_run: bool = False,
    preset_cfg: PresetConfig | None = None,
    mask_secrets: bool = True,
) -> tuple[ValidationReport, bool]:
    """Runs validation over documents and pairs across N runs."""
    runs = runs_override if runs_override is not None else labels_cfg.runs
    if runs < 1:
        runs = 1

    if preset_cfg is None:
        preset_cfg = validate_labels_preset(labels_cfg, base_dir)

    presence_results: list[DocumentPresenceResult] = []
    pair_results: list[PairScoreResult] = []
    choice_distributions: dict[str, dict[str, int]] = {}
    unplaced_warnings: list[str] = []
    has_runtime_error = False

    def _check_unplaced(
        res_obj: DocumentEvalResult, doc_label: str, r_idx: int, n_runs: int
    ) -> None:
        nonlocal has_runtime_error
        for w in res_obj.warnings:
            if is_unplaced_warning(w):
                formatted = f"{doc_label}: {w}" if not w.startswith(f"{doc_label}:") else w
                if formatted not in unplaced_warnings:
                    unplaced_warnings.append(formatted)
                if mask_secrets:
                    click.echo(
                        f"{doc_label} (run {r_idx + 1}/{n_runs}): Unplaced item in masked mode: {w}",
                        err=True,
                    )
                    has_runtime_error = True

    # Cache for unchanged file evaluations within this validate run
    # Key: (resolved_path, file_sha256, questions_hash, mask_secrets, run_index)
    eval_cache: dict[tuple[str, str, str, bool, int], DocumentEvalResult] = {}

    questions_hash = compute_questions_hash(preset_cfg)

    def _eval_cached(fpath: Path, r_idx: int) -> DocumentEvalResult:
        resolved = fpath.resolve()
        raw_bytes = resolved.read_bytes()
        f_hash = hashlib.sha256(raw_bytes).hexdigest()
        cache_key = (str(resolved), f_hash, questions_hash, bool(mask_secrets), r_idx)
        if cache_key not in eval_cache:
            eval_cache[cache_key] = evaluator.evaluate_document(
                filepath=str(resolved),
                preset=preset_cfg,
                mask_secrets=mask_secrets,
                dry_run=dry_run,
            )
        return eval_cache[cache_key]

    def _extract_q_val(res: DocumentEvalResult, q_id: str) -> float | None:
        if q_id in res.scores:
            return res.scores[q_id].normalized_score
        elif q_id in res.nouls and res.nouls[q_id].probability is not None:
            return res.nouls[q_id].probability
        return None

    # Determine max runs across file-level and per-pair overrides
    pair_runs_list = [p.runs if p.runs is not None else runs for p in labels_cfg.pairs]
    max_runs = max([runs] + pair_runs_list) if (labels_cfg.documents or labels_cfg.pairs) else runs

    # Run-major evaluation: doc_idx -> run_idx -> DocumentEvalResult
    doc_eval_runs: dict[int, dict[int, DocumentEvalResult]] = {
        i: {} for i in range(len(labels_cfg.documents))
    }
    # pair_idx -> run_idx -> (res_b, res_a)
    pair_eval_runs: dict[int, dict[int, tuple[DocumentEvalResult, DocumentEvalResult]]] = {
        i: {} for i in range(len(labels_cfg.pairs))
    }

    for r in range(max_runs):
        # 1. Presence documents for run r
        if r < runs:
            for d_idx, doc_item in enumerate(labels_cfg.documents):
                doc_path = resolve_file_path(base_dir, doc_item.path)
                try:
                    res = _eval_cached(doc_path, r)
                    doc_eval_runs[d_idx][r] = res
                    for ch_qid, ch_obj in res.choices.items():
                        q_dist = choice_distributions.setdefault(ch_qid, {})
                        q_dist[ch_obj.choice] = q_dist.get(ch_obj.choice, 0) + 1
                    _check_unplaced(res, str(doc_item.path), r, runs)
                except Exception as e:
                    click.echo(f"{doc_path} (run {r + 1}/{runs}): {e}", err=True)
                    has_runtime_error = True

        # 2. Pairs for run r
        for p_idx, pair_item in enumerate(labels_cfg.pairs):
            p_runs = pair_runs_list[p_idx]
            if r < p_runs:
                before_path = resolve_file_path(base_dir, pair_item.before)
                after_path = resolve_file_path(base_dir, pair_item.after)
                try:
                    res_b = _eval_cached(before_path, r)
                    res_a = _eval_cached(after_path, r)
                    pair_eval_runs[p_idx][r] = (res_b, res_a)
                    for res_item in (res_b, res_a):
                        for ch_qid, ch_obj in res_item.choices.items():
                            q_dist = choice_distributions.setdefault(ch_qid, {})
                            q_dist[ch_obj.choice] = q_dist.get(ch_obj.choice, 0) + 1
                    _check_unplaced(res_b, str(pair_item.before), r, p_runs)
                    _check_unplaced(res_a, str(pair_item.after), r, p_runs)
                except Exception as e:
                    click.echo(
                        f"Pair ({pair_item.before} -> {pair_item.after}, run {r + 1}/{p_runs}): {e}",
                        err=True,
                    )
                    has_runtime_error = True

    # Process presence document results
    for d_idx, doc_item in enumerate(labels_cfg.documents):
        doc_path = resolve_file_path(base_dir, doc_item.path)
        probs_by_question: dict[str, list[float]] = {q: [] for q in doc_item.expect}

        for r in range(runs):
            if r not in doc_eval_runs[d_idx]:
                continue
            res = doc_eval_runs[d_idx][r]
            for q_id in doc_item.expect:
                if q_id in res.nouls:
                    noul_obj = res.nouls[q_id]
                    q_cfg = preset_cfg.questions.get(q_id)
                    is_max_threshold = bool(q_cfg and q_cfg.max_threshold is not None)
                    threshold = (
                        q_cfg.max_threshold
                        if is_max_threshold
                        else (
                            q_cfg.min_threshold
                            if q_cfg and q_cfg.min_threshold is not None
                            else 0.5
                        )
                    )

                    has_cand_violation = False
                    if q_id == "has_pii":
                        has_cand_violation = (
                            any(e.outcome == "personal" for e in res.email_evaluations)
                            or any(p.outcome == "personal" for p in res.phone_evaluations)
                            or any(i.outcome == "sensitive" for i in res.ip_evaluations)
                            or any(u.outcome == "sensitive" for u in res.url_evaluations)
                        )
                    elif q_id == "has_secrets":
                        has_cand_violation = any(
                            s.outcome == "secret" for s in res.secret_evaluations
                        )

                    is_preflight = noul_obj.overridden_by is not None
                    if has_cand_violation or is_preflight:
                        p_val = (
                            max(noul_obj.probability, 1.0)
                            if noul_obj.probability is not None
                            else 1.0
                        )
                        probs_by_question[q_id].append(p_val)
                    elif noul_obj.probability is not None:
                        probs_by_question[q_id].append(noul_obj.probability)
                    else:
                        click.echo(
                            f"{doc_path} (run {r + 1}/{runs}): Question '{q_id}' probability is None without preflight decision",
                            err=True,
                        )
                        has_runtime_error = True
                elif q_id in res.scores:
                    probs_by_question[q_id].append(res.scores[q_id].normalized_score)
                else:
                    click.echo(
                        f"{doc_path} (run {r + 1}/{runs}): Question '{q_id}' was not returned by evaluator",
                        err=True,
                    )
                    has_runtime_error = True

        for q_id, expected in doc_item.expect.items():
            probs = probs_by_question[q_id]
            if not probs:
                continue

            q_cfg = preset_cfg.questions.get(q_id)
            is_max_threshold = bool(q_cfg and q_cfg.max_threshold is not None)

            if is_max_threshold:
                threshold = q_cfg.max_threshold

                def is_absent(p: float, t: float = threshold) -> bool:
                    return p <= t
            else:
                threshold = (
                    q_cfg.min_threshold if (q_cfg and q_cfg.min_threshold is not None) else 0.5
                )

                def is_absent(p: float, t: float = threshold) -> bool:
                    return p < t

            spread = max(probs) - min(probs) if probs else 0.0

            if expected == "absent":
                if all(is_absent(p) for p in probs):
                    verdict = "detected"
                else:
                    verdict = "missed"
            else:
                if any(is_absent(p) for p in probs):
                    verdict = "false_alarm"
                else:
                    verdict = "correct_present"

            presence_results.append(
                DocumentPresenceResult(
                    path=str(doc_item.path),
                    question_id=q_id,
                    expected=expected,
                    probabilities=probs,
                    spread=spread,
                    verdict=verdict,
                )
            )

    crit_cfg = labels_cfg.criteria

    # Process pairs: pairing only runs where both sides evaluated the question
    for p_idx, pair_item in enumerate(labels_cfg.pairs):
        p_runs = pair_runs_list[p_idx]
        for q_id, expected in pair_item.expect.items():
            valid_runs: list[tuple[float, float]] = []
            has_trunc_b = False
            has_trunc_a = False

            for r in range(p_runs):
                if r in pair_eval_runs[p_idx]:
                    res_b, res_a = pair_eval_runs[p_idx][r]
                    if res_b.was_truncated:
                        has_trunc_b = True
                    if res_a.was_truncated:
                        has_trunc_a = True

                    val_b = _extract_q_val(res_b, q_id)
                    val_a = _extract_q_val(res_a, q_id)

                    if val_b is not None and val_a is not None:
                        valid_runs.append((val_b, val_a))
                    else:
                        click.echo(
                            f"Pair ({pair_item.before} -> {pair_item.after}, run {r + 1}/{p_runs}): Question '{q_id}' not returned in pair",
                            err=True,
                        )
                        has_runtime_error = True

            incomplete = len(valid_runs) < p_runs
            incomplete_runs = p_runs - len(valid_runs)
            was_truncated = has_trunc_b or has_trunc_a

            b_list = [b for b, a in valid_runs]
            a_list = [a for b, a in valid_runs]
            deltas = [a - b for b, a in valid_runs]
            mean_d, ci_low, ci_high = compute_ci_95(deltas)

            # Determine each pair's own passed status via the pair guard
            if expected == "down":
                guard_down_tol = (
                    crit_cfg.pair_guard_down_tolerance
                    if crit_cfg and crit_cfg.pair_guard_down_tolerance is not None
                    else 0.0
                )
                pair_passed = mean_d <= guard_down_tol
            else:
                guard_neutral = (
                    crit_cfg.pair_guard_neutral_abs_max
                    if crit_cfg and crit_cfg.pair_guard_neutral_abs_max is not None
                    else (
                        crit_cfg.max_neutral_delta
                        if crit_cfg and crit_cfg.max_neutral_delta is not None
                        else 0.05
                    )
                )
                pair_passed = abs(mean_d) <= guard_neutral

            pair_results.append(
                PairScoreResult(
                    before_path=str(pair_item.before),
                    after_path=str(pair_item.after),
                    question_id=q_id,
                    expected=expected,
                    kind=pair_item.kind,
                    doc_id=pair_item.doc_id,
                    before_scores=b_list,
                    after_scores=a_list,
                    deltas=deltas,
                    mean_delta=mean_d,
                    ci_95_lower=ci_low,
                    ci_95_upper=ci_high,
                    passed=pair_passed,
                    incomplete=incomplete,
                    incomplete_runs=incomplete_runs,
                    was_truncated_before=has_trunc_b,
                    was_truncated_after=has_trunc_a,
                    was_truncated=was_truncated,
                )
            )

    incomplete_pairs_count = sum(1 for p in pair_results if p.incomplete)
    truncated_pairs_count = sum(1 for p in pair_results if p.was_truncated)

    # 3. Aggregate per-question statistics (across all active pairs for each question)
    question_stats: dict[str, QuestionValidationStats] = {}

    for pr in presence_results:
        q_id = pr.question_id
        if q_id not in question_stats:
            question_stats[q_id] = QuestionValidationStats(question_id=q_id, type="noul")
        stat = question_stats[q_id]
        if pr.expected == "absent":
            stat.total_absent_expected += 1
            if pr.verdict == "detected":
                stat.detected_count += 1
            else:
                stat.missed_count += 1
        else:
            stat.total_present_expected += 1
            if pr.verdict == "false_alarm":
                stat.false_alarm_count += 1
        stat.max_spread = max(stat.max_spread, pr.spread)

    # Question stats for score questions: compute aggregate across all active pair mean deltas
    score_q_ids = {p.question_id for p in pair_results}
    for q_id in sorted(score_q_ids):
        q_active_pairs = [
            p
            for p in pair_results
            if p.question_id == q_id and not p.incomplete and not p.was_truncated
        ]
        if q_id not in question_stats:
            question_stats[q_id] = QuestionValidationStats(question_id=q_id, type="score")
        stat = question_stats[q_id]
        stat.pairs_count = len(q_active_pairs)
        if q_active_pairs:
            pair_means = [p.mean_delta for p in q_active_pairs]
            m_val, lo_val, hi_val = compute_ci_95(pair_means)
            stat.mean_delta = m_val
            stat.ci_95 = (lo_val, hi_val)
        else:
            stat.mean_delta = None
            stat.ci_95 = None

    # 4. Grouping & Pair Group Results
    pair_group_results: list[PairGroupResult] = []
    group_by = crit_cfg.group_by if crit_cfg else "pair"
    report_only = set(crit_cfg.report_only_kinds) if crit_cfg else set()
    per_pair_kinds = set(crit_cfg.per_pair_kinds) if crit_cfg else set()
    min_grp_size = crit_cfg.min_group_size if crit_cfg else 6

    def _eval_pair_ci_passed(p: PairScoreResult) -> bool | None:
        if p.incomplete or p.was_truncated or (p.kind and p.kind in report_only):
            return None
        if p.expected == "down":
            if crit_cfg and crit_cfg.degradation_ci_upper_max is not None:
                return p.ci_95_upper < crit_cfg.degradation_ci_upper_max
            elif crit_cfg and crit_cfg.min_degradation_drop is not None:
                return p.mean_delta <= -crit_cfg.min_degradation_drop
            else:
                return p.mean_delta < 0.0
        else:
            if crit_cfg and crit_cfg.neutral_ci_abs_max is not None:
                return max(abs(p.ci_95_lower), abs(p.ci_95_upper)) <= crit_cfg.neutral_ci_abs_max
            elif crit_cfg and crit_cfg.max_neutral_delta is not None:
                return abs(p.mean_delta) <= crit_cfg.max_neutral_delta
            else:
                return abs(p.mean_delta) <= 0.05

    if group_by == "kind":
        # Separate per_pair_kinds and regular kind-grouped pairs
        regular_pairs = [p for p in pair_results if not (p.kind and p.kind in per_pair_kinds)]
        per_pair_items = [p for p in pair_results if p.kind and p.kind in per_pair_kinds]

        groups_dict: dict[tuple[str, str], list[PairScoreResult]] = {}
        for p in regular_pairs:
            k = p.kind or "default"
            groups_dict.setdefault((k, p.question_id), []).append(p)

        for (grp_kind, grp_qid), grp_pairs in groups_dict.items():
            exp = grp_pairs[0].expected
            active_pairs = [p for p in grp_pairs if not p.incomplete and not p.was_truncated]
            n = len(active_pairs)

            candidate_worst = active_pairs if active_pairs else grp_pairs
            if exp == "down":
                worst_p = max(candidate_worst, key=lambda p: p.mean_delta)
            else:
                worst_p = max(candidate_worst, key=lambda p: abs(p.mean_delta))
            worst_path = (
                f"[{worst_p.doc_id}] {worst_p.before_path} → {worst_p.after_path}"
                if worst_p.doc_id
                else f"{worst_p.before_path} → {worst_p.after_path}"
            )
            worst_delta = worst_p.mean_delta

            if n == 0:
                grp_mean, ci_lo, ci_hi = 0.0, 0.0, 0.0
                grp_passed = None
            else:
                pair_means = [p.mean_delta for p in active_pairs]
                grp_mean, ci_lo, ci_hi = compute_ci_95(pair_means)

                if n < min_grp_size or grp_kind in report_only:
                    grp_passed = None
                else:
                    if exp == "down":
                        if crit_cfg and crit_cfg.degradation_ci_upper_max is not None:
                            grp_passed = ci_hi < crit_cfg.degradation_ci_upper_max
                        elif crit_cfg and crit_cfg.min_degradation_drop is not None:
                            grp_passed = grp_mean <= -crit_cfg.min_degradation_drop
                        else:
                            grp_passed = grp_mean < 0.0
                    else:
                        if crit_cfg and crit_cfg.neutral_ci_abs_max is not None:
                            grp_passed = max(abs(ci_lo), abs(ci_hi)) <= crit_cfg.neutral_ci_abs_max
                        elif crit_cfg and crit_cfg.max_neutral_delta is not None:
                            grp_passed = abs(grp_mean) <= crit_cfg.max_neutral_delta
                        else:
                            grp_passed = abs(grp_mean) <= 0.05

            pair_group_results.append(
                PairGroupResult(
                    kind=grp_kind,
                    question_id=grp_qid,
                    expected=exp,
                    n=n,
                    mean_delta=grp_mean,
                    ci_95_lower=ci_lo,
                    ci_95_upper=ci_hi,
                    passed=grp_passed,
                    worst_pair_path=worst_path,
                    worst_pair_delta=worst_delta,
                )
            )

        # per_pair_kinds: each pair reported as own row, n = runs, not subject to min_group_size
        for p in per_pair_items:
            exp = p.expected
            pair_label = f"[{p.doc_id}] {p.after_path}" if p.doc_id else p.after_path
            grp_passed = _eval_pair_ci_passed(p)
            pair_group_results.append(
                PairGroupResult(
                    kind=p.kind,
                    question_id=p.question_id,
                    expected=exp,
                    n=len(p.deltas),
                    mean_delta=p.mean_delta,
                    ci_95_lower=p.ci_95_lower,
                    ci_95_upper=p.ci_95_upper,
                    passed=grp_passed,
                    worst_pair_path=pair_label,
                    worst_pair_delta=p.mean_delta,
                )
            )
    else:
        # group_by == "pair": each pair is treated as a group of n=runs evaluated on its own run CI
        for p in pair_results:
            exp = p.expected
            pair_name = (
                f"[{p.doc_id}] {p.before_path} → {p.after_path}"
                if p.doc_id
                else f"{p.before_path} → {p.after_path}"
            )
            k = p.kind or pair_name
            grp_passed = _eval_pair_ci_passed(p)

            pair_group_results.append(
                PairGroupResult(
                    kind=k,
                    question_id=p.question_id,
                    expected=exp,
                    n=len(p.deltas),
                    mean_delta=p.mean_delta,
                    ci_95_lower=p.ci_95_lower,
                    ci_95_upper=p.ci_95_upper,
                    passed=grp_passed,
                    worst_pair_path=pair_name,
                    worst_pair_delta=p.mean_delta,
                )
            )

    # 5. Evaluate Pass Criteria
    criteria_results: list[CriterionEvaluationResult] = []
    all_criteria_passed = True

    total_absent = sum(s.total_absent_expected for s in question_stats.values())
    total_detected = sum(s.detected_count for s in question_stats.values())
    total_present = sum(s.total_present_expected for s in question_stats.values())
    total_false_alarms = sum(s.false_alarm_count for s in question_stats.values())

    if crit_cfg:
        # min_detected
        if crit_cfg.min_detected is not None:
            exp_det = crit_cfg.min_detected
            if isinstance(exp_det, float) and exp_det <= 1.0:
                act_det_rate = (total_detected / total_absent) if total_absent > 0 else 0.0
                passed = act_det_rate >= exp_det
                criteria_results.append(
                    CriterionEvaluationResult(
                        name="min_detected (rate)",
                        expected=f"{exp_det * 100:.0f}%",
                        actual=f"{act_det_rate * 100:.1f}% ({total_detected}/{total_absent})",
                        passed=None if dry_run else passed,
                        message=f"Detected {total_detected}/{total_absent} absent items",
                    )
                )
            else:
                passed = total_detected >= int(exp_det)
                criteria_results.append(
                    CriterionEvaluationResult(
                        name="min_detected (count)",
                        expected=int(exp_det),
                        actual=f"{total_detected}/{total_absent}",
                        passed=None if dry_run else passed,
                        message=f"Detected {total_detected} absent items (required >= {int(exp_det)})",
                    )
                )
            if not passed:
                all_criteria_passed = False

        # max_false_alarms
        if crit_cfg.max_false_alarms is not None:
            exp_fa = crit_cfg.max_false_alarms
            passed = total_false_alarms <= int(exp_fa)
            criteria_results.append(
                CriterionEvaluationResult(
                    name="max_false_alarms",
                    expected=int(exp_fa),
                    actual=f"{total_false_alarms}/{total_present}",
                    passed=None if dry_run else passed,
                    message=f"False alarms {total_false_alarms} (allowed <= {int(exp_fa)})",
                )
            )
            if not passed:
                all_criteria_passed = False

        # max_neutral_delta (applies to active gating neutral pairs; zero pairs must not pass)
        if crit_cfg.max_neutral_delta is not None:
            active_neutrals = [
                p
                for p in pair_results
                if p.expected == "neutral"
                and not p.incomplete
                and not p.was_truncated
                and (not p.kind or p.kind not in report_only)
            ]
            if len(active_neutrals) == 0:
                passed = False
                act_str = "no active neutral pairs"
            else:
                max_act_neutral = max(abs(p.mean_delta) for p in active_neutrals)
                passed = max_act_neutral <= crit_cfg.max_neutral_delta
                act_str = f"{max_act_neutral:.3f}"
            criteria_results.append(
                CriterionEvaluationResult(
                    name="max_neutral_delta",
                    expected=f"<= {crit_cfg.max_neutral_delta:.3f}",
                    actual=act_str,
                    passed=None if dry_run else passed,
                    message=f"Max neutral delta check ({act_str})",
                )
            )
            if not passed:
                all_criteria_passed = False

        # min_degradation_drop (applies to active gating down pairs; zero pairs must not pass)
        if crit_cfg.min_degradation_drop is not None:
            active_downs = [
                p
                for p in pair_results
                if p.expected == "down"
                and not p.incomplete
                and not p.was_truncated
                and (not p.kind or p.kind not in report_only)
            ]
            min_drop = crit_cfg.min_degradation_drop
            if len(active_downs) == 0:
                passed = False
                act_str = "no active down pairs"
            else:
                passed = all(p.mean_delta <= -min_drop for p in active_downs)
                max_delta = max((p.mean_delta for p in active_downs), default=0.0)
                act_str = f"max delta {max_delta:.3f}"
            criteria_results.append(
                CriterionEvaluationResult(
                    name="min_degradation_drop",
                    expected=f"<= -{min_drop:.3f}",
                    actual=act_str,
                    passed=None if dry_run else passed,
                    message="Down pairs drop check",
                )
            )
            if not passed:
                all_criteria_passed = False

        # degradation_ci_upper_max
        if crit_cfg.degradation_ci_upper_max is not None:
            gating_down_groups = [
                g for g in pair_group_results if g.expected == "down" and g.passed is not None
            ]
            down_groups = [g for g in pair_group_results if g.expected == "down"]
            if len(down_groups) == 0:
                passed = False
                act_str = "no down groups"
            elif len(gating_down_groups) == 0:
                passed = True
                act_str = "no gating groups (all report-only or small)"
            else:
                passed = all(g.passed for g in gating_down_groups)
                max_ci_upper = max(g.ci_95_upper for g in gating_down_groups)
                act_str = f"max CI upper {max_ci_upper:+.3f}"
            criteria_results.append(
                CriterionEvaluationResult(
                    name="degradation_ci_upper_max",
                    expected=f"< {crit_cfg.degradation_ci_upper_max:+.3f}",
                    actual=act_str,
                    passed=None if dry_run else passed,
                    message="Degradation 95% CI upper bound check across down groups",
                )
            )
            if not passed:
                all_criteria_passed = False

        # neutral_ci_abs_max
        if crit_cfg.neutral_ci_abs_max is not None:
            gating_neutral_groups = [
                g for g in pair_group_results if g.expected == "neutral" and g.passed is not None
            ]
            neutral_groups = [g for g in pair_group_results if g.expected == "neutral"]
            if len(neutral_groups) == 0:
                passed = False
                act_str = "no neutral groups"
            elif len(gating_neutral_groups) == 0:
                passed = True
                act_str = "no gating groups (all report-only or small)"
            else:
                passed = all(g.passed for g in gating_neutral_groups)
                max_ci_abs = max(
                    max(abs(g.ci_95_lower), abs(g.ci_95_upper)) for g in gating_neutral_groups
                )
                act_str = f"max CI abs {max_ci_abs:.3f}"
            criteria_results.append(
                CriterionEvaluationResult(
                    name="neutral_ci_abs_max",
                    expected=f"<= {crit_cfg.neutral_ci_abs_max:.3f}",
                    actual=act_str,
                    passed=None if dry_run else passed,
                    message="Neutral 95% CI bounds check across neutral groups",
                )
            )
            if not passed:
                all_criteria_passed = False

        # pair_guard_neutral_abs_max
        if crit_cfg.pair_guard_neutral_abs_max is not None:
            active_gating_pairs = [
                p
                for p in pair_results
                if not p.incomplete
                and not p.was_truncated
                and (not p.kind or p.kind not in report_only)
            ]
            violating_pairs = []
            guard_down_tol = crit_cfg.pair_guard_down_tolerance
            for p in active_gating_pairs:
                if (
                    p.expected == "neutral"
                    and abs(p.mean_delta) > crit_cfg.pair_guard_neutral_abs_max
                ):
                    violating_pairs.append(f"{Path(p.after_path).name} ({p.mean_delta:+.3f})")
                elif p.expected == "down" and p.mean_delta > guard_down_tol:
                    violating_pairs.append(f"{Path(p.after_path).name} ({p.mean_delta:+.3f})")
            passed = len(violating_pairs) == 0 and len(active_gating_pairs) > 0
            act_str = f"{len(violating_pairs)} violations" if violating_pairs else "all passed"
            criteria_results.append(
                CriterionEvaluationResult(
                    name="pair_guard_neutral_abs_max",
                    expected=f"neutral <= {crit_cfg.pair_guard_neutral_abs_max:.3f}, down <= {guard_down_tol:.3f}",
                    actual=act_str,
                    passed=None if dry_run else passed,
                    message=f"Pair guard check ({', '.join(violating_pairs[:3])})"
                    if violating_pairs
                    else "All pairs satisfied pair guard",
                )
            )
            if not passed:
                all_criteria_passed = False

        # max_spread
        if crit_cfg.max_spread is not None:
            max_spread_all = max((s.max_spread for s in question_stats.values()), default=0.0)
            passed = max_spread_all <= crit_cfg.max_spread
            criteria_results.append(
                CriterionEvaluationResult(
                    name="max_spread",
                    expected=f"<= {crit_cfg.max_spread:.3f}",
                    actual=f"{max_spread_all:.3f}",
                    passed=None if dry_run else passed,
                    message=f"Max run-to-run spread is {max_spread_all:.3f}",
                )
            )
            if not passed:
                all_criteria_passed = False

        # If group_by is kind and any gating group explicitly failed, fail overall criteria
        if group_by == "kind":
            if any(g.passed is False for g in pair_group_results):
                all_criteria_passed = False

    summary = {
        "documents_evaluated": len(labels_cfg.documents),
        "pairs_evaluated": len(labels_cfg.pairs),
        "incomplete_pairs": incomplete_pairs_count,
        "truncated_pairs": truncated_pairs_count,
        "total_absent_expected": total_absent,
        "total_detected": total_detected,
        "detected_rate": (total_detected / total_absent) if total_absent > 0 else 1.0,
        "total_present_expected": total_present,
        "total_false_alarms": total_false_alarms,
        "false_alarm_rate": (total_false_alarms / total_present) if total_present > 0 else 0.0,
        "criteria_passed": None if dry_run else all_criteria_passed,
    }

    report = ValidationReport(
        preset_name=preset_cfg.name,
        runs=runs,
        all_passed=None if dry_run else all_criteria_passed,
        summary=summary,
        presence_results=presence_results,
        pair_results=pair_results,
        pair_group_results=pair_group_results,
        incomplete_pairs_count=incomplete_pairs_count,
        truncated_pairs_count=truncated_pairs_count,
        question_stats=question_stats,
        criteria_results=criteria_results,
        choice_distributions=choice_distributions,
        unplaced_warnings=unplaced_warnings,
        mock=dry_run,
    )

    return report, has_runtime_error


# --- Reporting ---


def render_validation_table(report: ValidationReport) -> None:
    """Renders validation report as rich tables to console."""
    console.print()
    if report.mock:
        verdict_badge = "[bold yellow]N/A (MOCK)[/bold yellow]"
        title = "[bold magenta]TypeSafe Validation Report (MOCK)[/bold magenta]"
    elif report.all_passed:
        verdict_badge = "[bold green]✔ PASS[/bold green]"
        title = "[bold magenta]TypeSafe Validation Report[/bold magenta]"
    else:
        verdict_badge = "[bold red]✘ FAIL[/bold red]"
        title = "[bold magenta]TypeSafe Validation Report[/bold magenta]"

    console.print(
        Panel(
            f"Preset: [bold cyan]{report.preset_name}[/bold cyan] | Runs: [bold]{report.runs}[/bold] | Verdict: {verdict_badge}",
            title=title,
            border_style="magenta",
        )
    )

    # 1. Presence questions table
    presence_stats = [s for s in report.question_stats.values() if s.type == "noul"]
    if presence_stats:
        table = Table(
            title="[bold cyan]Presence Questions (Noul)[/bold cyan]",
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Question", style="bold")
        table.add_column("Expected Absent", justify="center")
        table.add_column("Detected", justify="center")
        table.add_column("Missed", justify="center")
        table.add_column("Expected Present", justify="center")
        table.add_column("False Alarms", justify="center")
        table.add_column("Max Spread", justify="center")

        for s in presence_stats:
            det_rate = (
                f"{(s.detected_count / s.total_absent_expected * 100):.0f}%"
                if s.total_absent_expected > 0
                else "N/A"
            )
            fa_rate = (
                f"{(s.false_alarm_count / s.total_present_expected * 100):.0f}%"
                if s.total_present_expected > 0
                else "0%"
            )
            table.add_row(
                s.question_id,
                str(s.total_absent_expected),
                f"{s.detected_count} [dim]({det_rate})[/dim]",
                str(s.missed_count),
                str(s.total_present_expected),
                f"{s.false_alarm_count} [dim]({fa_rate})[/dim]",
                f"{s.max_spread:.3f}",
            )
        console.print(table)
        console.print()

    # 2. Pair Groups table (if present)
    if report.pair_group_results:
        table_groups = Table(
            title="[bold cyan]Pair Groups (Direction & CI)[/bold cyan]",
            header_style="bold cyan",
            border_style="dim",
        )
        table_groups.add_column("Group (Kind)", style="bold")
        table_groups.add_column("Question", justify="center")
        table_groups.add_column("Expected", justify="center")
        table_groups.add_column("n", justify="center")
        table_groups.add_column("Mean Δ", justify="center")
        table_groups.add_column("95% CI", justify="center")
        table_groups.add_column("Status", justify="center")
        table_groups.add_column("Worst Pair", justify="left")

        for g in report.pair_group_results:
            if report.mock:
                status = "[bold yellow]N/A (MOCK)[/bold yellow]"
            elif g.passed is None:
                status = "[bold yellow]N/A[/bold yellow]"
            elif g.passed:
                status = "[bold green]PASS[/bold green]"
            else:
                status = "[bold red]FAIL[/bold red]"
            ci_str = f"[{g.ci_95_lower:+.3f}, {g.ci_95_upper:+.3f}]"
            worst_str = f"{g.worst_pair_path} ({g.worst_pair_delta:+.3f})"
            table_groups.add_row(
                g.kind,
                g.question_id or "—",
                g.expected,
                str(g.n),
                f"{g.mean_delta:+.3f}",
                ci_str,
                status,
                worst_str,
            )
        console.print(table_groups)
        console.print()

    # 3. Score pairs table
    if report.pair_results:
        table_pairs = Table(
            title="[bold cyan]Score Pairs (Direction & CI)[/bold cyan]",
            header_style="bold cyan",
            border_style="dim",
        )
        table_pairs.add_column("Pair", style="bold")
        table_pairs.add_column("Question", justify="center")
        table_pairs.add_column("Expected", justify="center")
        table_pairs.add_column("Mean Δ", justify="center")
        table_pairs.add_column("95% CI", justify="center")
        table_pairs.add_column("Status", justify="center")

        for p in report.pair_results:
            pair_name = f"{Path(p.before_path).name} → {Path(p.after_path).name}"
            if report.mock:
                status = "[bold yellow]N/A (MOCK)[/bold yellow]"
            elif p.incomplete:
                status = f"[bold yellow]INCOMPLETE ({p.incomplete_runs} lost)[/bold yellow]"
            elif p.was_truncated:
                status = "[bold yellow]TRUNCATED[/bold yellow]"
            elif p.passed:
                status = "[bold green]PASS[/bold green]"
            else:
                status = "[bold red]FAIL[/bold red]"
            ci_str = f"[{p.ci_95_lower:.2f}, {p.ci_95_upper:.2f}]"
            table_pairs.add_row(
                pair_name,
                p.question_id,
                p.expected,
                f"{p.mean_delta:+.3f}",
                ci_str,
                status,
            )
        console.print(table_pairs)
        if report.incomplete_pairs_count > 0 or report.truncated_pairs_count > 0:
            console.print(
                f"[yellow]Excluded from gating: {report.incomplete_pairs_count} incomplete pair(s), "
                f"{report.truncated_pairs_count} truncated pair(s)[/yellow]"
            )
        console.print()

    # 4. Criteria checks
    if report.criteria_results:
        table_crit = Table(
            title="[bold cyan]Pass Criteria Verification[/bold cyan]",
            header_style="bold cyan",
            border_style="dim",
        )
        table_crit.add_column("Criterion", style="bold")
        table_crit.add_column("Required", justify="center")
        table_crit.add_column("Actual", justify="center")
        table_crit.add_column("Status", justify="center")

        for c in report.criteria_results:
            if c.passed is None:
                status = "[bold yellow]N/A (MOCK)[/bold yellow]"
            elif c.passed:
                status = "[bold green]✔ PASS[/bold green]"
            else:
                status = "[bold red]✘ FAIL[/bold red]"
            table_crit.add_row(c.name, str(c.expected), str(c.actual), status)

        console.print(table_crit)
        console.print()

    # 5. Choice Distributions (Non-gating, e.g. readiness, tone)
    if report.choice_distributions:
        dist_texts = []
        for q_id, counts in sorted(report.choice_distributions.items()):
            total = sum(counts.values())
            parts = [
                f"{choice}: {c} ({(c / total * 100):.1f}%)" for choice, c in sorted(counts.items())
            ]
            dist_texts.append(f"• [bold cyan]{q_id}[/bold cyan]: " + ", ".join(parts))
        console.print(
            Panel(
                "\n".join(dist_texts),
                title=f"[bold cyan]Choice Question Distributions (Non-gating, counts over {report.runs} run(s))[/bold cyan]",
                border_style="cyan",
            )
        )
        console.print()

    # 6. Unplaced Warnings
    if report.unplaced_warnings:
        warning_texts = [f"• {escape(w)}" for w in report.unplaced_warnings]
        console.print(
            Panel(
                "\n".join(warning_texts),
                title="[bold yellow]Unplaced Warnings[/bold yellow]",
                border_style="yellow",
            )
        )
        console.print()

    if report.mock:
        console.print("[dim]Mode: MOCK (dry-run, no API calls made)[/dim]")
        console.print()


def render_validation_json(report: ValidationReport) -> str:
    """Renders validation report as structured JSON."""
    return json.dumps(report.model_dump(), indent=2, ensure_ascii=False)


def render_validation_markdown(report: ValidationReport) -> str:
    """Renders validation report as Markdown."""
    title = "# TypeSafe Validation Report (MOCK)" if report.mock else "# TypeSafe Validation Report"
    if report.mock:
        verdict_str = "N/A (MOCK)"
    elif report.all_passed:
        verdict_str = "PASS"
    else:
        verdict_str = "FAIL"

    lines = [
        title,
        "",
        f"**Preset:** `{report.preset_name}` | **Runs:** {report.runs} | **Verdict:** {verdict_str}",
    ]
    if report.mock:
        lines.append("**Mode:** MOCK (dry-run, no API calls made)  ")
    lines.append("")

    presence_stats = [s for s in report.question_stats.values() if s.type == "noul"]
    if presence_stats:
        lines.append("## Presence Questions (Noul)")
        lines.append("")
        lines.append(
            "| Question | Expected Absent | Detected | Missed | Expected Present | False Alarms | Max Spread |"
        )
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for s in presence_stats:
            det_rate = (
                f"{(s.detected_count / s.total_absent_expected * 100):.0f}%"
                if s.total_absent_expected > 0
                else "N/A"
            )
            fa_rate = (
                f"{(s.false_alarm_count / s.total_present_expected * 100):.0f}%"
                if s.total_present_expected > 0
                else "0%"
            )
            lines.append(
                f"| `{s.question_id}` | {s.total_absent_expected} | {s.detected_count} ({det_rate}) | {s.missed_count} | {s.total_present_expected} | {s.false_alarm_count} ({fa_rate}) | {s.max_spread:.3f} |"
            )
        lines.append("")

    if report.pair_group_results:
        lines.append("## Pair Groups (Direction & CI)")
        lines.append("")
        lines.append(
            "| Group (Kind) | Question | Expected | n | Mean Δ | 95% CI | Status | Worst Pair |"
        )
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
        for g in report.pair_group_results:
            if report.mock:
                status = "N/A (MOCK)"
            elif g.passed is None:
                status = "N/A"
            elif g.passed:
                status = "PASS"
            else:
                status = "FAIL"
            ci_str = f"[{g.ci_95_lower:+.3f}, {g.ci_95_upper:+.3f}]"
            worst_str = f"`{g.worst_pair_path}` ({g.worst_pair_delta:+.3f})"
            qid_str = f"`{g.question_id}`" if g.question_id else "—"
            lines.append(
                f"| `{g.kind}` | {qid_str} | `{g.expected}` | {g.n} | {g.mean_delta:+.3f} | {ci_str} | **{status}** | {worst_str} |"
            )
        lines.append("")

    if report.pair_results:
        lines.append("## Score Pairs (Direction & CI)")
        lines.append("")
        lines.append("| Pair | Question | Expected | Mean Δ | 95% CI | Status |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for p in report.pair_results:
            pair_name = f"`{Path(p.before_path).name}` → `{Path(p.after_path).name}`"
            if report.mock:
                status = "N/A (MOCK)"
            elif p.incomplete:
                status = f"INCOMPLETE ({p.incomplete_runs} lost)"
            elif p.was_truncated:
                status = "TRUNCATED"
            elif p.passed:
                status = "PASS"
            else:
                status = "FAIL"
            ci_str = f"[{p.ci_95_lower:.2f}, {p.ci_95_upper:.2f}]"
            lines.append(
                f"| {pair_name} | `{p.question_id}` | `{p.expected}` | {p.mean_delta:+.3f} | {ci_str} | **{status}** |"
            )
        if report.incomplete_pairs_count > 0 or report.truncated_pairs_count > 0:
            lines.append("")
            lines.append(
                f"**Excluded from gating:** {report.incomplete_pairs_count} incomplete pair(s), "
                f"{report.truncated_pairs_count} truncated pair(s)  "
            )
        lines.append("")

    if report.criteria_results:
        lines.append("## Criteria Verification")
        lines.append("")
        lines.append("| Criterion | Required | Actual | Status |")
        lines.append("| :--- | :---: | :---: | :---: |")
        for c in report.criteria_results:
            status = "N/A (MOCK)" if c.passed is None else ("PASS" if c.passed else "FAIL")
            lines.append(f"| {c.name} | {c.expected} | {c.actual} | **{status}** |")
        lines.append("")

    if report.choice_distributions:
        lines.append(f"## Choice Distributions (Non-gating, counts over {report.runs} run(s))")
        lines.append("")
        for q_id, counts in sorted(report.choice_distributions.items()):
            total = sum(counts.values())
            parts = [
                f"`{choice}`: {c} ({(c / total * 100):.1f}%)"
                for choice, c in sorted(counts.items())
            ]
            lines.append(f"- **`{q_id}`**: " + ", ".join(parts))
        lines.append("")

    if report.unplaced_warnings:
        lines.append("## Unplaced Warnings")
        lines.append("")
        for w in report.unplaced_warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


# --- Ablation Generator ---


def split_markdown_by_h2(content: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Splits markdown content by '## ' headings.

    Returns (preamble, list_of_(title, slug, section_content)).
    """
    lines = content.splitlines(keepends=True)
    preamble_lines: list[str] = []
    sections: list[tuple[str, str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        m = re.match(r"^##\s+(.+)$", line.strip())
        if m:
            if current_title is not None:
                slug = re.sub(r"[^a-z0-9]+", "_", current_title.lower()).strip("_")
                sections.append((current_title, slug, "".join(current_lines)))
            else:
                preamble_lines = list(current_lines)
            current_title = m.group(1).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_title is not None:
        slug = re.sub(r"[^a-z0-9]+", "_", current_title.lower()).strip("_")
        sections.append((current_title, slug, "".join(current_lines)))
    elif current_lines and not preamble_lines:
        preamble_lines = list(current_lines)

    return "".join(preamble_lines), sections


def generate_ablation_variants(
    doc_path: Path,
    out_dir: Path | None = None,
    preset_name: str = "design_doc",
) -> tuple[list[Path], str]:
    """Builds 'one section removed' variants from a markdown document split on '## ' headings.

    Outputs variant markdown files and starter labels.yaml content.
    """
    doc_path = doc_path.resolve()
    if not doc_path.is_file():
        raise FileNotFoundError(f"Document not found: {doc_path}")

    content = doc_path.read_text(encoding="utf-8")
    preamble, sections = split_markdown_by_h2(content)

    if not sections:
        raise ValueError(f"No '## ' headings found in document: {doc_path}")

    target_dir = out_dir.resolve() if out_dir else doc_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    variant_paths: list[Path] = []
    expect_full: dict[str, str] = {}
    variant_docs: list[dict[str, Any]] = []

    # Full document expectation: all sections present
    for _title, slug, _ in sections:
        expect_full[slug] = "present"

    full_doc_entry = {
        "path": str(doc_path.relative_to(target_dir))
        if target_dir in doc_path.parents
        else str(doc_path.name),
        "expect": expect_full,
    }
    variant_docs.append(full_doc_entry)

    # For each section, build variant omitting that section
    for idx, (_title, slug, _) in enumerate(sections):
        variant_content = preamble + "".join(
            sec_body for j, (_, _, sec_body) in enumerate(sections) if j != idx
        )
        variant_filename = f"{doc_path.stem}_without_{slug}.md"
        variant_file = target_dir / variant_filename
        variant_file.write_text(variant_content, encoding="utf-8")
        variant_paths.append(variant_file)

        variant_expect = {}
        for _, other_slug, _ in sections:
            variant_expect[other_slug] = "absent" if other_slug == slug else "present"

        variant_docs.append(
            {
                "path": variant_filename,
                "expect": variant_expect,
            }
        )

    labels_data = {
        "preset": preset_name,
        "runs": 3,
        "criteria": {
            "min_detected": len(sections),
            "max_false_alarms": 0,
        },
        "documents": variant_docs,
    }

    labels_yaml = yaml.dump(labels_data, sort_keys=False, allow_unicode=True)
    labels_file = target_dir / "labels.yaml"
    labels_file.write_text(labels_yaml, encoding="utf-8")
    return variant_paths, labels_yaml
