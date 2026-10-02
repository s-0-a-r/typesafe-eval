"""Command line interface for TypeSafe document evaluation and validation."""

import sys
import glob
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.markup import escape

from typesafe_eval import __version__
from typesafe_eval.presets import load_preset, list_builtin_presets
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.reporter import render_table, render_json, render_markdown
from typesafe_eval.baseline import load_baseline, compare_document_with_baseline
from typesafe_eval.validator import (
    load_labels_file,
    validate_labels_preset,
    run_validation,
    render_validation_table,
    render_validation_json,
    render_validation_markdown,
    generate_ablation_variants,
)

err_console = Console(stderr=True)


class DefaultGroup(click.Group):
    """Click Group that defaults to a specified command if no subcommand matches."""

    def __init__(self, *args, **kwargs):
        self.default_cmd_name = kwargs.pop("default_if_no_match", None)
        super().__init__(*args, **kwargs)

    def parse_args(self, ctx, args):
        if not args:
            if self.default_cmd_name:
                args = [self.default_cmd_name]
            return super().parse_args(ctx, args)
        cmd_name = args[0]
        if cmd_name not in self.commands:
            if self.default_cmd_name and cmd_name not in ("--help", "-h", "--version"):
                args.insert(0, self.default_cmd_name)
        return super().parse_args(ctx, args)


@click.group(
    name="typesafe-eval",
    cls=DefaultGroup,
    default_if_no_match="eval",
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.version_option(version=__version__, prog_name="typesafe-eval")
def main():
    """Fast, typed multi-dimensional document evaluation CLI using TypeSafe API (Jev)."""
    pass


@main.command(name="eval", context_settings=dict(help_option_names=["-h", "--help"]))
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
    "--mask/--no-mask",
    default=True,
    help="Automatically redact detected API keys, credentials, and PII before API call. Default: enabled.",
)
@click.option(
    "--max-chars",
    type=click.IntRange(min=1),
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
    "--baseline",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Previous JSON report to compare against and detect score regressions.",
)
@click.option(
    "--list-presets",
    is_flag=True,
    help="List all available built-in evaluation presets and exit.",
)
def eval_command(
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
    baseline: Optional[Path],
    list_presets: bool,
):
    """Evaluate documents against quality, safety, or custom evaluation presets."""
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
        sys.exit(2)

    # 1. Resolve matched files
    resolved_paths: List[Path] = []
    for pattern in files:
        if not glob.has_magic(pattern):
            p = Path(pattern)
            if not p.is_file():
                err_console.print(f"[bold red]Error:[/bold red] File not found: {pattern}")
                sys.exit(2)
            if p not in resolved_paths:
                resolved_paths.append(p)
        else:
            matches = glob.glob(pattern, recursive=True)
            for m in matches:
                p = Path(m)
                if p.is_file() and p not in resolved_paths:
                    resolved_paths.append(p)

    if not resolved_paths:
        err_console.print(f"[bold red]Error:[/bold red] No valid files matched the pattern(s): {', '.join(files)}")
        sys.exit(2)

    # 2. Load preset configuration
    preset_target = str(config) if config else preset
    try:
        preset_cfg = load_preset(preset_target)
    except Exception as e:
        err_console.print(f"[bold red]Error loading preset:[/bold red] {e}")
        sys.exit(2)

    # 3. Load baseline if specified
    baseline_lookup = None
    if baseline:
        try:
            baseline_lookup = load_baseline(baseline, expected_preset=preset_cfg.name)
        except FileNotFoundError as e:
            err_console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(2)
        except Exception as e:
            err_console.print(f"[bold red]Error loading baseline:[/bold red] {e}")
            sys.exit(2)

    # 4. Initialize Evaluator
    evaluator = TypeSafeEvaluator(api_key=api_key)

    # 5. Evaluate documents
    results = []
    has_violations = False
    has_errors = False

    for path in resolved_paths:
        try:
            res = evaluator.evaluate_document(
                filepath=str(path),
                preset=preset_cfg,
                mask_secrets=mask_secrets,
                max_chars=max_chars,
                dry_run=dry_run,
            )

            # Compare against baseline if active
            if baseline_lookup is not None:
                try:
                    res, has_reg, warn_msg = compare_document_with_baseline(
                        result=res,
                        baseline_lookup=baseline_lookup,
                        preset=preset_cfg,
                        default_max_drop=0.10,
                    )
                except ValueError as e:
                    err_console.print(f"[bold red]Error comparing baseline:[/bold red] {e}")
                    sys.exit(2)
                if warn_msg:
                    click.echo(f"Warning: {warn_msg}", err=True)
                if has_reg:
                    has_violations = True

            results.append(res)
            if not res.passed_thresholds and not res.mock:
                has_violations = True
        except Exception as e:
            click.echo(f"{path}: {e}", err=True)
            has_errors = True

    # 5. Output handling
    if results or output_format == "json":
        if output_format == "table":
            render_table(results, preset_cfg)
        elif output_format == "json":
            json_output = render_json(results)
            click.echo(json_output)
        elif output_format == "markdown":
            md_output = render_markdown(results, preset_cfg)
            click.echo(md_output)

    # 6. Save to out file if requested
    if out and (results or output_format == "json"):
        if output_format == "json":
            out.write_text(render_json(results), encoding="utf-8")
        elif output_format == "markdown":
            out.write_text(render_markdown(results, preset_cfg), encoding="utf-8")
        else:
            out.write_text(render_markdown(results, preset_cfg), encoding="utf-8")
        err_console.print(f"[green]Report saved successfully to:[/green] {out}")

    # 7. Exit code resolution (1 takes precedence over 3; dry-run exits 3 on file errors, 0 otherwise)
    if dry_run:
        if has_errors:
            sys.exit(3)
        sys.exit(0)
    elif fail_on_threshold and has_violations:
        sys.exit(1)
    elif has_errors:
        sys.exit(3)
    else:
        sys.exit(0)


