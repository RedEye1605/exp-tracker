"""CLI interface for exp-tracker using Click + Rich."""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from . import report, tracker

console = Console()

_json_output = False
_quiet_mode = False


def _out(msg=""):
    if not _quiet_mode:
        console.print(msg)


def _json_out(data):
    if _json_output:
        print(json.dumps(data, indent=2, default=str))
        return True
    return False


def _find_project():
    from . import db
    found = db.find_project_dir()
    if not found:
        console.print("[red]Error:[/red] Not in an exp-tracker project. Run [bold]exp-tracker init[/bold] first.")
        raise SystemExit(1)
    return found


@click.group()
@click.version_option(version="0.2.0", prog_name="exp-tracker")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
def main(json_flag, quiet):
    """🧪 Exp Tracker — Lightweight ML experiment tracking for competitions."""
    global _json_output, _quiet_mode
    _json_output = json_flag
    _quiet_mode = quiet


@main.command()
def init():
    """Initialize exp-tracker in the current directory."""
    project_dir = Path.cwd()
    db_path = tracker.init(project_dir)
    if _json_output:
        _json_out({"status": "initialized", "path": str(db_path)})
    else:
        console.print(Panel(
            f"[green]✓[/green] Initialized exp-tracker in [cyan]{project_dir}/.exp-tracker/[/cyan]\n"
            f"Database: [dim]{db_path}[/dim]",
            title="🧪 Exp Tracker",
            border_style="green",
        ))


@main.command("log")
@click.option("--name", "-n", required=True, help="Experiment name")
@click.option("--params", "-p", default=None, help="Parameters as JSON or key=val,key2=val2")
@click.option("--cv-score", "-s", type=float, default=None, help="Cross-validation score")
@click.option("--notes", default="", help="Notes about this experiment")
@click.option("--tags", "-t", default=None, help="Comma-separated tags")
@click.option("--parent", default=None, help="Parent experiment ID (for iterations)")
def log_experiment(name, params, cv_score, notes, tags, parent):
    """Log a new experiment."""
    project_dir = _find_project()
    tags_list = [t.strip() for t in tags.split(",")] if tags else None

    result = tracker.log_experiment(
        name=name, params=params, cv_score=cv_score, notes=notes,
        tags=tags_list, parent_id=parent, project_dir=project_dir,
    )

    if _json_output:
        _json_out(result)
    else:
        _print_experiment_card(result, "Experiment Logged")


@main.command("submit")
@click.option("--file", "-f", "filepath", required=True, help="Path to submission file")
@click.option("--experiment", "-e", default=None, help="Experiment ID to link")
@click.option("--note", default="", help="Note about this submission")
def submit(filepath, experiment, note):
    """Log a submission with auto-versioning."""
    project_dir = _find_project()
    result = tracker.log_submission(filepath=filepath, experiment_id=experiment, note=note, project_dir=project_dir)

    if _json_output:
        _json_out(result)
    else:
        console.print(Panel(
            f"[green]✓[/green] Submission logged\n"
            f"  Version: [bold]{result['version']}[/bold]\n"
            f"  File: [cyan]{result['filename']}[/cyan]\n"
            f"  Checksum: [dim]{result['checksum']}[/dim]\n"
            f"  Experiment: [dim]{result['experiment_id'][:8]}...[/dim]",
            title="📤 Submission", border_style="blue",
        ))


@main.command("score")
@click.argument("experiment_id")
@click.option("--public", type=float, default=None, help="Public leaderboard score")
@click.option("--private", type=float, default=None, help="Private leaderboard score")
def update_score(experiment_id, public, private):
    """Update leaderboard scores for an experiment."""
    if public is None and private is None:
        console.print("[red]Error:[/red] Provide at least --public or --private")
        raise SystemExit(1)

    project_dir = _find_project()
    result = tracker.update_score(experiment_id=experiment_id, public_lb=public, private_lb=private, project_dir=project_dir)

    if not result:
        console.print(f"[red]Error:[/red] Experiment [dim]{experiment_id}[/dim] not found")
        raise SystemExit(1)

    if _json_output:
        _json_out(result)
    else:
        _print_experiment_card(result, "Scores Updated")


@main.command("list")
@click.option("--tags", "-t", default=None, help="Filter by comma-separated tags")
@click.option("--name", "name_contains", default=None, help="Filter by name (substring)")
@click.option("--top", "-n", type=int, default=None, help="Limit to top N")
def list_experiments(tags, name_contains, top):
    """List experiments."""
    project_dir = _find_project()
    tags_list = [t.strip() for t in tags.split(",")] if tags else None
    experiments = tracker.list_experiments(tags=tags_list, name_contains=name_contains, limit=top, project_dir=project_dir)

    if _json_output:
        _json_out(experiments)
        return
    if not experiments:
        _out("[dim]No experiments found.[/dim]")
        return
    _print_experiments_table(experiments)


