"""Rich terminal rendering, JSON export, and Markdown report generator."""

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from typesafe_eval.models import NEAR_THRESHOLD_MARGIN, DocumentEvalResult, PresetConfig

console = Console()


def format_score_badge(val: float, invert: bool = False) -> str:
    pct = val * 100
    if invert:
        if val <= 0.25:
            return f"[bold green]{pct:.0f}%[/bold green]"
        elif val <= 0.50:
            return f"[bold yellow]{pct:.0f}%[/bold yellow]"
        else:
            return f"[bold red]{pct:.0f}%[/bold red]"
    else:
        if val >= 0.75:
            return f"[bold green]{pct:.0f}%[/bold green]"
        elif val >= 0.50:
            return f"[bold yellow]{pct:.0f}%[/bold yellow]"
        else:
            return f"[bold red]{pct:.0f}%[/bold red]"


def render_table(results: list[DocumentEvalResult], preset: PresetConfig) -> None:
    """Renders evaluation results as an interactive Rich terminal table."""
    is_mock = any(r.mock for r in results)
    title_prefix = "TypeSafe Evaluation Report (MOCK)" if is_mock else "TypeSafe Evaluation Report"
    table = Table(
        title=f"{title_prefix} — Preset: [bold cyan]{preset.title or preset.name}[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )

    table.add_column("Document", style="cyan", no_wrap=True)

    # Add column for each question
    for q_id, q_cfg in preset.questions.items():
        col_name = q_cfg.label or q_id
        table.add_column(col_name, justify="center")

    if any(r.composite_score is not None for r in results):
        table.add_column("Composite", justify="center")

    table.add_column("Status", justify="center")

    for res in results:
        row_cells = []
        doc_display = res.filename
        if res.was_truncated:
            doc_display += " [dim](truncated)[/dim]"
        if res.api_calls > 1:
            doc_display += f" [dim cyan]({res.api_calls} calls)[/dim cyan]"
        if res.redactions_count > 0:
            doc_display += f" [dim red]({res.redactions_count} masked)[/dim red]"
        row_cells.append(doc_display)

        b_diff = res.baseline_diff

        for q_id, q_cfg in preset.questions.items():
            diff_info = (
                b_diff.questions.get(q_id) if b_diff and b_diff.status == "compared" else None
            )
            is_risk = q_cfg.max_threshold is not None

            if q_cfg.type == "score" and q_id in res.scores:
                s_obj = res.scores[q_id]
                badge = format_score_badge(s_obj.normalized_score, invert=is_risk)
                near_marker = " [yellow]~[/yellow]" if s_obj.near_threshold else ""
                cell_text = (
                    f"{badge}{near_marker}\n[dim]{s_obj.score:.1f}/{s_obj.max_score:.0f}[/dim]"
                )
                if diff_info:
                    delta_color = (
                        "red"
                        if diff_info.regressed
                        else ("green" if diff_info.delta > 0 else "dim")
                    )
                    cell_text += f"\n[{delta_color}]prev: {diff_info.previous * 100:.0f}% (Δ {diff_info.delta:+.2f})[/{delta_color}]"
                row_cells.append(cell_text)
            elif q_cfg.type == "noul" and q_id in res.nouls:
                prob = res.nouls[q_id].probability
                if prob is not None:
                    badge = format_score_badge(prob, invert=is_risk)
                    near_marker = " [yellow]~[/yellow]" if res.nouls[q_id].near_threshold else ""
                    cell_text = f"{badge}{near_marker}\n[dim]p(yes)[/dim]"
                    if diff_info:
                        delta_color = (
                            "red"
                            if diff_info.regressed
                            else ("green" if diff_info.delta > 0 else "dim")
                        )
                        cell_text += f"\n[{delta_color}]prev: {diff_info.previous * 100:.0f}% (Δ {diff_info.delta:+.2f})[/{delta_color}]"
                    row_cells.append(cell_text)
                else:
                    row_cells.append("[dim red]overridden[/dim red]\n[dim]preflight[/dim]")
            elif q_cfg.type == "choice" and q_id in res.choices:
                choice = res.choices[q_id].choice
                conf = res.choices[q_id].confidence
                row_cells.append(f"[bold]{choice}[/bold]\n[dim]c: {conf:.2f}[/dim]")
            else:
                row_cells.append("-")

        if any(r.composite_score is not None for r in results):
            if res.composite_score is not None:
                row_cells.append(format_score_badge(res.composite_score))
            else:
                row_cells.append("-")

        # Status cell
        status_suffix = ""
        if b_diff and b_diff.status == "new":
            status_suffix = " (new)"

        if res.mock:
            row_cells.append(f"[bold yellow]N/A{status_suffix}[/bold yellow]")
        elif res.passed_thresholds:
            row_cells.append(f"[bold green]✔ PASS{status_suffix}[/bold green]")
        else:
            row_cells.append(f"[bold red]✘ FAIL{status_suffix}[/bold red]")

        table.add_row(*row_cells)

    console.print()
    console.print(table)
    if is_mock:
        console.print("[dim]Mode: MOCK (dry-run, no API calls made)[/dim]")

    has_near_threshold = any(s.near_threshold for r in results for s in r.scores.values()) or any(
        n.near_threshold for r in results for n in r.nouls.values()
    )
    if has_near_threshold:
        console.print(
            f"[dim]~: value is within ±{NEAR_THRESHOLD_MARGIN:.2f} of threshold (near_threshold)[/dim]"
        )

    for r in results:
        near_cands = []
        all_cands = (
            r.email_evaluations
            + r.phone_evaluations
            + r.ip_evaluations
            + r.url_evaluations
            + r.secret_evaluations
        )
        for c in all_cands:
            if c.near_threshold and c.probability is not None:
                near_cands.append(f"{c.placeholder} {c.outcome} (p={c.probability:.2f})")
        if near_cands:
            cand_str = ", ".join(near_cands)
            if len(results) > 1:
                console.print(f"[dim]{r.filename}: ~ near threshold: {cand_str}[/dim]")
            else:
                console.print(f"[dim]~ near threshold: {cand_str}[/dim]")

    # Print baseline truncation warnings if any
    for r in results:
        if r.baseline_diff and r.baseline_diff.truncation_mismatch:
            console.print(
                f"[bold yellow]Warning:[/bold yellow] Truncation status differs for {r.filename} "
                f"between baseline and current evaluation. Scores may be shifted."
            )

    # Print warnings summary if any
    warning_items = [r for r in results if r.warnings and not r.mock]
    if warning_items:
        console.print()
        warning_texts = []
        for r in warning_items:
            for w in r.warnings:
                warning_texts.append(f"• [bold yellow]{r.filename}[/bold yellow]: {w}")
        console.print(
            Panel(
                "\n".join(warning_texts),
                title="[bold yellow]Warnings[/bold yellow]",
                border_style="yellow",
            )
        )

    # Print violations summary if any
    failed_items = [r for r in results if not r.passed_thresholds and not r.mock]
    if failed_items:
        console.print()
        violation_texts = []
        for r in failed_items:
            for v in r.violations:
                violation_texts.append(f"• [bold red]{r.filename}[/bold red]: {v}")
        console.print(
            Panel(
                "\n".join(violation_texts),
                title="[bold red]Threshold & Baseline Violations[/bold red]",
                border_style="red",
            )
        )
    console.print()


def render_markdown(results: list[DocumentEvalResult], preset: PresetConfig) -> str:
    """Renders evaluation report into Markdown format."""
    is_mock = any(r.mock for r in results)
    title = "# TypeSafe Evaluation Report (MOCK)" if is_mock else "# TypeSafe Evaluation Report"
    lines = [
        title,
        "",
        f"**Preset:** {preset.title or preset.name}  ",
        f"**Description:** {preset.description or 'N/A'}  ",
    ]
    if is_mock:
        lines.append("**Mode:** MOCK (dry-run, no API calls made)  ")
    lines.extend(
        [
            "",
            "| Document | "
            + " | ".join(q.label or q_id for q_id, q in preset.questions.items())
            + " | Composite | Status |",
            "| :--- | " + " | ".join([":---:"] * len(preset.questions)) + " | :---: | :---: |",
        ]
    )

    for res in results:
        doc_cell = res.filename
        if res.was_truncated:
            doc_cell += " *(truncated)*"
        if res.api_calls > 1:
            doc_cell += f" *({res.api_calls} calls)*"
        cells = [doc_cell]
        b_diff = res.baseline_diff

        for q_id, q_cfg in preset.questions.items():
            diff_info = (
                b_diff.questions.get(q_id) if b_diff and b_diff.status == "compared" else None
            )

            if q_cfg.type == "score" and q_id in res.scores:
                s = res.scores[q_id]
                near_marker = " ~" if s.near_threshold else ""
                val_str = f"{s.normalized_score * 100:.0f}%{near_marker}"
                if diff_info:
                    val_str += (
                        f"<br>(prev: {diff_info.previous * 100:.0f}%, Δ: {diff_info.delta:+.2f})"
                    )
                cells.append(val_str)
            elif q_cfg.type == "noul" and q_id in res.nouls:
                n = res.nouls[q_id]
                if n.probability is not None:
                    near_marker = " ~" if n.near_threshold else ""
                    val_str = f"{n.probability * 100:.0f}%{near_marker}"
                    if diff_info:
                        val_str += f"<br>(prev: {diff_info.previous * 100:.0f}%, Δ: {diff_info.delta:+.2f})"
                    cells.append(val_str)
                else:
                    cells.append(f"overridden ({n.overridden_by or 'preflight'})")
            elif q_cfg.type == "choice" and q_id in res.choices:
                c = res.choices[q_id]
                cells.append(f"`{c.choice}` (conf: {c.confidence:.2f})")
            else:
                cells.append("-")

        composite_str = (
            f"{res.composite_score * 100:.0f}%" if res.composite_score is not None else "-"
        )
        status_suffix = " (new)" if (b_diff and b_diff.status == "new") else ""
        if res.mock:
            status_str = f"N/A{status_suffix}"
        elif res.passed_thresholds:
            status_str = f"PASS{status_suffix}"
        else:
            status_str = f"FAIL{status_suffix}"
        cells.append(composite_str)
        cells.append(status_str)

        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")

    has_near_threshold = any(s.near_threshold for r in results for s in r.scores.values()) or any(
        n.near_threshold for r in results for n in r.nouls.values()
    )
    if has_near_threshold:
        lines.append(
            f"*~: value is within ±{NEAR_THRESHOLD_MARGIN:.2f} of threshold (near_threshold)*"
        )
        lines.append("")

    for r in results:
        near_cands = []
        all_cands = (
            r.email_evaluations
            + r.phone_evaluations
            + r.ip_evaluations
            + r.url_evaluations
            + r.secret_evaluations
        )
        for cand in all_cands:
            if cand.near_threshold and cand.probability is not None:
                near_cands.append(f"{cand.placeholder} {cand.outcome} (p={cand.probability:.2f})")
        if near_cands:
            cand_str = ", ".join(near_cands)
            if len(results) > 1:
                lines.append(f"{r.filename}: ~ near threshold: {cand_str}")
            else:
                lines.append(f"~ near threshold: {cand_str}")
            lines.append("")

    # Baseline diff table if baseline was compared
    compared_docs = [r for r in results if r.baseline_diff and r.baseline_diff.status == "compared"]
    if compared_docs:
        lines.append("## Baseline Comparison Details")
        lines.append("")
        lines.append(
            "| Document | Question | Previous | Current | Δ (Drop) | Max Allowed Drop | Result |"
        )
        lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")
        for r in compared_docs:
            assert r.baseline_diff is not None
            for q_id, q_diff in r.baseline_diff.questions.items():
                status_badge = "**REGRESSED**" if q_diff.regressed else "OK"
                lines.append(
                    f"| {r.filename} | `{q_id}` | {q_diff.previous:.2f} | {q_diff.current:.2f} | "
                    f"{q_diff.delta:+.2f} | {q_diff.max_drop:.2f} | {status_badge} |"
                )
        lines.append("")

    warned = [r for r in results if r.warnings and not r.mock]
    if warned:
        lines.append("## Warnings")
        lines.append("")
        for r in warned:
            for w in r.warnings:
                lines.append(f"- **{r.filename}**: {w}")
        lines.append("")

    failed = [r for r in results if not r.passed_thresholds and not r.mock]
    if failed:
        lines.append("## Threshold & Baseline Violations")
        lines.append("")
        for r in failed:
            for v in r.violations:
                lines.append(f"- **{r.filename}**: {v}")
        lines.append("")

    return "\n".join(lines)


def render_json(results: list[DocumentEvalResult]) -> str:
    """Exports results as structured JSON string."""
    data = [res.model_dump() for res in results]
    return json.dumps(data, indent=2, ensure_ascii=False)
