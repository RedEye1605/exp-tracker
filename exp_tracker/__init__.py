"""
Exp Tracker — Lightweight ML experiment tracking for competitions.

Provides a simple, portable way to track ML experiments without external dependencies
or complex infrastructure. Experiments are stored in a SQLite database at
`.exp-tracker/experiments.db` in the project directory.

Example usage::

    >>> from exp_tracker import init, log_experiment, update_score, list_experiments
    >>>
    >>> # Initialize in project
    >>> init()  # Creates .exp-tracker/experiments.db in current directory
    >>>>
    >>> # Log an experiment
    >>> log_experiment(
    >>>     name="baseline",
    >>>     params={"model":"xgboost","n_estimators":100},
    >>>     cv_score=0.85,
    >>>     notes="Simple baseline model"
    >>> )
    >>>>
    >>> # Update with test score later
    >>> update_score("baseline", test_score=0.82)
    >>>>
    >>> # List all experiments
    >>> list_experiments()
    >>>>
    >>> # Compare top 5 models by CV score
    >>> compare_experiments(top=5, metric="cv_score")
"""

__version__ = "0.2.0"

__all__ = [
    "init",
    "log_experiment",
    "log_submission",
    "update_score",
    "list_experiments",
    "compare_experiments",
    "get_lineage",
]
