"""SQLite database layer for exp-tracker."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = ".exp-tracker"
DB_NAME = "experiments.db"
SUBMISSIONS_DIR = "submissions"

_CREATE_EXPERIMENTS = """
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'experiment',
    params TEXT DEFAULT '{}',
    cv_score REAL,
    public_lb REAL,
    private_lb REAL,
    submission_file TEXT,
    notes TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    parent_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES experiments(id)
)
"""

_CREATE_SUBMISSIONS = """
CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    checksum TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    UNIQUE(experiment_id, version)
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_experiments_name ON experiments(name)",
    "CREATE INDEX IF NOT EXISTS idx_experiments_cv_score ON experiments(cv_score)",
    "CREATE INDEX IF NOT EXISTS idx_experiments_public_lb ON experiments(public_lb)",
    "CREATE INDEX IF NOT EXISTS idx_experiments_parent_id ON experiments(parent_id)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_experiment_id ON submissions(experiment_id)",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def get_db_path(project_dir: Path) -> Path:
    return project_dir / DB_DIR / DB_NAME


def get_connection(project_dir: Path) -> sqlite3.Connection:
    db_path = get_db_path(project_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(project_dir: Path) -> Path:
    """Initialize the database and directories. Returns db_path."""
    db_dir = project_dir / DB_DIR
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / SUBMISSIONS_DIR).mkdir(parents=True, exist_ok=True)

    conn = get_connection(project_dir)
    try:
        conn.execute(_CREATE_EXPERIMENTS)
        conn.execute(_CREATE_SUBMISSIONS)
        for idx_sql in _CREATE_INDEXES:
            conn.execute(idx_sql)
        conn.commit()
    finally:
        conn.close()

    return get_db_path(project_dir)


def insert_experiment(
    project_dir: Path,
    name: str,
    exp_type: str = "experiment",
    params: dict | None = None,
    cv_score: float | None = None,
    notes: str = "",
    tags: list[str] | None = None,
    parent_id: str | None = None,
) -> dict:
    """Insert a new experiment and return its row as a dict."""
    exp_id = _uuid()
    now = _now_iso()

    conn = get_connection(project_dir)
    try:
        conn.execute(
            """INSERT INTO experiments (id, name, type, params, cv_score, notes, tags, parent_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                exp_id,
                name,
                exp_type,
                json.dumps(params or {}),
                cv_score,
                notes,
                json.dumps(tags or []),
                parent_id,
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def insert_submission(
    project_dir: Path,
    experiment_id: str,
    filepath: Path,
    checksum: str,
) -> dict:
    """Insert a submission record with auto-versioning."""
    sub_id = _uuid()
    now = _now_iso()
    filename = filepath.name

    conn = get_connection(project_dir)
    try:
        # Get next version number
        row = conn.execute(
            "SELECT MAX(version) as max_ver FROM submissions WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
        next_version = (row["max_ver"] or 0) + 1

        # Store relative path inside submissions dir
        dest_filename = f"{experiment_id[:8]}_v{next_version}_{filename}"
        dest_relpath = f"{SUBMISSIONS_DIR}/{dest_filename}"

        conn.execute(
            """INSERT INTO submissions (id, experiment_id, version, filename, filepath, checksum, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sub_id, experiment_id, next_version, filename, dest_relpath, checksum, now),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
        result = dict(row)
        result["_dest_filename"] = dest_filename
        result["_dest_relpath"] = dest_relpath
        return result
    finally:
        conn.close()


def update_scores(
    project_dir: Path,
    experiment_id: str,
    public_lb: float | None = None,
    private_lb: float | None = None,
) -> dict | None:
    """Update leaderboard scores for an experiment."""
    conn = get_connection(project_dir)
    try:
        sets = []
        vals = []
        if public_lb is not None:
            sets.append("public_lb = ?")
            vals.append(public_lb)
        if private_lb is not None:
            sets.append("private_lb = ?")
            vals.append(private_lb)

        if not sets:
            return None

        vals.append(experiment_id)
        conn.execute(f"UPDATE experiments SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def query_experiments(
    project_dir: Path,
    tags: list[str] | None = None,
    name_contains: str | None = None,
    limit: int | None = None,
    order_by: str = "created_at",
    ascending: bool = False,
) -> list[dict]:
    """Query experiments with optional filters."""
    conn = get_connection(project_dir)
    try:
        query = "SELECT * FROM experiments"
        conditions = []
        params = []

        if name_contains:
            conditions.append("name LIKE ?")
            params.append(f"%{name_contains}%")

        if tags:
            for tag in tags:
                conditions.append("tags LIKE ?")
                params.append(f'%"{tag}"%')

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        direction = "ASC" if ascending else "DESC"
        query += f" ORDER BY {order_by} {direction}"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_experiment(project_dir: Path, experiment_id: str) -> dict | None:
    """Get a single experiment by ID."""
    conn = get_connection(project_dir)
    try:
        row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_submissions(project_dir: Path, experiment_id: str) -> list[dict]:
    """Get all submissions for an experiment."""
    conn = get_connection(project_dir)
    try:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE experiment_id = ? ORDER BY version ASC",
            (experiment_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_lineage(project_dir: Path, experiment_id: str) -> list[dict]:
    """Get the full parent→child chain for an experiment."""
    conn = get_connection(project_dir)
    try:
        # Walk up to root
        chain = []
        current_id = experiment_id
        visited = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            row = conn.execute("SELECT * FROM experiments WHERE id = ?", (current_id,)).fetchone()
            if not row:
                break
            chain.append(dict(row))
            current_id = row["parent_id"]

        # Reverse so root is first
        chain.reverse()

        # Now walk down: find children of the target
        children = conn.execute(
            "SELECT * FROM experiments WHERE parent_id = ? ORDER BY created_at",
            (experiment_id,),
        ).fetchall()
        for child in children:
            child_dict = dict(child)
            if child_dict["id"] != chain[-1]["id"] if chain else True:
                chain.append(child_dict)

        return chain
    finally:
        conn.close()


def find_project_dir(start: Path | None = None) -> Path | None:
    """Find project directory by looking for .exp-tracker/ upwards."""
    current = start or Path.cwd()
    while current != current.parent:
        if (current / DB_DIR).exists():
            return current
        current = current.parent
    # Check root
    if (current / DB_DIR).exists():
        return current
    return None
