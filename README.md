# courtside-oracle

NBA game outcome predictor using XGBoost + SHAP. Runs daily via GitHub Actions, stores predictions and results in Supabase, and exposes data for a Next.js website integration.

**Live accuracy tracked publicly** — every prediction is logged with a confidence score and marked correct or incorrect after games complete.

---

## Architecture

```
nba_api  →  collect.py  →  data/raw/
                              ↓
                          features.py  →  feature matrix
                              ↓
                          train.py  →  models/xgb_model.pkl
                              ↓
         daily_run.py ──┬──  predict.py  →  Supabase: predictions + shap_values
   (GitHub Actions cron) └──  evaluate.py  →  Supabase: correct/incorrect + running_record
```

---

## Local setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

Create a `.env` file (never commit this) or export directly:

```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your-service-role-key
```

### 3. Set up Supabase schema

In the Supabase dashboard → SQL Editor, paste and run the contents of:

```
src/supabase/schema.sql
```

---

## Running the pipeline

### Full historical data pull (one-time bootstrap)

Pulls game logs, player stats, and box scores from 2000-01 through 2024-25.
**Expect 2–6 hours** — nba_api requires rate limiting between requests.

```bash
python src/pipeline/collect.py
```

Data is saved to `src/data/raw/`. Already-cached seasons are skipped on re-runs.

### Feature engineering

Feature engineering is scaffolded in `src/pipeline/features.py` — implement the `TODO` blocks before training.
Once complete, generate the feature matrix:

```bash
python -c "from pipeline.features import build_feature_matrix; ..."
```

(Implement a batch script here once feature logic is filled in.)

### Train the model

```bash
python src/pipeline/train.py
```

Outputs:
- `src/models/xgb_model.pkl` — saved model
- `src/data/processed/train_metrics.json` — accuracy, AUC-ROC, Brier score
- `src/data/processed/feature_importance.csv` — ranked feature importance

### Run the daily pipeline manually

```bash
python src/scripts/daily_run.py
```

This runs evaluate (yesterday's results) then predict (today's games) in sequence.

### Generate global SHAP plots

```bash
python -c "
from pipeline.shap_export import generate_global_shap_plots, generate_shap_summary_stats
import pickle, pandas as pd
model = pickle.load(open('src/models/xgb_model.pkl', 'rb'))
X = pd.read_csv('src/data/processed/feature_matrix.csv').drop(columns=['game_date','game_id','home_team_win'])
generate_global_shap_plots(model, X.tail(2000))
generate_shap_summary_stats(model, X.tail(2000))
"
```

---

## Feature engineering

`src/pipeline/features.py` is scaffolded with:

**Fully implemented helpers:**
- `rolling_window(series, window)` — mean of last N non-null values
- `split_home_away(team_id, game_log_df)` — splits a team's games by home/away
- `days_rest_calculator(team_id, game_date, game_log_df)` — integer days since last game
- `is_back_to_back(team_id, game_date, game_log_df)` — 0/1 flag

**Feature functions (TODO — implement the logic):**
| Function | Features returned |
|---|---|
| `get_team_rolling_stats` | Last-5, last-10, season avg for pts/reb/ast/TO/ratings |
| `get_home_away_splits` | Win%, pts avg, pts allowed for home vs away |
| `get_rest_features` | Days rest, back-to-back flag, games in last 7 days |
| `get_head_to_head_features` | H2H wins/losses this season |
| `get_player_availability_features` | Availability score, star player out flag |
| `get_efficiency_differential_features` | Offensive vs defensive rating matchup diff |
| `get_player_form_features` | Top-3 players' recent form vs season average |
| `get_streak_features` | Win/loss streak, last-5 win % |

---

## Gitignored (regenerate locally)

- `src/data/raw/` — regenerate with `collect.py`
- `src/data/processed/` — regenerate by running features + train
- `src/models/*.pkl` — regenerate with `train.py`

---

## GitHub Actions setup

Add a workflow file at `.github/workflows/daily.yml`:

```yaml
name: Daily predictions

on:
  schedule:
    - cron: '0 14 * * *'  # 10am ET — adjust for your timezone / tipoff window
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python src/scripts/daily_run.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

Add `SUPABASE_URL` and `SUPABASE_KEY` to your repository's GitHub Actions secrets.
The model file is not committed — you'll need to either commit it or download it as an artifact in CI.
