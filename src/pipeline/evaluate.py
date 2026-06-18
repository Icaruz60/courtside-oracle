"""
Check yesterday's prediction results and update Supabase.

Run the morning after games complete:
  SUPABASE_URL=... SUPABASE_KEY=... python src/pipeline/evaluate.py

What it does:
  1. Fetches predictions from Supabase where actual_winner is NULL
  2. Pulls completed game results from the NBA game log
  3. Marks each prediction correct/wrong + stores actual_winner
  4. Recomputes and updates the running_record row
"""

import logging
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _get_supabase():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set.")
    return create_client(url, key)


def _infer_season_from_game_id(game_id: str) -> str:
    year_code = int(game_id[3:5])
    year = 2000 + year_code
    return f"{year}-{str(year + 1)[2:]}"


def _fetch_game_results(game_ids: list[str]) -> dict[str, str]:
    """Return {game_id: winning_team_abbrev} for completed games."""
    results: dict[str, str] = {}

    frames = [pd.read_csv(f) for f in sorted(RAW_DIR.glob("game_log_*.csv"))]
    if not frames:
        return results

    df = pd.concat(frames, ignore_index=True)
    df["GAME_ID"] = df["GAME_ID"].astype(str).str.zfill(10)

    missing = [gid for gid in game_ids if gid not in df["GAME_ID"].values]
    if missing:
        # Re-pull game logs to pick up very recent results
        try:
            from pipeline.collect import collect_game_log
            seasons = {_infer_season_from_game_id(gid) for gid in missing}
            for season in seasons:
                for st in ("Regular Season", "Playoffs"):
                    path = RAW_DIR / f"game_log_{'regular' if 'Regular' in st else 'playoffs'}_{season}.csv"
                    if path.exists():
                        path.unlink()
                    collect_game_log(season, st)
            frames2 = [pd.read_csv(f) for f in sorted(RAW_DIR.glob("game_log_*.csv"))]
            df = pd.concat(frames2, ignore_index=True)
            df["GAME_ID"] = df["GAME_ID"].astype(str).str.zfill(10)
        except Exception as exc:
            logger.warning("Could not refresh game logs: %s", exc)

    for gid in game_ids:
        winner_row = df[(df["GAME_ID"] == gid) & (df["WL"] == "W")]
        if not winner_row.empty:
            results[gid] = str(winner_row["TEAM_ABBREVIATION"].iloc[0])

    return results


def evaluate():
    db = _get_supabase()

    # All predictions without a result yet
    resp    = db.table("predictions").select("*").is_("actual_winner", "null").execute()
    pending = resp.data or []

    if not pending:
        logger.info("No pending predictions to evaluate.")
        return

    logger.info("Evaluating %d pending prediction(s)...", len(pending))
    results = _fetch_game_results([p["game_id"] for p in pending])

    updated = 0
    for pred in pending:
        actual = results.get(pred["game_id"])
        if actual is None:
            logger.info("  %s — result not available yet", pred["game_id"])
            continue

        correct = (pred["predicted_team"] == actual)
        db.table("predictions").update({
            "actual_winner": actual,
            "correct":       correct,
        }).eq("game_id", pred["game_id"]).execute()

        logger.info(
            "  %s @ %s  predicted: %s  actual: %s  %s",
            pred["away_team"], pred["home_team"],
            pred["predicted_team"], actual,
            "✓ CORRECT" if correct else "✗ WRONG",
        )
        updated += 1

    if updated == 0:
        logger.info("No completed games found yet.")
        return

    # Recompute running record across all resolved predictions
    all_resp = (
        db.table("predictions")
          .select("correct")
          .not_.is_("correct", "null")
          .execute()
    )
    rows            = all_resp.data or []
    total_correct   = sum(1 for r in rows if r["correct"])
    total_incorrect = sum(1 for r in rows if not r["correct"])
    total           = total_correct + total_incorrect
    accuracy        = round(total_correct / total, 4) if total > 0 else None

    db.table("running_record").upsert({
        "id":              1,
        "total_correct":   total_correct,
        "total_incorrect": total_incorrect,
        "accuracy":        accuracy,
    }, on_conflict="id").execute()

    logger.info(
        "Running record: %d correct / %d total (%.1f%%)",
        total_correct, total, (accuracy or 0) * 100,
    )


if __name__ == "__main__":
    evaluate()
