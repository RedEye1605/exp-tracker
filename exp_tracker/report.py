"""Report generation — markdown and JSON output."""

import json
from datetime import datetime


def generate_markdown(experiments: list[dict], title: str = "Experiment Report") -> str:
    """Generate a markdown table report of experiments."""
    if not experiments:
        return f"# {title}\n\nNo experiments found.\n"

    lines = [f"# {title}", ""]

    # Header
    headers = ["ID", "Name", "Type", "CV Score", "Public LB", "Private LB", "Tags", "Created"]
    rows = []

    for exp in experiments:
        tags = json.loads(exp.get("tags", "[]")) if isinstance(exp.get("tags"), str) else exp.get("tags", [])
        tags_str = ", ".join(tags) if tags else "-"
        exp_id = exp["id"][:8]

        created = exp.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                created = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass

        rows.append([
            exp_id,
            exp.get("name", "-"),
            exp.get("type", "experiment"),
            _fmt_score(exp.get("cv_score")),
            _fmt_score(exp.get("public_lb")),
            _fmt_score(exp.get("private_lb")),
            tags_str,
            created,
        ])

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Format table
    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"

    lines.append(header_line)
    lines.append(sep_line)
    for row in rows:
        line = "| " + " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"
        lines.append(line)

    lines.append("")
    lines.append(f"_Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")

    return "\n".join(lines)


def generate_comparison_table(experiments: list[dict], metric: str = "cv_score") -> str:
    """Generate a side-by-side comparison ranked by metric."""
    if not experiments:
        return "No experiments to compare.\n"

    valid = [e for e in experiments if e.get(metric) is not None]
    if not valid:
        return f"No experiments with {metric} recorded.\n"

    # Sort
    reverse = metric == "cv_score"
    valid.sort(key=lambda e: e.get(metric, 0), reverse=reverse)

    lines = [f"## Comparison by {metric}", ""]

    best = valid[0].get(metric)
    worst = valid[-1].get(metric)

    for rank, exp in enumerate(valid, 1):
        score = exp.get(metric)
        tags = json.loads(exp.get("tags", "[]")) if isinstance(exp.get("tags"), str) else exp.get("tags", [])
        params = json.loads(exp.get("params", "{}")) if isinstance(exp.get("params"), str) else exp.get("params", {})

        marker = ""
        if score == best:
            marker = " 🏆"
        elif score == worst and len(valid) > 1:
            marker = " ⚠️"

        lines.append(f"### #{rank} {exp.get('name', 'unnamed')}{marker}")
        lines.append(f"- **{metric}**: `{score}`")
        if tags:
            lines.append(f"- **Tags**: {', '.join(f'`{t}`' for t in tags)}")
        if params:
            param_strs = [f"`{k}={v}`" for k, v in params.items()]
            lines.append(f"- **Params**: {', '.join(param_strs)}")
        notes = exp.get("notes", "")
        if notes:
            lines.append(f"- **Notes**: {notes}")
        lines.append("")

    return "\n".join(lines)


def generate_json(experiments: list[dict]) -> str:
    """Generate JSON output of experiments."""
    # Ensure all values are serializable
    clean = []
    for exp in experiments:
        d = dict(exp)
        for key in ("params", "tags"):
            if isinstance(d.get(key), str):
                try:
                    d[key] = json.loads(d[key])
                except json.JSONDecodeError:
                    pass
        clean.append(d)
    return json.dumps(clean, indent=2, default=str)


def _fmt_score(value) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.6f}"
    except (ValueError, TypeError):
        return str(value)