@main.command("compare")
@click.option("--top", "-n", type=int, default=10, help="Top N experiments")
@click.option("--metric", "-m", type=click.Choice(["cv_score", "public_lb"]), default="cv_score", help="Metric to rank by")
@click.option("--markdown", is_flag=True, help="Output as markdown table (vault-friendly)")
def compare_experiments(top, metric, markdown):
    """Compare and rank experiments by metric."""
    project_dir = _find_project()
    experiments = tracker.compare_experiments(top_n=top, metric=metric, project_dir=project_dir)

    if not experiments:
        _out(f"[dim]No experiments with {metric} recorded.[/dim]")
        return

    if _json_output:
        _json_out(experiments)
        return

    if markdown:
        content = report.generate_comparison_table(experiments, metric)
        print(content)
        return

    # Rich table output
    scores = [e[metric] for e in experiments if e.get(metric) is not None]
    best = max(scores) if scores else None
    worst = min(scores) if scores else None

    table = Table(title=f"🏆 Comparison by {metric}", show_lines=True)
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column(metric, justify="right")
    table.add_column("Other LB", justify="right")
    table.add_column("Tags")
    table.add_column("Notes", max_width=30)

    other_metric = "private_lb" if metric == "public_lb" else "public_lb"

    for rank, exp in enumerate(experiments, 1):
        score = exp.get(metric)
        other_score = exp.get(other_metric)
        score_str = _fmt_score(score)
        if score == best and best != worst:
            score_str = f"[bold green]{score_str}[/bold green]"
        elif score == worst and best != worst:
            score_str = f"[red]{score_str}[/red]"

        tags = json.loads(exp.get("tags", "[]")) if isinstance(exp.get("tags"), str) else exp.get("tags", [])
        tags_str = " ".join(f"[dim]#[/dim]{t}" for t in tags) if tags else "-"

        rank_str = str(rank)
        if rank == 1: rank_str = "🥇"
        elif rank == 2: rank_str = "🥈"
        elif rank == 3: rank_str = "🥉"

        table.add_row(
            rank_str, exp["id"][:8], exp.get("name", "-"),
            score_str, _fmt_score(other_score), tags_str,
            (exp.get("notes", "") or "-")[:30],
        )

    _out(table)


@main.command("top")
@click.option("--metric", "-m", type=click.Choice(["cv_score", "public_lb"]), default="cv_score")
@click.option("--limit", "-n", type=int, default=5)
def top_experiment(metric, limit):
    """Quick: what's my best model?"""
    project_dir = _find_project()
    experiments = tracker.compare_experiments(top_n=limit, metric=metric, project_dir=project_dir)

    if not experiments:
        _out(f"[dim]No experiments with {metric} recorded.[/dim]")
        return

    if _json_output:
        _json_out(experiments)
        return

    best = experiments[0]
    _out(f"[bold green]🏆 Best by {metric}:[/bold green] {best.get('name', '?')} = {best.get(metric)}")
    for i, e in enumerate(experiments[:3], 1):
        _out(f"  {i}. {e.get('name', '?')} ({metric}={e.get(metric, '-')})")


@main.command("export")
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--output", "-o", default=None, help="Output file path (default: vault experiments.md)")
def export_cmd(fmt, output):
    """Export experiments to the vault or a file."""
    project_dir = _find_project()
    experiments = tracker.list_experiments(project_dir=project_dir)

    if not experiments:
        _out("[dim]No experiments to export.[/dim]")
        return

    if fmt == "markdown":
        content = report.generate_markdown(experiments)
    else:
        content = report.generate_json(experiments)

    if output:
        out_path = Path(output)
    else:
        vault = Path.home() / "Obsidian/RhendyVault"
        out_path = vault / "03_active" / "experiments-export.md" if fmt == "markdown" else vault / "03_active" / "experiments-export.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content)
    if _json_output:
        _json_out({"exported": len(experiments), "path": str(out_path)})
    else:
        _out(f"[green]✓[/green] Exported {len(experiments)} experiments to [cyan]{out_path}[/cyan]")


