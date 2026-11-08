"""Commands for the local survey audit, analysis, and dashboard."""

import hashlib
import json
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Annotated

import typer
import yaml

from .config import AppConfig, load_config
from .ingestion import ingest
from .normalization import normalize
from .quality import build_quality_report

app = typer.Typer(help="Local EveryMind 988 survey tools.", pretty_exceptions_show_locals=False)


class RolePolicyOption(str, Enum):
    every = "every"
    multiple = "multiple"


@app.callback()
def main() -> None:
    """Audit and analyze EveryMind 988 training survey exports."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary_path = Path(file.name)
            file.write(content)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _write_json(path: Path, payload: dict) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    _write_atomic(path, content.encode("utf-8"))


def _config_hash(config: AppConfig) -> str:
    return hashlib.sha256(json.dumps(config.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def _validate_output(source: Path, output: Path) -> None:
    if output.suffix.lower() != ".json" or output.resolve() == source.resolve():
        raise typer.BadParameter("Choose a separate .json report file.", param_hint="--output")


@app.command()
def check(
    source: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(help="Where to save the private JSON audit.")] = Path("reports/quality.json"),
    config_dir: Annotated[
        Path | None, typer.Option(exists=True, file_okay=False, dir_okay=True, help="Optional YAML settings folder.")
    ] = None,
    role_policy: Annotated[RolePolicyOption | None, typer.Option(help="How to group people who selected multiple roles.")] = None,
    sheet: Annotated[str | None, typer.Option(help="Override the XLSX worksheet name.")] = None,
) -> None:
    """Read an XLSX or CSV export and save the Phase 1 quality report locally."""
    _validate_output(source, output)

    try:
        started = perf_counter()
        config = load_config(config_dir)
        if role_policy is not None:
            config.normalization.role_policy = role_policy.value
        ingested = ingest(source, config.registry, sheet=sheet)
        ingested_at = perf_counter()
        normalized = normalize(ingested.frame, config.normalization, config.registry)
        normalized_at = perf_counter()
        quality = build_quality_report(normalized, config.quality)
        audited_at = perf_counter()
        _write_json(
            output,
            {
                "quality_schema_version": "1.0.0",
                "visibility": "private_local_diagnostics",
                "config_hash": _config_hash(config),
                "ingestion": ingested.audit,
                **quality.report,
            },
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        typer.echo(f"Survey check failed. {error}", err=True)
        raise typer.Exit(1) from error

    row_count = ingested.audit["input_row_count"]
    column_count = ingested.audit["input_column_count"]
    typer.echo(f"Loaded {row_count:,} responses and {column_count:,} columns.")
    typer.echo(f"Usable response IDs {quality.report['n_usable']:,}. Flagged rows {quality.report['flags']['is_flagged']:,}.")
    schema_changes = (
        "new_columns", "missing_columns", "renamed_columns", "reordered_columns",
        "blank_columns", "duplicate_columns", "review_columns",
    )
    if any(ingested.audit[key] for key in schema_changes):
        typer.echo("Review the schema changes in the private quality report.")
    sensitivity = quality.report["presenter_sensitivity"]
    comparison = "unchanged" if sensitivity["objective_headlines_unchanged"] else "different"
    typer.echo(f"Presenter sensitivity check. Objective headline counts {comparison}.")
    typer.echo(f"Private quality report saved to {output}.")
    typer.echo(
        f"Stage timings in seconds. Load {ingested_at - started:.3f}, normalize {normalized_at - ingested_at:.3f}, "
        f"audit {audited_at - normalized_at:.3f}, save {perf_counter() - audited_at:.3f}.",
        err=True,
    )


@app.command("phase3")
def phase3(
    source: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(help="Where to save the Phase 3 aggregate analysis.")] = Path("reports/phase3.json"),
    config_dir: Annotated[
        Path | None, typer.Option(exists=True, file_okay=False, dir_okay=True, help="Optional YAML settings folder.")
    ] = None,
    role_policy: Annotated[RolePolicyOption | None, typer.Option(help="How to group people who selected multiple roles.")] = None,
    sheet: Annotated[str | None, typer.Option(help="Override the XLSX worksheet name.")] = None,
) -> None:
    """Analyze subgroups, item coverage, and delivery in an XLSX or CSV export."""
    from .delivery import analyze_delivery
    from .schemas import SuppressionPolicy
    from .subgroups import analyze_subgroups
    from .survey_versions import analyze_survey_versions

    _validate_output(source, output)
    try:
        started = perf_counter()
        config = load_config(config_dir)
        if role_policy is not None:
            config.normalization.role_policy = role_policy.value
        ingested = ingest(source, config.registry, sheet=sheet)
        normalized = normalize(ingested.frame, config.normalization, config.registry)
        quality = build_quality_report(normalized, config.quality)
        prepared_at = perf_counter()

        settings = config.phase3
        shared = {
            "input_hash": ingested.audit["input_hash"],
            "config_hash": _config_hash(config),
            "minimum_n": settings.minimum_n,
        }
        subgroup_metrics = analyze_subgroups(
            quality.frame, normalized.objective_columns, config.normalization,
            minimum_clusters=settings.minimum_clusters, **shared,
        )
        subgroups_at = perf_counter()
        versions = analyze_survey_versions(
            quality.frame, known_roles=set(config.normalization.role_aliases.values()),
            seed=settings.seed, shuffles=settings.shuffles, dominance_threshold=settings.dominance_threshold, **shared,
        )
        versions_at = perf_counter()
        delivery_metrics = analyze_delivery(
            quality.frame, normalized.objective_columns,
            seed=settings.seed, bootstrap_resamples=settings.bootstrap_resamples, **shared,
        )
        delivery_at = perf_counter()
        ledger = subgroup_metrics + versions.metrics + delivery_metrics
        _write_json(output, {
            "analysis_schema_version": "1.0.0",
            "input_hash": shared["input_hash"],
            "missing_question_ids": ingested.audit["missing_columns"],
            "suppression_policy": SuppressionPolicy(minimum_n=settings.minimum_n).model_dump(mode="json"),
            "metrics": [metric.model_dump(mode="json") for metric in ledger],
        })
    except (OSError, ValueError, yaml.YAMLError) as error:
        typer.echo(f"Phase 3 analysis failed. {error}", err=True)
        raise typer.Exit(1) from error

    typer.echo(f"Phase 3 analysis saved to {output}.")
    typer.echo(f"Aggregate metrics {len(ledger):,}. Suppressed entries {sum(metric.suppressed for metric in ledger):,}.")
    if ingested.audit["missing_columns"] or ingested.audit["review_columns"]:
        typer.echo("Some questions need review. Run the check command to see the schema details.")
    typer.echo(
        f"Stage timings in seconds. Prepare {prepared_at - started:.3f}, subgroups {subgroups_at - prepared_at:.3f}, "
        f"versions {versions_at - subgroups_at:.3f}, delivery {delivery_at - versions_at:.3f}, "
        f"save {perf_counter() - delivery_at:.3f}.",
        err=True,
    )


@app.command()
def report(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(help="Validated aggregate report for the dashboard.")] = Path("reports/report.json"),
    audit_output: Annotated[Path, typer.Option(help="Separate PRIVATE schema and quality diagnostics.")] = Path("reports/private-quality.json"),
    sheet: Annotated[str | None, typer.Option(help="Override the XLSX worksheet name.")] = None,
    config_dir: Annotated[Path | None, typer.Option(exists=True, file_okay=False)] = None,
    role_policy: Annotated[RolePolicyOption | None, typer.Option()] = None,
    synthetic: Annotated[bool, typer.Option(help="Label a generated/test survey as synthetic.")] = False,
    filters: Annotated[Path | None, typer.Option(exists=True, dir_okay=False, help="Version 1.0.0 FilterSpec JSON; no exclusions by default.")] = None,
    csv_output: Annotated[Path | None, typer.Option(help="Optional aggregate-only CSV export.")] = None,
    parquet_output: Annotated[Path | None, typer.Option(help="Optional aggregate-only Parquet export.")] = None,
) -> None:
    """Analyze an export and build the complete, privacy-checked dashboard report."""
    from .reporting import build_report

    _validate_output(source, output)
    _validate_output(source, audit_output)
    if output.resolve() == audit_output.resolve():
        raise typer.BadParameter("Keep the aggregate report and private audit in separate files.")
    destinations = [p.resolve() for p in (output,audit_output,csv_output,parquet_output) if p is not None]
    protected = {source.resolve()} | ({filters.resolve()} if filters else set())
    if len(destinations) != len(set(destinations)) or protected.intersection(destinations):
        raise typer.BadParameter("Use distinct output files, separate from the survey and filter specification.")
    filter_spec = None
    if filters is not None:
        from pydantic import ValidationError
        from .filters import FilterSpec
        try:
            filter_spec = FilterSpec.model_validate_json(filters.read_bytes())
        except ValidationError as error:
            messages = '; '.join(item['msg'] for item in error.errors(include_input=False))
            raise typer.BadParameter(f"Invalid filter specification: {messages}", param_hint="--filters") from None
        except OSError:
            raise typer.BadParameter("The filter specification could not be read.", param_hint="--filters") from None
    try:
        if filters is not None:
            from .filter_service import FilterService
            current = FilterService(source, sheet=sheet, config_dir=config_dir, role_policy=role_policy.value if role_policy else None)
            bundle = current.open_report(filter_spec)
            if synthetic: bundle.data_kind = 'synthetic'
            audit = {"visibility":"private_local_diagnostics", "ingestion":current.prepared.incoming.audit,
                     **current.prepared.quality.report, "filter_spec":filter_spec.canonical()}
        else:
            bundle, audit = build_report(source, sheet=sheet, config_dir=config_dir,
                                        role_policy=role_policy.value if role_policy else None, synthetic=synthetic)
        _write_json(audit_output, audit)
        _write_json(output, bundle.model_dump(mode="json"))
        if csv_output or parquet_output:
            from .filter_service import export_report
            for destination, format in ((csv_output,'csv'),(parquet_output,'parquet')):
                if destination: _write_atomic(destination,export_report(bundle,format))
    except (OSError, ValueError, yaml.YAMLError):
        typer.echo("Report could not be completed. Check the worksheet, ID and paired-question headers, file format and output permissions. Use check for private diagnostics. No demo was substituted; check timestamps before using older outputs.", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Validated {bundle.data_kind} report saved to {output}.")
    typer.echo(f"PRIVATE audit saved to {audit_output}. Keep it private. Review topics, recommendations and disclosure risks before sharing the aggregate.")


@app.command()
def serve(
    input: Annotated[Path | None, typer.Option(exists=True, dir_okay=False, help="Optional XLSX/CSV survey; otherwise choose one in the page.")] = None,
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8001,
):
    """Open the data-options dashboard on this computer only. Uploads stay in memory."""
    import uvicorn
    from .server import create_app
    try:
        application = create_app(input)
    except (OSError,ValueError):
        typer.echo("Survey could not be prepared. Check the worksheet, IDs and paired questions; at least 10 usable responses are required.",err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Open http://127.0.0.1:{port}/ — survey data and filter caches stay in memory. Press Ctrl+C to stop.")
    uvicorn.run(application,host='127.0.0.1',port=port,access_log=False)


@app.command("validate-report")
def validate_report(source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]):
    """Check the report contract, public surface and release rules."""
    from .release import validate_release
    from .schemas import ReportBundle
    try:
        bundle = ReportBundle.model_validate_json(source.read_bytes())
        validate_release(bundle)
    except (OSError, ValueError):
        typer.echo("Not a valid releasable report. Do not substitute private phase3 or quality JSON.", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Validated {bundle.data_kind} report. Validation is not approval to publish.")


@app.command()
def pages(
    report: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path("fixtures/report.sample.json"),
    out: Annotated[Path, typer.Option(help="New or empty website-only output directory.")] = Path("dist/pages"),
) -> None:
    """Prepare a local GitHub Pages package. Does not publish anything."""
    from .pages import prepare_pages
    try:
        prepare_pages(report, out)
    except (OSError, ValueError):
        typer.echo("Could not prepare Pages files. Select a valid release report and a new or empty output folder.", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Website package ready at {out}. Nothing was published. Review report disclosure and anonymous judging requirements before deployment.")


@app.command()
def dashboard(
    report: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, readable=True, help="Public report bundle to copy.")
    ] = Path("fixtures/report.sample.json"),
    out: Annotated[
        Path, typer.Option(file_okay=False, help="Dashboard directory that will receive report.json.")
    ] = Path("dashboard"),
) -> None:
    """Validate and place a public report bundle beside the static dashboard."""
    from pydantic import ValidationError

    from .schemas import ReportBundle

    destination = out / "report.json"
    try:
        content = report.read_bytes()
        ReportBundle.model_validate_json(content)
        if report.resolve() != destination.resolve():
            _write_atomic(destination, content)
    except ValidationError:
        typer.echo("Choose a valid public report bundle with schema version 1.0.0.", err=True)
        raise typer.Exit(1) from None
    except OSError as error:
        typer.echo(f"Dashboard report could not be prepared. {error}", err=True)
        raise typer.Exit(1) from error

    typer.echo(f"Dashboard report ready at {destination}.")
