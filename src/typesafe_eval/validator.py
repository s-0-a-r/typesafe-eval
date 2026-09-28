"""Validation engine, statistical metrics, labels runner, and ablation helper.

Implements `typesafe-eval validate` per Issue #38.
"""

import math
import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Literal

import yaml
import click
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from typesafe_eval.presets import load_preset, PresetConfig
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.models import DocumentEvalResult

err_console = Console(stderr=True)
console = Console()


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
        15: 2.131,
        20: 2.086,
        30: 2.042,
        60: 2.000,
        120: 1.980,
    }
    if df <= 0:
        return 1.960
    if df in t_table:
        return t_table[df]
    for k in sorted(t_table.keys()):
        if df <= k:
            return t_table[k]
    return 1.960


def compute_ci_95(deltas: List[float]) -> Tuple[float, float, float]:
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
    path: str
    expect: Dict[str, Literal["present", "absent"]]


class ValidationPairExpectation(BaseModel):
    before: str
    after: str
    expect: Dict[str, Literal["down", "neutral"]]


class QuestionCriteria(BaseModel):
    min_detected: Optional[Union[int, float]] = None
    max_false_alarms: Optional[Union[int, float]] = None
    max_neutral_delta: Optional[float] = None
    min_degradation_drop: Optional[float] = None
    max_spread: Optional[float] = None


class ValidationCriteria(QuestionCriteria):
    questions: Optional[Dict[str, QuestionCriteria]] = None


class ValidationLabelsConfig(BaseModel):
    preset: Optional[str] = None
    config: Optional[str] = None
    runs: int = 3
    criteria: Optional[ValidationCriteria] = None
    documents: List[ValidationDocumentExpectation] = Field(default_factory=list)
    pairs: List[ValidationPairExpectation] = Field(default_factory=list)


# --- Results Models ---

class DocumentPresenceResult(BaseModel):
    path: str
    question_id: str
    expected: Literal["present", "absent"]
    probabilities: List[float]
    spread: float
    verdict: Literal["detected", "missed", "correct_present", "false_alarm"]


class PairScoreResult(BaseModel):
    before_path: str
    after_path: str
    question_id: str
    expected: Literal["down", "neutral"]
    before_scores: List[float]
    after_scores: List[float]
    deltas: List[float]
    mean_delta: float
    ci_95_lower: float
    ci_95_upper: float
    passed: bool


class QuestionValidationStats(BaseModel):
    question_id: str
    type: Literal["noul", "score"]
    total_absent_expected: int = 0
    detected_count: int = 0
    missed_count: int = 0
    total_present_expected: int = 0
    false_alarm_count: int = 0
    max_spread: float = 0.0
    mean_delta: Optional[float] = None
    ci_95: Optional[Tuple[float, float]] = None
    pairs_count: int = 0


class CriterionEvaluationResult(BaseModel):
    name: str
    expected: Any
    actual: Any
    passed: Optional[bool] = None
    message: str


class ValidationReport(BaseModel):
    preset_name: str
    runs: int
    all_passed: Optional[bool] = None
    summary: Dict[str, Any]
    presence_results: List[DocumentPresenceResult] = Field(default_factory=list)
    pair_results: List[PairScoreResult] = Field(default_factory=list)
    question_stats: Dict[str, QuestionValidationStats] = Field(default_factory=dict)
    criteria_results: List[CriterionEvaluationResult] = Field(default_factory=list)
    choice_distributions: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    mock: bool = False


# --- Execution Engine ---

