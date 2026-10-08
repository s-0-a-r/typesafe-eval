"""Command line interface for TypeSafe document evaluation and validation."""

import glob
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.markup import escape

from typesafe_eval import __version__
from typesafe_eval.baseline import compare_document_with_baseline, load_baseline
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.models import DocumentEvalResult, PresetConfig
from typesafe_eval.presets import (
    is_default_ignored,
    is_path_excluded,
    list_builtin_presets,
    load_preset,
    load_project_config,
)
from typesafe_eval.reporter import (
    render_github_annotations,
    render_json,
    render_markdown,
    render_table,
)
from typesafe_eval.validator import (
    generate_ablation_variants,
    load_labels_file,
    render_validation_json,
    render_validation_markdown,
    render_validation_table,
    run_validation,
    validate_labels_preset,
)

err_console = Console(stderr=True)


def get_git_changed_files(staged: bool = False, since: str | None = None) -> list[str]:
    """Retrieves list of modified/added files from git."""
    git_env = dict(os.environ)
    if "GIT_CONFIG_GLOBAL" not in git_env:
        git_env["GIT_CONFIG_GLOBAL"] = "/dev/null"

    try:
        root_proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            env=git_env,
        )
        repo_root = Path(root_proc.stdout.strip())
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else str(e)
        raise RuntimeError(f"Not a git repository: {err_msg}") from e
    except FileNotFoundError as e:
        raise RuntimeError("git executable not found in PATH") from e

    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR"]
    if staged:
        cmd.append("--cached")
    if since:
        cmd.append(since)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, env=git_env)
        files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        result = []
        for f in files:
            full_path = (repo_root / f).resolve()
            if full_path.is_file():
                result.append(str(full_path))
        return result
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else str(e)
        raise RuntimeError(f"Git diff extraction failed: {err_msg}") from e


DEFAULT_EVAL_EXTENSIONS = {
    ".md",
    ".markdown",
    ".mdown",
    ".txt",
    ".text",
    ".rst",
    ".adoc",
    ".asciidoc",
    ".json",
    ".yaml",
    ".yml",
}


def _emit_empty_diff_result(
    output_format: str,
    out: Path | None,
    msg: str = "No modified or staged files matched evaluation criteria.",
) -> None:
    """Emits clean result when no modified or staged files match criteria."""
    if output_format == "json":
        out_content = render_json([])
        if out:
            out.write_text(out_content, encoding="utf-8")
        else:
            click.echo(out_content)
    else:
        if out:
            out.write_text(msg + "\n", encoding="utf-8")
        else:
            click.echo(msg)