@main.command("history")
@click.argument("experiment_id", required=False)
def show_history(experiment_id):
    """Show experiment timeline or single experiment detail."""
    project_dir = _find_project()

    if experiment_id:
        from . import db as db_mod
        exp = db_mod.get_experiment(project_dir, experiment_id)
        if not exp:
            console.print(f"[red]Error:[/red] Experiment [dim]{experiment_id}[/dim] not found")
            raise SystemExit(1)

        if _json_output:
            _json_out(exp)
            return

        _print_experiment_card(exp, "Experiment Detail")

        submissions = db_mod.get_submissions(project_dir, experiment_id)
        if submissions:
            console.print("\n[bold]Submissions:[/bold]")
            sub_table = Table()
            sub_table.add_column("Version", justify="right")
            sub_table.add_column("File")
            sub_table.add_column("Checksum", style="dim")
            sub_table.add_column("Created")
            for sub in submissions:
                sub_table.add_row(
                    str(sub["version"]), sub["filename"],
                    sub["checksum"][:12] + "...", _fmt_datetime(sub.get("created_at", "")),
                )
            console.print(sub_table)

        lineage = db_mod.get_lineage(project_dir, experiment_id)
        if len(lineage) > 1:
            console.print("\n[bold]Lineage:[/bold]")
            for i, l_exp in enumerate(lineage):
                prefix = "  " * i + ("→ " if i > 0 else "")
                marker = " [bold green]*[/bold green]" if l_exp["id"] == experiment_id else ""
                console.print(f"{prefix}[cyan]{l_exp.get('name', '?')}[/cyan] ({l_exp['id'][:8]}){marker}")
    else:
        experiments = tracker.list_experiments(project_dir=project_dir)
        if not experiments:
            _out("[dim]No experiments found.[/dim]")
            return
        if _json_output:
            _json_out(experiments)
            return
        _print_experiments_table(experiments)


@main.command("report")
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
def generate_report(fmt, output):
    """Generate a report of all experiments."""
    project_dir = _find_project()
    experiments = tracker.list_experiments(project_dir=project_dir)

    if fmt == "markdown":
        content = report.generate_markdown(experiments)
    else:
        content = report.generate_json(experiments)

    if output:
        Path(output).write_text(content)
        _out(f"[green]✓[/green] Report written to [cyan]{output}[/cyan]")
    else:
        print(content)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _print_experiment_card(exp: dict, title: str):
    tags = json.loads(exp.get("tags", "[]")) if isinstance(exp.get("tags"), str) else exp.get("tags", [])
    params = json.loads(exp.get("params", "{}")) if isinstance(exp.get("params"), str) else exp.get("params", {})
    lines = [
        f"[bold]ID:[/bold] {exp['id']}",
        f"[bold]Name:[/bold] [cyan]{exp.get('name', '-')}[/cyan]",
        f"[bold]Type:[/bold] {exp.get('type', 'experiment')}",
        f"[bold]CV Score:[/bold] {_fmt_score(exp.get('cv_score'))}",
        f"[bold]Public LB:[/bold] {_fmt_score(exp.get('public_lb'))}",
        f"[bold]Private LB:[/bold] {_fmt_score(exp.get('private_lb'))}",
    ]
    if tags:
        lines.append(f"[bold]Tags:[/bold] {', '.join(f'`{t}`' for t in tags)}")
    if params:
        param_strs = [f"`{k}={v}`" for k, v in params.items()]
        lines.append(f"[bold]Params:[/bold] {', '.join(param_strs)}")
    if exp.get("notes"):
        lines.append(f"[bold]Notes:[/bold] {exp['notes']}")
    if exp.get("parent_id"):
        lines.append(f"[bold]Parent:[/bold] {exp['parent_id'][:8]}...")
    console.print(Panel("\n".join(lines), title=f"🧪 {title}", border_style="blue"))


def _print_experiments_table(experiments: list[dict]):
    table = Table(title="🧪 Experiments", show_lines=True)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("CV Score", justify="right")
    table.add_column("Public LB", justify="right")
    table.add_column("Private LB", justify="right")
    table.add_column("Tags")
    table.add_column("Created")

    for exp in experiments:
        tags = json.loads(exp.get("tags", "[]")) if isinstance(exp.get("tags"), str) else exp.get("tags", [])
        tags_str = " ".join(f"[dim]#[/dim]{t}" for t in tags) if tags else "-"
        table.add_row(
            exp["id"][:8], exp.get("name", "-"), exp.get("type", "experiment"),
            _fmt_score(exp.get("cv_score")), _fmt_score(exp.get("public_lb")),
            _fmt_score(exp.get("private_lb")), tags_str,
            _fmt_datetime(exp.get("created_at", "")),
        )
    console.print(table)


def _fmt_score(value) -> str:
    if value is None:
        return "[dim]-[/dim]"
    try:
        return f"{float(value):.6f}"
    except (ValueError, TypeError):
        return str(value)


def _fmt_datetime(iso_str: str) -> str:
    if not iso_str:
        return "-"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_str[:16]


if __name__ == "__main__":
    main()
