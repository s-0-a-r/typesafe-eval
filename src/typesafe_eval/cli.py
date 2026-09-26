"""Command line interface for TypeSafe document evaluation."""

import sys
import glob
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console

from typesafe_eval import __version__
from typesafe_eval.presets import load_preset, list_builtin_presets
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.reporter import render_table, render_json, render_markdown

err_console = Console(stderr=True)

@click.command(name="typesafe-eval", context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("files", nargs=-1, type=str)
@click.option(
    "-p", "--preset",
    default="quality",
    help=f"Built-in preset to use ({', '.join(list_builtin_presets())}). Default: quality.",
)
@click.option(
    "-c", "--config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Custom YAML configuration file defining evaluation dimensions.",
)
@click.option(
    "-f", "--format", "output_format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output presentation format. Default: table.",
)
@click.option(
    "-o", "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Save report output to specified file path.",
)
@click.option(
    "--mask-secrets/--no-mask-secrets",
    default=True,
    help="Automatically redact detected API keys, credentials, and PII before API call. Default: enabled.",
)
@click.option(
    "--max-chars",
    type=int,
    default=25000,
    help="Maximum character threshold before safe head/tail truncation. Default: 25000.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate files and inputs using mock results without sending requests to TypeSafe API.",
)
@click.option(
    "--api-key",
    envvar="TYPESAFE_API_KEY",
    help="TypeSafe API key (falls back to TYPESAFE_API_KEY environment variable).",
)
@click.option(
    "--fail-on-threshold/--no-fail-on-threshold",
    default=True,
    help="Exit with non-zero status code (exit 1) if any threshold violation occurs. Default: enabled.",
)
@click.option(
    "--list-presets",
    is_flag=True,
    help="List all available built-in evaluation presets and exit.",
)
@click.version_option(version=__version__, prog_name="typesafe-eval")
def main(
    files: List[str],
    preset: str,
    config: Optional[Path],
    output_format: str,
    out: Optional[Path],
    mask_secrets: bool,
    max_chars: int,
    dry_run: bool,
    api_key: Optional[str],
    fail_on_threshold: bool,
    list_presets: bool,
):
    """Fast, typed multi-dimensional document evaluation CLI using TypeSafe API (Jev)."""
    if list_presets:
        click.echo("Available built-in presets:")
        for name in list_builtin_presets():
            p = load_preset(name)
            click.echo(f"  • {name:<12} : {p.title or p.name} ({p.description or ''})")
        sys.exit(0)

    if not files:
        err_console.print("[bold red]Error:[/bold red] No files or file patterns specified.")
        err_console.print("Usage: typesafe-eval [OPTIONS] <FILE_OR_GLOB>...")
        err_console.print("Example: typesafe-eval docs/*.md --preset quality")
        sys.exit(1)

    # 1. Resolve matched files
    resolved_paths: List[Path] = []
    for pattern in files:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            for m in matches:
                p = Path(m)
                if p.is_file() and p not in resolved_paths:
                    resolved_paths.append(p)
        else:
            p = Path(pattern)
            if p.is_file() and p not in resolved_paths:
                resolved_paths.append(p)

    if not resolved_paths:
        err_console.print(f"[bold red]Error:[/bold red] No valid files matched the pattern(s): {', '.join(files)}")
        sys.exit(1)

    # 2. Load preset configuration
    preset_target = str(config) if config else preset
    try:
        preset_cfg = load_preset(preset_target)
    except Exception as e:
        err_console.print(f"[bold red]Error loading preset:[/bold red] {e}")
        sys.exit(1)

    # 3. Initialize Evaluator
    evaluator = TypeSafeEvaluator(api_key=api_key)

    # 4. Evaluate documents
    results = []
    has_violations = False

    for path in resolved_paths:
        try:
            res = evaluator.evaluate_document(
                filepath=str(path),
                preset=preset_cfg,
                mask_secrets=mask_secrets,
                max_chars=max_chars,
                dry_run=dry_run,
            )
            results.append(res)
            if not res.passed_thresholds:
                has_violations = True
        except Exception as e:
            err_console.print(f"[bold red]Error evaluating {path}:[/bold red] {e}")
            sys.exit(1)

    # 5. Output handling
    if output_format == "table":
        render_table(results, preset_cfg)
    elif output_format == "json":
        json_output = render_json(results)
        click.echo(json_output)
    elif output_format == "markdown":
        md_output = render_markdown(results, preset_cfg)
        click.echo(md_output)

    # 6. Save to out file if requested
    if out:
        if output_format == "json":
            out.write_text(render_json(results), encoding="utf-8")
        elif output_format == "markdown":
            out.write_text(render_markdown(results, preset_cfg), encoding="utf-8")
        else:
            # Default to Markdown if table was rendered to console
            out.write_text(render_markdown(results, preset_cfg), encoding="utf-8")
        err_console.print(f"[green]Report saved successfully to:[/green] {out}")

    # 7. Threshold failure exit
    if fail_on_threshold and has_violations:
        sys.exit(1)

if __name__ == "__main__":
    main()