class DefaultGroup(click.Group):
    """Click Group that defaults to a specified command if no subcommand matches."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.default_cmd_name: str | None = kwargs.pop("default_if_no_match", None)
        super().__init__(*args, **kwargs)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
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
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__, prog_name="typesafe-eval")
def main() -> None:
    """Fast, typed multi-dimensional document evaluation CLI using TypeSafe API (Jev)."""
    pass


@main.command(name="eval", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("files", nargs=-1, type=str)
@click.option(
    "-p",
    "--preset",
    default=None,
    help=f"Built-in preset to use ({', '.join(list_builtin_presets())}). Default: project config or quality.",
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Custom YAML configuration file defining evaluation dimensions.",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "markdown", "github"], case_sensitive=False),
    default="table",
    help="Output presentation format. Default: table.",
)
@click.option(
    "-o",
    "--out",
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
    "--offline",
    "--rules-only",
    is_flag=True,
    default=False,
    help="Run static regex rule checks offline without TypeSafe API (no API key required).",
)
@click.option(
    "--api-key",
    envvar="TYPESAFE_API_KEY",
    help="TypeSafe or OpenAI API key (falls back to TYPESAFE_API_KEY or OPENAI_API_KEY).",
)
@click.option(
    "--provider",
    type=click.Choice(["auto", "openai", "typesafe", "jev"], case_sensitive=False),
    default="auto",
    help="Decision provider backend (auto, openai, typesafe). Default: auto.",
)
@click.option(
    "--model",
    default=None,
    help="Model override (e.g. gpt-6-luna for OpenAI, jev-1.13.0 for TypeSafe).",
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
    "-j",
    "--concurrency",
    type=click.IntRange(min=1),
    default=4,
    help="Number of concurrent worker threads for parallel document evaluation. Default: 4.",
)
@click.option(
    "--staged",
    is_flag=True,
    help="Evaluate only files staged for git commit.",
)
@click.option(
    "--since",
    "--changed-since",
    "changed_since",
    type=str,
    default=None,
    help="Evaluate files modified or added in git since the specified commit or branch reference.",
)
@click.option(
    "--list-presets",
    is_flag=True,
    help="List all available built-in evaluation presets and exit.",
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Enable or disable evaluation result cache. Default: enabled.",
)
@click.option(
    "--cache-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Custom directory for caching evaluation results.",
)
@click.option(
    "-e",
    "--exclude",
    "exclude_patterns",
    multiple=True,
    type=str,
    help="Glob pattern(s) to exclude from evaluation (can be specified multiple times).",
)
@click.option(
    "--include-images/--no-include-images",
    "--multimodal/--no-multimodal",
    "include_images",
    default=None,
    help="Evaluate embedded markdown/HTML images alongside text (OpenAI Decisions API). Default: disabled.",
)
@click.option(
    "--max-images-per-doc",
    "--max-images",
    "max_images_per_doc",
    type=click.IntRange(min=1, max=128),
    default=None,
    help="Maximum images per document to evaluate (1-128). Default: 5 or config value.",
)
def eval_command(
    files: list[str],
    preset: str | None,
    config: Path | None,
    output_format: str,
    out: Path | None,
    mask_secrets: bool,
    max_chars: int,
    dry_run: bool,
    offline: bool,
    api_key: str | None,
    provider: str,
    model: str | None,
    fail_on_threshold: bool,
    baseline: Path | None,
    concurrency: int,
    staged: bool,
    changed_since: str | None,
    list_presets: bool,
    cache: bool,
    cache_dir: Path | None,
    exclude_patterns: tuple[str, ...],
    include_images: bool | None,
    max_images_per_doc: int | None,
) -> None:
    """Evaluate documents against quality, safety, or custom evaluation presets."""
    if list_presets:
        click.echo("Available built-in presets:")
        for name in list_builtin_presets():
            loaded_p = load_preset(name)
            click.echo(
                f"  • {name:<12} : {loaded_p.title or loaded_p.name} ({loaded_p.description or ''})"
            )
        sys.exit(0)

    # 1. Load preset configuration early (needed for project config & exclude list)
    preset_cfg: PresetConfig
    if config:
        try:
            preset_cfg = load_preset(str(config))
        except Exception as e:
            err_console.print(f"[bold red]Error loading preset:[/bold red] {e}")
            sys.exit(2)
    elif preset is not None:
        try:
            preset_cfg = load_preset(preset)
        except Exception as e:
            err_console.print(f"[bold red]Error loading preset:[/bold red] {e}")
            sys.exit(2)
    else:
        try:
            auto_cfg, _ = load_project_config()
            if auto_cfg is not None:
                preset_cfg = auto_cfg
            else:
                preset_cfg = load_preset("quality")
        except Exception as e:
            err_console.print(f"[bold red]Error loading discovered config:[/bold red] {e}")
            sys.exit(2)

    # Git diff resolution if requested
    git_files: list[Path] | None = None
    if staged or changed_since:
        try:
            raw_git_files = get_git_changed_files(staged=staged, since=changed_since)
            git_files = [Path(f).resolve() for f in raw_git_files]
        except RuntimeError as e:
            err_console.print(f"[bold red]Git Error:[/bold red] {e}")
            sys.exit(2)

    if not files and git_files is None:
        err_console.print("[bold red]Error:[/bold red] No files or file patterns specified.")
        err_console.print("Usage: typesafe-eval [OPTIONS] <FILE_OR_GLOB>...")
        err_console.print("Example: typesafe-eval docs/*.md --preset quality")
        sys.exit(2)

    # 2. Resolve matched files
    resolved_paths: list[Path] = []
    had_file_matches = False

    if files:
        for pattern in files:
            if not glob.has_magic(pattern):
                doc_p = Path(pattern)
                if not doc_p.is_file():
                    err_console.print(f"[bold red]Error:[/bold red] File not found: {pattern}")
                    sys.exit(2)
                if doc_p not in resolved_paths:
                    resolved_paths.append(doc_p)
                    had_file_matches = True
            else:
                matches = glob.glob(pattern, recursive=True)
                for m in matches:
                    doc_p = Path(m)
                    if doc_p.is_file():
                        had_file_matches = True
                        if not is_default_ignored(doc_p) and doc_p not in resolved_paths:
                            resolved_paths.append(doc_p)

        if git_files is not None:
            git_files_set = {f.resolve() for f in git_files}
            resolved_paths = [p for p in resolved_paths if p.resolve() in git_files_set]
    else:
        assert git_files is not None
        had_file_matches = bool(git_files)
        resolved_paths = [
            p
            for p in git_files
            if p.suffix.lower() in DEFAULT_EVAL_EXTENSIONS and not is_default_ignored(p)
        ]

    # 3. Apply exclusion rules from CLI options and preset configuration
    combined_excludes = list(exclude_patterns) + (preset_cfg.exclude or [])
    if combined_excludes:
        resolved_paths = [
            p for p in resolved_paths if not is_path_excluded(p, combined_excludes, root=Path.cwd())
        ]

    if not resolved_paths:
        if staged or changed_since:
            _emit_empty_diff_result(output_format=output_format, out=out)
            sys.exit(0)
        if had_file_matches:
            _emit_empty_diff_result(
                output_format=output_format,
                out=out,
                msg="No files matched evaluation criteria (all matched files were excluded).",
            )
            sys.exit(0)
        err_console.print(
            f"[bold red]Error:[/bold red] No valid files matched the pattern(s): {', '.join(files)}"
        )
        sys.exit(2)

    # 4. Load baseline if specified
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

    # 4. Resolve provider and model from CLI or project configuration
    ctx = click.get_current_context(silent=True)
    is_cli_provider = (
        ctx.get_parameter_source("provider") == click.core.ParameterSource.COMMANDLINE
        if ctx
        else False
    )
    active_provider = (
        provider if (is_cli_provider or not preset_cfg.provider) else preset_cfg.provider
    )
    active_model = model or preset_cfg.model

    actual_api_key = api_key
    if active_provider.lower() == "openai":
        api_key_source = ctx.get_parameter_source("api_key") if ctx else None
        if api_key_source != click.core.ParameterSource.COMMANDLINE:
            actual_api_key = os.environ.get("OPENAI_API_KEY")

    effective_include_images = (
        include_images
        if include_images is not None
        else getattr(preset_cfg, "include_images", False)
    )
    effective_max_images = (
        max_images_per_doc
        if max_images_per_doc is not None
        else getattr(preset_cfg, "max_images_per_doc", 5)
    )

    if effective_include_images:
        err_console.print(
            "[yellow]Security advisory:[/yellow] Multimodal evaluation is enabled. "
            "Embedded images are NOT automatically redacted for credentials or PII. "
            "Ensure diagrams do not contain sensitive secrets or private information."
        )

    evaluator = TypeSafeEvaluator(
        api_key=actual_api_key,
        provider=active_provider,
        model=active_model,
        enable_cache=cache,
        cache_dir=cache_dir,
    )

    # 5. Evaluate documents (concurrent or sequential)
    def _eval_single(target_path: Path) -> tuple[Path, DocumentEvalResult | None, str | None]:
        try:
            res = evaluator.evaluate_document(
                filepath=str(target_path),
                preset=preset_cfg,
                mask_secrets=mask_secrets,
                max_chars=max_chars,
                dry_run=dry_run,
                offline=offline,
                include_images=effective_include_images,
                max_images_per_doc=effective_max_images,
            )
            return (target_path, res, None)
        except Exception as e:
            return (target_path, None, str(e))

    raw_eval_results: list[tuple[Path, DocumentEvalResult | None, str | None]] = []
    if concurrency == 1 or len(resolved_paths) == 1:
        for path in resolved_paths:
            raw_eval_results.append(_eval_single(path))
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(concurrency, len(resolved_paths))) as executor:
            raw_eval_results = list(executor.map(_eval_single, resolved_paths))

    results = []
    has_violations = False
    has_errors = False

    for path, res, err in raw_eval_results:
        if err is not None:
            click.echo(f"{path}: {err}", err=True)
            has_errors = True
            continue

        assert res is not None
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

    # 5. Output handling
    if results or output_format in ("json", "github"):
        if output_format == "table":
            render_table(results, preset_cfg)
        elif output_format == "json":
            json_output = render_json(results)
            click.echo(json_output)
        elif output_format == "markdown":
            md_output = render_markdown(results, preset_cfg)
            click.echo(md_output)
        elif output_format == "github":
            github_output = render_github_annotations(results)
            if github_output:
                click.echo(github_output)

    # 6. Save to out file if requested
    if out and (results or output_format in ("json", "github")):
        if output_format == "json":
            out.write_text(render_json(results), encoding="utf-8")
        elif output_format == "markdown":
            out.write_text(render_markdown(results, preset_cfg), encoding="utf-8")
        elif output_format == "github":
            out.write_text(render_github_annotations(results), encoding="utf-8")
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


@main.command(name="validate", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("labels_file", required=False, type=str)
@click.option(
    "--runs",
    type=int,
    default=None,
    help="Number of evaluation runs per document/pair (default: 3, or set in labels file).",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output presentation format. Default: table.",
)
@click.option(
    "-o",
    "--out",
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
    help="TypeSafe or OpenAI API key (falls back to TYPESAFE_API_KEY or OPENAI_API_KEY).",
)
@click.option(
    "--provider",
    type=click.Choice(["auto", "openai", "typesafe", "jev"], case_sensitive=False),
    default="auto",
    help="Decision provider backend (auto, openai, typesafe). Default: auto.",
)
@click.option(
    "--model",
    default=None,
    help="Model override (e.g. gpt-6-luna for OpenAI, jev-1.13.0 for TypeSafe).",
)
def validate_command(
    labels_file: str | None,
    runs: int | None,
    output_format: str,
    out: Path | None,
    ablate: Path | None,
    ablate_out_dir: Path | None,
    ablate_preset: str,
    ablate_labels_out: Path | None,
    dry_run: bool,
    api_key: str | None,
    provider: str = "auto",
    model: str | None = None,
    mask_secrets: bool = True,
) -> None:
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
                err_console.print(
                    f"[green]Labels configuration saved to:[/green] {target_labels_out}"
                )
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

    # Resolve provider and model from CLI or preset configuration
    ctx = click.get_current_context(silent=True)
    is_cli_provider = (
        ctx.get_parameter_source("provider") == click.core.ParameterSource.COMMANDLINE
        if ctx
        else False
    )
    active_provider: str = (
        provider
        if (is_cli_provider or not getattr(preset_cfg, "provider", None))
        else (preset_cfg.provider or provider)
    )
    active_model = model or getattr(preset_cfg, "model", None)

    actual_api_key = api_key
    if active_provider.lower() == "openai":
        api_key_source = ctx.get_parameter_source("api_key") if ctx else None
        if api_key_source != click.core.ParameterSource.COMMANDLINE:
            actual_api_key = os.environ.get("OPENAI_API_KEY")

    # Initialize evaluator
    evaluator = TypeSafeEvaluator(
        api_key=actual_api_key,
        provider=active_provider,
        model=active_model,
    )

    if not dry_run and not evaluator.api_key:
        if active_provider.lower() == "openai":
            click.echo(
                "No OpenAI API key provided. Set the OPENAI_API_KEY environment variable "
                "or pass --api-key.",
                err=True,
            )
        else:
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


PRE_COMMIT_SNIPPET = f"""  - repo: https://github.com/s-0-a-r/typesafe-eval
    rev: v{__version__}
    hooks:
      - id: typesafe-eval
        args: [--preset, safety]
