"""Core tracker logic — high-level API for experiment tracking."""

import hashlib
import json
import shutil
from pathlib import Path

from . import db


def init(project_dir: Path | None = None) -> Path:
    """Initialize exp-tracker in a project directory."""
    project_dir = project_dir or Path.cwd()
    db_path = db.init_db(project_dir)
    return db_path


def log_experiment(
    name: str,
    params: dict | str | None = None,
    cv_score: float | None = None,
    notes: str = "",
    tags: list[str] | str | None = None,
    parent_id: str | None = None,
    project_dir: Path | None = None,
) -> dict:
    """Log a new experiment."""
    project_dir = _resolve_project_dir(project_dir)

    # Parse params if string
    if isinstance(params, str):
        if params.strip():
            # Support "key=val,key2=val2" format
            if "=" in params and not params.strip().startswith("{"):
                parsed = {}
                for pair in params.split(","):
                    pair = pair.strip()
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        parsed[k.strip()] = _try_parse(v.strip())
                    else:
                        parsed[pair] = True
                params = parsed
            else:
                params = json.loads(params)
        else:
            params = {}

    # Parse tags if string
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return db.insert_experiment(
        project_dir=project_dir,
        name=name,
        params=params,
        cv_score=cv_score,
        notes=notes,
        tags=tags,
        parent_id=parent_id,
    )


def log_submission(
    filepath: str | Path,
    experiment_id: str | None = None,
    note: str = "",
    project_dir: Path | None = None,
) -> dict:
    """Log a submission with auto-versioning and file copy."""
    project_dir = _resolve_project_dir(project_dir)
    filepath = Path(filepath).resolve()

    if not filepath.exists():
        raise FileNotFoundError(f"Submission file not found: {filepath}")

    # Compute checksum
    checksum = _md5(filepath)

    # If no experiment_id, create one from the submission
    if not experiment_id:
        exp = db.insert_experiment(
            project_dir=project_dir,
            name=filepath.stem,
            exp_type="submission",
            notes=note,
        )
        experiment_id = exp["id"]
    else:
        # Verify experiment exists
        existing = db.get_experiment(project_dir, experiment_id)
        if not existing:
            raise ValueError(f"Experiment not found: {experiment_id}")

    # Insert submission record
    result = db.insert_submission(
        project_dir=project_dir,
        experiment_id=experiment_id,
        filepath=filepath,
        checksum=checksum,
    )

    # Copy file to submissions directory
    dest_dir = project_dir / db.DB_DIR / db.SUBMISSIONS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / result["_dest_filename"]
    shutil.copy2(str(filepath), str(dest_path))

    return result


def update_score(
    experiment_id: str,
    public_lb: float | None = None,
    private_lb: float | None = None,
    project_dir: Path | None = None,
) -> dict | None:
    """Update leaderboard scores for an experiment."""
    project_dir = _resolve_project_dir(project_dir)
    return db.update_scores(project_dir, experiment_id, public_lb, private_lb)


def list_experiments(
    tags: list[str] | None = None,
    name_contains: str | None = None,
    limit: int | None = None,
    project_dir: Path | None = None,
) -> list[dict]:
    """List experiments with optional filters."""
    project_dir = _resolve_project_dir(project_dir)
    return db.query_experiments(
        project_dir, tags=tags, name_contains=name_contains, limit=limit
    )


def compare_experiments(
    top_n: int = 10,
    metric: str = "cv_score",
    project_dir: Path | None = None,
) -> list[dict]:
    """Compare and rank experiments by metric."""
    project_dir = _resolve_project_dir(project_dir)

    # Higher is better for cv_score, lower could be better for LB depending on competition
    ascending = metric == "public_lb" or metric == "private_lb"

    return db.query_experiments(
        project_dir,
        order_by=metric,
        ascending=ascending,
        limit=top_n,
    )


def get_lineage(
    experiment_id: str,
    project_dir: Path | None = None,
) -> list[dict]:
    """Get parent/child chain for an experiment."""
    project_dir = _resolve_project_dir(project_dir)
    return db.get_lineage(project_dir, experiment_id)


def _resolve_project_dir(project_dir: Path | None) -> Path:
    if project_dir:
        return project_dir
    found = db.find_project_dir()
    if not found:
        raise RuntimeError(
            "Not in an exp-tracker project. Run 'exp-tracker init' first."
        )
    return found


def _md5(filepath: Path) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _try_parse(value: str):
    """Try to parse a string as int, float, bool, or keep as string."""
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