def load_labels_file(labels_path: Union[str, Path]) -> Tuple[ValidationLabelsConfig, Path]:
    """Loads and validates a labels.yaml configuration file."""
    path = Path(labels_path)
    if not path.is_file():
        raise FileNotFoundError(f"Labels file not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
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

    config = ValidationLabelsConfig(**data)
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


def run_validation(
    labels_cfg: ValidationLabelsConfig,
    base_dir: Path,
    evaluator: TypeSafeEvaluator,
    runs_override: Optional[int] = None,
    dry_run: bool = False,
    preset_cfg: Optional[PresetConfig] = None,
) -> Tuple[ValidationReport, bool]:
    """Runs validation over documents and pairs across N runs."""
    runs = runs_override if runs_override is not None else labels_cfg.runs
    if runs < 1:
        runs = 1

    if preset_cfg is None:
        preset_cfg = validate_labels_preset(labels_cfg, base_dir)

    presence_results: List[DocumentPresenceResult] = []
    pair_results: List[PairScoreResult] = []
    choice_distributions: Dict[str, Dict[str, int]] = {}
    has_runtime_error = False

    # 1. Evaluate document presence expectations
    for doc_item in labels_cfg.documents:
        doc_path = resolve_file_path(base_dir, doc_item.path)
        probs_by_question: Dict[str, List[float]] = {q: [] for q in doc_item.expect}

        for r in range(runs):
            try:
                res = evaluator.evaluate_document(
                    filepath=str(doc_path),
                    preset=preset_cfg,
                    dry_run=dry_run,
                )
                # Track non-gating choice distributions across evaluated documents
                for ch_qid, ch_obj in res.choices.items():
                    if ch_qid not in choice_distributions:
                        choice_distributions[ch_qid] = {}
                    choice_distributions[ch_qid][ch_obj.choice] = (
                        choice_distributions[ch_qid].get(ch_obj.choice, 0) + 1
                    )

                for q_id in doc_item.expect:
                    if q_id in res.nouls:
                        noul_obj = res.nouls[q_id]
                        q_cfg = preset_cfg.questions.get(q_id)
                        is_max_threshold = bool(q_cfg and q_cfg.max_threshold is not None)
                        threshold = (
                            q_cfg.max_threshold
                            if is_max_threshold
                            else (q_cfg.min_threshold if q_cfg and q_cfg.min_threshold is not None else 0.5)
                        )

                        # Check candidate violations for category
                        has_cand_violation = False
                        if q_id == "has_pii":
                            has_cand_violation = (
                                any(e.outcome == "personal" for e in res.email_evaluations)
                                or any(p.outcome == "personal" for p in res.phone_evaluations)
                                or any(i.outcome == "sensitive" for i in res.ip_evaluations)
                                or any(u.outcome == "sensitive" for u in res.url_evaluations)
                            )
                        elif q_id == "has_secrets":
                            has_cand_violation = any(s.outcome == "secret" for s in res.secret_evaluations)

                        # Determine presence
                        is_preflight = noul_obj.overridden_by is not None
                        doc_present = False
                        if noul_obj.probability is not None:
                            doc_present = (
                                noul_obj.probability > threshold
                                if is_max_threshold
                                else noul_obj.probability >= threshold
                            )

                        if has_cand_violation or is_preflight:
                            # Present via candidate or preflight: count as 1.0 (or prob if higher)
                            p_val = max(noul_obj.probability, 1.0) if noul_obj.probability is not None else 1.0
                            probs_by_question[q_id].append(p_val)
                        elif noul_obj.probability is not None:
                            probs_by_question[q_id].append(noul_obj.probability)
                        else:
                            click.echo(
                                f"{doc_path} (run {r+1}/{runs}): Question '{q_id}' probability is None without preflight decision",
                                err=True,
                            )
                            has_runtime_error = True
                    elif q_id in res.scores:
                        probs_by_question[q_id].append(res.scores[q_id].normalized_score)
                    else:
                        click.echo(
                            f"{doc_path} (run {r+1}/{runs}): Question '{q_id}' was not returned by evaluator",
                            err=True,
                        )
                        has_runtime_error = True
            except Exception as e:
                click.echo(f"{doc_path} (run {r+1}/{runs}): {e}", err=True)
                has_runtime_error = True

        for q_id, expected in doc_item.expect.items():
            probs = probs_by_question[q_id]
            if not probs:
                continue

            q_cfg = preset_cfg.questions.get(q_id)
            is_max_threshold = bool(q_cfg and q_cfg.max_threshold is not None)

            if is_max_threshold:
                threshold = q_cfg.max_threshold
                is_present = lambda p, t=threshold: p > t
                is_absent = lambda p, t=threshold: p <= t
            else:
                threshold = q_cfg.min_threshold if (q_cfg and q_cfg.min_threshold is not None) else 0.5
                is_present = lambda p, t=threshold: p >= t
                is_absent = lambda p, t=threshold: p < t

            spread = max(probs) - min(probs) if probs else 0.0

            if expected == "absent":
                # Detected if absent in EVERY run
                if all(is_absent(p) for p in probs):
                    verdict = "detected"
                else:
                    verdict = "missed"
            else:
                # False alarm if absent in ANY run
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

    # 2. Evaluate score pairs
    for pair_item in labels_cfg.pairs:
        before_path = resolve_file_path(base_dir, pair_item.before)
        after_path = resolve_file_path(base_dir, pair_item.after)

        before_scores_by_q: Dict[str, List[float]] = {q: [] for q in pair_item.expect}
        after_scores_by_q: Dict[str, List[float]] = {q: [] for q in pair_item.expect}

        for r in range(runs):
            try:
                res_b = evaluator.evaluate_document(
                    filepath=str(before_path),
                    preset=preset_cfg,
                    dry_run=dry_run,
                )
                res_a = evaluator.evaluate_document(
                    filepath=str(after_path),
                    preset=preset_cfg,
                    dry_run=dry_run,
                )
                for res_item in (res_b, res_a):
                    for ch_qid, ch_obj in res_item.choices.items():
                        if ch_qid not in choice_distributions:
                            choice_distributions[ch_qid] = {}
                        choice_distributions[ch_qid][ch_obj.choice] = (
                            choice_distributions[ch_qid].get(ch_obj.choice, 0) + 1
                        )
                for q_id in pair_item.expect:
                    if q_id in res_b.scores:
                        before_scores_by_q[q_id].append(res_b.scores[q_id].normalized_score)
                    elif q_id in res_b.nouls and res_b.nouls[q_id].probability is not None:
                        before_scores_by_q[q_id].append(res_b.nouls[q_id].probability)
                    else:
                        click.echo(f"{before_path} (run {r+1}/{runs}): Question '{q_id}' not returned in pair", err=True)
                        has_runtime_error = True

                    if q_id in res_a.scores:
                        after_scores_by_q[q_id].append(res_a.scores[q_id].normalized_score)
                    elif q_id in res_a.nouls and res_a.nouls[q_id].probability is not None:
                        after_scores_by_q[q_id].append(res_a.nouls[q_id].probability)
                    else:
                        click.echo(f"{after_path} (run {r+1}/{runs}): Question '{q_id}' not returned in pair", err=True)
                        has_runtime_error = True
            except Exception as e:
                click.echo(f"Pair ({pair_item.before} -> {pair_item.after}, run {r+1}/{runs}): {e}", err=True)
                has_runtime_error = True

        for q_id, expected in pair_item.expect.items():
            b_list = before_scores_by_q[q_id]
            a_list = after_scores_by_q[q_id]
            if not b_list or not a_list:
                continue

            deltas = [a - b for a, b in zip(a_list, b_list)]
            mean_d, ci_low, ci_high = compute_ci_95(deltas)

            passed = True
            if expected == "down":
                passed = mean_d < 0.0
            elif expected == "neutral":
                max_neutral = 0.05
                if labels_cfg.criteria and labels_cfg.criteria.max_neutral_delta is not None:
                    max_neutral = labels_cfg.criteria.max_neutral_delta
                passed = abs(mean_d) <= max_neutral

            pair_results.append(
                PairScoreResult(
                    before_path=str(pair_item.before),
                    after_path=str(pair_item.after),
                    question_id=q_id,
                    expected=expected,
                    before_scores=b_list,
                    after_scores=a_list,
                    deltas=deltas,
                    mean_delta=mean_d,
                    ci_95_lower=ci_low,
                    ci_95_upper=ci_high,
                    passed=passed,
                )
            )

    # 3. Aggregate per-question statistics
    question_stats: Dict[str, QuestionValidationStats] = {}

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

    for ps in pair_results:
        q_id = ps.question_id
        if q_id not in question_stats:
            question_stats[q_id] = QuestionValidationStats(question_id=q_id, type="score")
        stat = question_stats[q_id]
        stat.pairs_count += 1
        stat.mean_delta = ps.mean_delta
        stat.ci_95 = (ps.ci_95_lower, ps.ci_95_upper)

    # 4. Evaluate Pass Criteria
    criteria_results: List[CriterionEvaluationResult] = []
    all_criteria_passed = True

    total_absent = sum(s.total_absent_expected for s in question_stats.values())
    total_detected = sum(s.detected_count for s in question_stats.values())
    total_present = sum(s.total_present_expected for s in question_stats.values())
    total_false_alarms = sum(s.false_alarm_count for s in question_stats.values())

    crit_cfg = labels_cfg.criteria
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
                        expected=f"{exp_det*100:.0f}%",
                        actual=f"{act_det_rate*100:.1f}% ({total_detected}/{total_absent})",
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

        # max_neutral_delta
        if crit_cfg.max_neutral_delta is not None:
            neutral_pairs = [p for p in pair_results if p.expected == "neutral"]
            max_act_neutral = max((abs(p.mean_delta) for p in neutral_pairs), default=0.0)
            passed = max_act_neutral <= crit_cfg.max_neutral_delta
            criteria_results.append(
                CriterionEvaluationResult(
                    name="max_neutral_delta",
                    expected=f"<= {crit_cfg.max_neutral_delta:.3f}",
                    actual=f"{max_act_neutral:.3f}",
                    passed=None if dry_run else passed,
                    message=f"Max neutral delta is {max_act_neutral:.3f}",
                )
            )
            if not passed:
                all_criteria_passed = False

        # min_degradation_drop
        if crit_cfg.min_degradation_drop is not None:
            down_pairs = [p for p in pair_results if p.expected == "down"]
            min_drop = crit_cfg.min_degradation_drop
            passed = all(p.mean_delta <= -min_drop for p in down_pairs)
            max_delta = max((p.mean_delta for p in down_pairs), default=0.0)
            criteria_results.append(
                CriterionEvaluationResult(
                    name="min_degradation_drop",
                    expected=f"<= -{min_drop:.3f}",
                    actual=f"max delta {max_delta:.3f}",
                    passed=None if dry_run else passed,
                    message=f"Down pairs drop check",
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

    summary = {
        "documents_evaluated": len(labels_cfg.documents),
        "pairs_evaluated": len(labels_cfg.pairs),
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
        question_stats=question_stats,
        criteria_results=criteria_results,
        choice_distributions=choice_distributions,
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
            det_rate = f"{(s.detected_count / s.total_absent_expected * 100):.0f}%" if s.total_absent_expected > 0 else "N/A"
            fa_rate = f"{(s.false_alarm_count / s.total_present_expected * 100):.0f}%" if s.total_present_expected > 0 else "0%"
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

    # 2. Score pairs table
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
        console.print()

    # 3. Criteria checks
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

    # 4. Choice Distributions (Non-gating, e.g. readiness, tone)
    if report.choice_distributions:
        dist_texts = []
        for q_id, counts in sorted(report.choice_distributions.items()):
            total = sum(counts.values())
            parts = [f"{choice}: {c} ({(c/total*100):.1f}%)" for choice, c in sorted(counts.items())]
            dist_texts.append(f"• [bold cyan]{q_id}[/bold cyan]: " + ", ".join(parts))
        console.print(
            Panel(
                "\n".join(dist_texts),
                title=f"[bold cyan]Choice Question Distributions (Non-gating, counts over {report.runs} run(s))[/bold cyan]",
                border_style="cyan",
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
        lines.append("| Question | Expected Absent | Detected | Missed | Expected Present | False Alarms | Max Spread |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for s in presence_stats:
            det_rate = f"{(s.detected_count / s.total_absent_expected * 100):.0f}%" if s.total_absent_expected > 0 else "N/A"
            fa_rate = f"{(s.false_alarm_count / s.total_present_expected * 100):.0f}%" if s.total_present_expected > 0 else "0%"
            lines.append(
                f"| `{s.question_id}` | {s.total_absent_expected} | {s.detected_count} ({det_rate}) | {s.missed_count} | {s.total_present_expected} | {s.false_alarm_count} ({fa_rate}) | {s.max_spread:.3f} |"
            )
        lines.append("")

    if report.pair_results:
        lines.append("## Score Pairs (Direction & CI)")
        lines.append("")
        lines.append("| Pair | Question | Expected | Mean Δ | 95% CI | Status |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for p in report.pair_results:
            pair_name = f"`{Path(p.before_path).name}` → `{Path(p.after_path).name}`"
            status = "N/A (MOCK)" if report.mock else ("PASS" if p.passed else "FAIL")
            ci_str = f"[{p.ci_95_lower:.2f}, {p.ci_95_upper:.2f}]"
            lines.append(f"| {pair_name} | `{p.question_id}` | `{p.expected}` | {p.mean_delta:+.3f} | {ci_str} | **{status}** |")
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
            parts = [f"`{choice}`: {c} ({(c/total*100):.1f}%)" for choice, c in sorted(counts.items())]
            lines.append(f"- **`{q_id}`**: " + ", ".join(parts))
        lines.append("")

    return "\n".join(lines)


# --- Ablation Generator ---

def split_markdown_by_h2(content: str) -> Tuple[str, List[Tuple[str, str, str]]]:
    """Splits markdown content by '## ' headings.
    
    Returns (preamble, list_of_(title, slug, section_content)).
    """
    lines = content.splitlines(keepends=True)
    preamble_lines: List[str] = []
    sections: List[Tuple[str, str, str]] = []
    current_title: Optional[str] = None
    current_lines: List[str] = []

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
    out_dir: Optional[Path] = None,
    preset_name: str = "design_doc",
) -> Tuple[List[Path], str]:
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

    variant_paths: List[Path] = []
    expect_full: Dict[str, str] = {}
    variant_docs: List[Dict[str, Any]] = []

    # Full document expectation: all sections present
    for title, slug, _ in sections:
        expect_full[slug] = "present"

    full_doc_entry = {
        "path": str(doc_path.relative_to(target_dir)) if target_dir in doc_path.parents else str(doc_path.name),
        "expect": expect_full,
    }
    variant_docs.append(full_doc_entry)

    # For each section, build variant omitting that section
    for idx, (title, slug, _) in enumerate(sections):
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

        variant_docs.append({
            "path": variant_filename,
            "expect": variant_expect,
        })

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