@main.command(name="validate", context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("labels_file", required=False, type=str)
@click.option(
    "--runs",
    type=int,
    default=None,
    help="Number of evaluation runs per document/pair (default: 3, or set in labels file).",
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
    "--ablate",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Generate 'one section removed' variants from a markdown document split on '## ' headings.",
)
@click.option(
    "--ablate-out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for ablated document variants (defaults to document directory).",
)
@click.option(
    "--ablate-preset",
    default="design_doc",
    help="Preset name to specify in the generated labels.yaml (default: design_doc).",
)
@click.option(
    "--ablate-labels-out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write starter labels.yaml to this file path.",
)
@click.option(
    "--mask-secrets/--no-mask-secrets",
    "--mask/--no-mask",
    default=True,
    help="Automatically redact detected API keys, credentials, and PII before API call. Default: enabled.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run validation with mock evaluator results.",
)
@click.option(
    "--api-key",
    envvar="TYPESAFE_API_KEY",
    help="TypeSafe API key (falls back to TYPESAFE_API_KEY environment variable).",
)
def validate_command(
    labels_file: Optional[str],
    runs: Optional[int],
    output_format: str,
    out: Optional[Path],
    ablate: Optional[Path],
    ablate_out_dir: Optional[Path],
    ablate_preset: str,
    ablate_labels_out: Optional[Path],
    dry_run: bool,
    api_key: Optional[str],
    mask_secrets: bool = True,
):
    """Run validation across fixed test documents using a labels.yaml specification or generate ablation variants."""
    # Handle --ablate helper mode
    if ablate:
        try:
            variants, labels_yaml = generate_ablation_variants(
                doc_path=ablate,
                out_dir=ablate_out_dir,
                preset_name=ablate_preset,
            )
            click.echo(f"Generated {len(variants)} ablation variants:")
            for v in variants:
                click.echo(f"  • {v.name}")
            click.echo("\nStarter labels configuration:")
            click.echo(labels_yaml)
            target_labels_out = ablate_labels_out or out
            if target_labels_out:
                target_labels_out.write_text(labels_yaml, encoding="utf-8")
                err_console.print(f"[green]Labels configuration saved to:[/green] {target_labels_out}")
            sys.exit(0)
        except Exception as e:
            err_console.print(f"[bold red]Ablation error:[/bold red] {e}")
            sys.exit(2)

    if not labels_file:
        err_console.print("[bold red]Error:[/bold red] No labels file specified.")
        err_console.print("Usage: typesafe-eval validate <labels.yaml> [OPTIONS]")
        err_console.print("       typesafe-eval validate --ablate <doc.md> [OPTIONS]")
        sys.exit(2)

    # Load labels file
    try:
        labels_cfg, base_dir = load_labels_file(labels_file)
    except FileNotFoundError as e:
        err_console.print(f"[bold red]Error:[/bold red] {escape(str(e))}")
        sys.exit(2)
    except Exception as e:
        err_console.print(f"[bold red]Error loading labels file:[/bold red] {escape(str(e))}")
        sys.exit(2)

    # Validate preset and questions
    try:
        preset_cfg = validate_labels_preset(labels_cfg, base_dir)
    except Exception as e:
        err_console.print(f"[bold red]Validation setup error:[/bold red] {e}")
        sys.exit(2)

    # Initialize evaluator
    evaluator = TypeSafeEvaluator(api_key=api_key)

    if not dry_run and not evaluator.api_key:
        click.echo(
            "No TypeSafe API key provided. Set the TYPESAFE_API_KEY environment variable "
            "or pass --api-key / specify in configuration.",
            err=True,
        )
        sys.exit(3)

    # Run validation
    try:
        report, has_runtime_error = run_validation(
            labels_cfg=labels_cfg,
            base_dir=base_dir,
            evaluator=evaluator,
            runs_override=runs,
            dry_run=dry_run,
            preset_cfg=preset_cfg,
            mask_secrets=mask_secrets,
        )
    except Exception as e:
        err_console.print(f"[bold red]Validation setup error:[/bold red] {e}")
        sys.exit(2)

    # Output unplaced warnings to stderr
    for w in report.unplaced_warnings:
        click.echo(f"Warning: {w}", err=True)

    # Output handling
    if output_format == "table":
        render_validation_table(report)
    elif output_format == "json":
        json_out = render_validation_json(report)
        click.echo(json_out)
    elif output_format == "markdown":
        md_out = render_validation_markdown(report)
        click.echo(md_out)

    # Save to out if specified
    if out:
        if output_format == "json":
            out.write_text(render_validation_json(report), encoding="utf-8")
        elif output_format == "markdown":
            out.write_text(render_validation_markdown(report), encoding="utf-8")
        else:
            out.write_text(render_validation_markdown(report), encoding="utf-8")
        err_console.print(f"[green]Report saved successfully to:[/green] {out}")

    # Exit code resolution (1 over 3 precedence; dry-run exits 3 on file/runtime errors, 0 otherwise)
    if dry_run:
        if has_runtime_error:
            sys.exit(3)
        sys.exit(0)
    elif not report.all_passed:
        sys.exit(1)
    elif has_runtime_error:
        sys.exit(3)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