"""

GITHUB_ACTION_WORKFLOW = f"""name: TypeSafe Evaluation Gate

on:
  pull_request:
    paths:
      - '**.md'
  push:
    branches:
      - main
    paths:
      - '**.md'

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run typesafe-eval safety gate
        uses: s-0-a-r/typesafe-eval@v{__version__}
        with:
          preset: safety
        env:
          TYPESAFE_API_KEY: ${{{{ secrets.TYPESAFE_API_KEY }}}}
"""

CLAUDE_HOOK_CONFIG = """{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "command": "python3 hooks/claude_safety_hook.py"
      }
    ]
  }
}
"""


@main.command(name="init", context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--pre-commit", "opt_pre_commit", is_flag=True, help="Configure .pre-commit-config.yaml hook."
)
@click.option(
    "--claude-code",
    "opt_claude_code",
    is_flag=True,
    help="Configure Claude Code safety hook (hooks/hooks.json).",
)
@click.option(
    "--github-action",
    "opt_github_action",
    is_flag=True,
    help="Generate .github/workflows/typesafe-eval.yml.",
)
@click.option("--all", "opt_all", is_flag=True, help="Set up all agent and CI integrations.")
def init(
    opt_pre_commit: bool,
    opt_claude_code: bool,
    opt_github_action: bool,
    opt_all: bool,
) -> None:
    """Scaffolds agent integrations and CI workflows in the current repository."""
    if opt_all or not (opt_pre_commit or opt_claude_code or opt_github_action):
        opt_pre_commit = True
        opt_claude_code = True
        if opt_all:
            opt_github_action = True

    configured = []

    # 1. Pre-commit
    if opt_pre_commit:
        pc_path = Path(".pre-commit-config.yaml")
        if pc_path.exists():
            content = pc_path.read_text(encoding="utf-8")
            if "typesafe-eval" not in content:
                if "repos:" in content:
                    content = content.replace("repos:\n", f"repos:\n{PRE_COMMIT_SNIPPET}")
                else:
                    content += f"\nrepos:\n{PRE_COMMIT_SNIPPET}"
                pc_path.write_text(content, encoding="utf-8")
                configured.append(".pre-commit-config.yaml (updated)")
            else:
                configured.append(".pre-commit-config.yaml (already configured)")
        else:
            pc_path.write_text(f"repos:\n{PRE_COMMIT_SNIPPET}", encoding="utf-8")
            configured.append(".pre-commit-config.yaml (created)")

    # 2. Claude Code Hook
    if opt_claude_code:
        hooks_dir = Path("hooks")
        hooks_dir.mkdir(exist_ok=True)
        hh_path = hooks_dir / "hooks.json"
        if not hh_path.exists():
            hh_path.write_text(CLAUDE_HOOK_CONFIG, encoding="utf-8")
            configured.append("hooks/hooks.json (created)")
        else:
            configured.append("hooks/hooks.json (already exists)")

    # 3. GitHub Action Workflow
    if opt_github_action:
        wf_dir = Path(".github/workflows")
        wf_dir.mkdir(parents=True, exist_ok=True)
        wf_path = wf_dir / "typesafe-eval.yml"
        if not wf_path.exists():
            wf_path.write_text(GITHUB_ACTION_WORKFLOW, encoding="utf-8")
            configured.append(".github/workflows/typesafe-eval.yml (created)")
        else:
            configured.append(".github/workflows/typesafe-eval.yml (already exists)")

    for item in configured:
        click.echo(f"✓ {item}")
    sys.exit(0)


@main.command(name="schema", context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-t",
    "--type",
    "schema_type",
    type=click.Choice(["preset", "labels"], case_sensitive=False),
    default="preset",
    help="Schema target type ('preset' for evaluation config YAML, 'labels' for validation labels YAML). Default: preset.",
)
@click.option(
    "-o",
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Save JSON schema output to specified file path.",
)
@click.option(
    "--indent",
    type=int,
    default=2,
    help="Indentation spaces for JSON formatting. Default: 2.",
)
def schema(schema_type: str, out: Path | None, indent: int) -> None:
    """Outputs JSON Schema for configuration and presets (enables IDE autocomplete)."""
    import json

    from typesafe_eval.models import PresetConfig
    from typesafe_eval.validator import ValidationLabelsConfig

    if schema_type.lower() == "labels":
        schema_dict = ValidationLabelsConfig.model_json_schema()
        schema_dict["title"] = "TypeSafeEvalValidationLabels"
        schema_dict["description"] = (
            "JSON Schema for typesafe-eval ground-truth labels specification (labels.yaml)."
        )
    else:
        schema_dict = PresetConfig.model_json_schema()
        schema_dict["title"] = "TypeSafeEvalPresetConfig"
        schema_dict["description"] = (
            "JSON Schema for typesafe-eval evaluation preset and configuration YAML files."
        )

    json_str = json.dumps(schema_dict, indent=indent)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_str + "\n", encoding="utf-8")
        click.echo(f"✓ JSON Schema saved to {out}")
    else:
        click.echo(json_str)


@main.group(name="cache")
def cache_group() -> None:
    """Manage local evaluation result cache."""
    pass


@cache_group.command(name="clear")
@click.option(
    "--cache-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Custom directory for caching evaluation results.",
)
def cache_clear_command(cache_dir: Path | None) -> None:
    """Clear all cached evaluation results."""
    from typesafe_eval.cache import EvaluationCache

    c = EvaluationCache(cache_dir=cache_dir)
    count = c.clear()
    click.echo(f"Cleared {count} cached evaluation result(s).")


if __name__ == "__main__":
    main()
