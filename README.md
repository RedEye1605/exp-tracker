# Exp Tracker

Lightweight experiment tracking for ML competitions. No more `submission_v28_drawadj_rank3.csv`.

Tracks experiments, submissions, scores, and hyperparameters with a simple CLI. Zero infrastructure — just SQLite + git.

## Usage

```bash
# Initialize in a competition project
exp-tracker init

# Log an experiment
exp-tracker log --name "xgboost_baseline" --params "lr=0.01,n_est=500" --score 0.8721

# Log a submission with auto-versioning
exp-tracker submit --file submission.csv --note "v34 teacher blend" --score 0.8972

# Compare experiments
exp-tracker compare --top 10

# Show history
exp-tracker history

# Generate report
exp-tracker report --format markdown
```

## Features

- **Auto-versioning:** submission.csv → submission_v{N}_{description}.csv
- **Score tracking:** CV scores, public LB, private LB
- **Hyperparameter logging:** JSON key-value pairs
- **Comparison tables:** Rank experiments by score
- **Git integration:** Auto-commit on submission
- **Markdown reports:** Export for writeups/papers
- **Notes & tags:** Annotate experiments with findings

## Schema

```json
{
  "id": "uuid",
  "name": "xgboost_v3",
  "type": "experiment|submission",
  "params": {"lr": 0.01, "n_est": 500},
  "cv_score": 0.8721,
  "public_lb": null,
  "private_lb": null,
  "submission_file": "submission_v15.csv",
  "notes": "Added feature X, improved by 2%",
  "tags": ["xgboost", "baseline", "feature-engineering"],
  "created_at": "2026-05-01T23:00:00"
}
```

## License

MIT
