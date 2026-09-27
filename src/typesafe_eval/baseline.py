"""Baseline diff mode: loads previous evaluation reports and detects regressions.

Implements `--baseline` per Issue #39.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from typesafe_eval.models import DocumentEvalResult, PresetConfig, BaselineDiff, QuestionDiff


def load_baseline(baseline_path: Union[str, Path]) -> Dict[str, DocumentEvalResult]:
    """Loads a previous evaluation report JSON and returns an indexed lookup map."""
    path = Path(baseline_path)
    if not path.is_file():
        raise FileNotFoundError(f"Baseline file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw_text)
    except Exception as e:
        raise ValueError(f"Failed to parse baseline JSON {path}: {e}")

    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f"Invalid baseline report structure in {path}: expected JSON list or object")

    lookup: Dict[str, DocumentEvalResult] = {}
    for item in items:
        try:
            doc_res = DocumentEvalResult(**item)
            # Index by filepath and resolved path only (do not index by filename to prevent collision)
            lookup[doc_res.filepath] = doc_res
            try:
                resolved_key = str(Path(doc_res.filepath).resolve())
                lookup[resolved_key] = doc_res
            except Exception:
                pass
        except Exception as e:
            raise ValueError(f"Invalid document result in baseline {path}: {e}")

    return lookup


def compare_document_with_baseline(
    result: DocumentEvalResult,
    baseline_lookup: Dict[str, DocumentEvalResult],
    preset: PresetConfig,
    default_max_drop: float = 0.10,
) -> Tuple[DocumentEvalResult, bool, Optional[str]]:
    """Compares a current document result with its baseline counterpart.
    
    Returns (updated_result, has_regression, optional_truncation_warning).
    """
    # Match candidate by filepath or resolved path only
    match_key = None
    prev = None
    for key in (result.filepath, str(Path(result.filepath).resolve())):
        if key in baseline_lookup:
            prev = baseline_lookup[key]
            match_key = key
            break

    if prev is None:
        result.baseline_diff = BaselineDiff(status="new")
        return result, False, None

    # Check truncation mismatch
    trunc_mismatch = (prev.was_truncated != result.was_truncated)
    warning_msg = None
    if trunc_mismatch:
        warning_msg = (
            f"Truncation status differs for {result.filename} "
            f"(baseline was_truncated={prev.was_truncated}, current was_truncated={result.was_truncated}). "
            f"Scores may be shifted by truncation."
        )

    has_regression = False
    diff_questions: Dict[str, QuestionDiff] = {}

    for q_id, q_cfg in preset.questions.items():
        threshold = q_cfg.max_drop if (q_cfg and q_cfg.max_drop is not None) else default_max_drop

        curr_val: Optional[float] = None
        prev_val: Optional[float] = None

        if q_id in result.scores and q_id in prev.scores:
            curr_val = result.scores[q_id].normalized_score
            prev_val = prev.scores[q_id].normalized_score
        elif q_id in result.nouls and q_id in prev.nouls:
            if result.nouls[q_id].probability is not None and prev.nouls[q_id].probability is not None:
                curr_val = result.nouls[q_id].probability
                prev_val = prev.nouls[q_id].probability

        if curr_val is not None and prev_val is not None:
            delta = curr_val - prev_val
            is_risk_question = bool(q_cfg and q_cfg.max_threshold is not None)

            if is_risk_question:
                # For risk questions with max_threshold (e.g. has_secrets, has_pii, confidentiality_risk):
                # A rise in probability/risk is a regression
                rise = curr_val - prev_val
                regressed = rise > threshold

                diff_questions[q_id] = QuestionDiff(
                    previous=prev_val,
                    current=curr_val,
                    delta=delta,
                    max_drop=threshold,
                    regressed=regressed,
                )

                if regressed:
                    has_regression = True
                    result.passed_thresholds = False
                    result.violations.append(
                        f"Baseline risk rise: '{q_id}' rose by {rise:.2f} "
                        f"(prev: {prev_val:.2f}, curr: {curr_val:.2f}, max allowed rise: {threshold:.2f})"
                    )
            else:
                # For standard/min_threshold questions (e.g. clarity, completeness):
                # A drop in score is a regression
                drop = prev_val - curr_val
                regressed = drop > threshold

                diff_questions[q_id] = QuestionDiff(
                    previous=prev_val,
                    current=curr_val,
                    delta=delta,
                    max_drop=threshold,
                    regressed=regressed,
                )

                if regressed:
                    has_regression = True
                    result.passed_thresholds = False
                    result.violations.append(
                        f"Baseline drop: '{q_id}' dropped by {drop:.2f} "
                        f"(prev: {prev_val:.2f}, curr: {curr_val:.2f}, max allowed drop: {threshold:.2f})"
                    )

    result.baseline_diff = BaselineDiff(
        status="compared",
        baseline_filepath=prev.filepath,
        truncation_mismatch=trunc_mismatch,
        questions=diff_questions,
    )

    return result, has_regression, warning_msg
