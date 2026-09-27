"""Rich terminal rendering, JSON export, and Markdown report generator."""

import json
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from typesafe_eval.models import DocumentEvalResult, PresetConfig

console = Console()

def format_score_badge(val: float) -> str:
    pct = val * 100
    if val >= 0.75:
        return f"[bold green]{pct:.0f}%[/bold green]"
    elif val >= 0.50:
        return f"[bold yellow]{pct:.0f}%[/bold yellow]"
    else:
        return f"[bold red]{pct:.0f}%[/bold red]"

def render_table(results: List[DocumentEvalResult], preset: PresetConfig) -> None:
    """Renders evaluation results as an interactive Rich terminal table."""
    table = Table(
        title=f"TypeSafe Evaluation Report — Preset: [bold cyan]{preset.title or preset.name}[/bold cyan]",
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
        if res.redactions_count > 0:
            doc_display += f" [dim red]({res.redactions_count} masked)[/dim red]"
        row_cells.append(doc_display)

        for q_id, q_cfg in preset.questions.items():
            if q_cfg.type == "score" and q_id in res.scores:
                s_obj = res.scores[q_id]
                badge = format_score_badge(s_obj.normalized_score)
                row_cells.append(f"{badge}\n[dim]{s_obj.score:.1f}/{s_obj.max_score:.0f} (c: {s_obj.confidence:.2f})[/dim]")
            elif q_cfg.type == "noul" and q_id in res.nouls:
                prob = res.nouls[q_id].probability
                if prob is not None:
                    badge = format_score_badge(prob)
                    row_cells.append(f"{badge}\n[dim]p(yes)[/dim]")
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

        if res.passed_thresholds:
            row_cells.append("[bold green]✔ PASS[/bold green]")
        else:
            row_cells.append("[bold red]✘ FAIL[/bold red]")

        table.add_row(*row_cells)

    console.print()
    console.print(table)

    # Print violations summary if any
    failed_items = [r for r in results if not r.passed_thresholds]
    if failed_items:
        console.print()
        violation_texts = []
        for r in failed_items:
            for v in r.violations:
                violation_texts.append(f"• [bold red]{r.filename}[/bold red]: {v}")
        console.print(
            Panel(
                "\n".join(violation_texts),
                title="[bold red]Threshold Violations[/bold red]",
                border_style="red",
            )
        )
    console.print()


def render_markdown(results: List[DocumentEvalResult], preset: PresetConfig) -> str:
    """Renders evaluation report into Markdown format."""
    lines = [
        f"# TypeSafe Evaluation Report",
        f"",
        f"**Preset:** {preset.title or preset.name}  ",
        f"**Description:** {preset.description or 'N/A'}  ",
        f"",
        f"| Document | " + " | ".join(q.label or q_id for q_id, q in preset.questions.items()) + " | Composite | Status |",
        f"| :--- | " + " | ".join([":---:"] * len(preset.questions)) + " | :---: | :---: |",
    ]

    for res in results:
        cells = [res.filename]
        for q_id, q_cfg in preset.questions.items():
            if q_cfg.type == "score" and q_id in res.scores:
                s = res.scores[q_id]
                cells.append(f"{s.normalized_score * 100:.0f}% ({s.score:.1f}/{s.max_score:.0f}, conf: {s.confidence:.2f})")
            elif q_cfg.type == "noul" and q_id in res.nouls:
                n = res.nouls[q_id]
                if n.probability is not None:
                    cells.append(f"{n.probability * 100:.0f}% (p={n.probability:.2f})")
                else:
                    cells.append(f"overridden ({n.overridden_by or 'preflight'})")
            elif q_cfg.type == "choice" and q_id in res.choices:
                c = res.choices[q_id]
                cells.append(f"`{c.choice}` (conf: {c.confidence:.2f})")
            else:
                cells.append("-")

        composite_str = f"{res.composite_score * 100:.0f}%" if res.composite_score is not None else "-"
        status_str = "PASS" if res.passed_thresholds else "FAIL"
        cells.append(composite_str)
        cells.append(status_str)

        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    failed = [r for r in results if not r.passed_thresholds]
    if failed:
        lines.append("## Threshold Violations")
        for r in failed:
            for v in r.violations:
                lines.append(f"- **{r.filename}**: {v}")
        lines.append("")

    return "\n".join(lines)


def render_json(results: List[DocumentEvalResult]) -> str:
    """Exports results as structured JSON string."""
    data = [res.model_dump() for res in results]
    return json.dumps(data, indent=2, ensure_ascii=False)
