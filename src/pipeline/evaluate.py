"""
Result evaluation pipeline.

Runs daily after games complete:
  1. Fetch yesterday's final scores from nba_api
  2. Match results against stored predictions in Supabase
  3. Mark each prediction correct or incorrect
  4. Recompute and update the running_record table

Environment variables required:
  SUPABASE_URL   — your project URL
  SUPABASE_KEY   — service role key (never commit this)
"""

import logging
import os
import sys
from datetime import date, timedelta

import pandas as pd
from nba_api.stats.endpoints import scoreboardv2
from supabase import create_client, Client

from pipeline.collect import _api_call

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set as environment variables.")
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Result fetching
# ---------------------------------------------------------------------------

def fetch_yesterdays_results() -> dict[str, str]:
    """
    Fetch completed game results from yesterday.

    Returns:
        dict mapping game_id → winning side ("home" or "away")
    """
    yesterday = (date.today() - timedelta(days=1)).strftime("%m/%d/%Y")
    logger.info("Fetching results for %s", yesterday)

    try:
        result = _api_call(scoreboardv2.ScoreboardV2, game_date=yesterday)
    except Exception as exc:
        logger.error("Failed to fetch scoreboard for %s: %s", yesterday, exc)
        return {}

    line_score = result.line_score.get_data_frame()
    if line_score.empty:
        logger.info("No completed games found for %s", yesterday)
        return {}

    # line_score has two rows per game (one per team)
    # TEAM_WINS_LOSSES and PTS are the key columns
    # HOME/VISITOR is not directly labelled here — infer from game_header
    game_header = result.game_header.get_data_frame()

    results: dict[str, str] = {}
    for _, game in game_header.iterrows():
        game_id = str(game["GAME_ID"])
        home_id = game["HOME_TEAM_ID"]
        away_id = game["VISITOR_TEAM_ID"]

        home_row = line_score[line_score["TEAM_ID"] == home_id]
        away_row = line_score[line_score["TEAM_ID"] == away_id]

        if home_row.empty or away_row.empty:
            logger.warning("Incomplete line score for game %s", game_id)
            continue

        home_pts = int(home_row.iloc[0]["PTS"] or 0)
        away_pts = int(away_row.iloc[0]["PTS"] or 0)

        if home_pts == away_pts:
            logger.warning("Tied score for game %s — skipping", game_id)
            continue

        results[game_id] = "home" if home_pts > away_pts else "away"
        logger.info(
            "Game %s: home=%d away=%d → %s wins",
            game_id, home_pts, away_pts, results[game_id],
        )

    return results


# ---------------------------------------------------------------------------
# Prediction updating
# ---------------------------------------------------------------------------

def update_predictions_with_results(results: dict[str, str], supabase: Client) -> dict:
    """
    Match actual results against stored predictions and mark correct/incorrect.

    Args:
        results:   game_id → "home" or "away"
        supabase:  authenticated Supabase client

    Returns:
        dict with keys "updated", "correct", "incorrect", "not_found"
    """
    stats = {"updated": 0, "correct": 0, "incorrect": 0, "not_found": 0}

    for game_id, actual_winner in results.items():
        # Find the stored prediction for this game
        response = (
            supabase.table("predictions")
            .select("id, predicted_winner, correct")
            .eq("game_id", game_id)
            .execute()
        )

        if not response.data:
            logger.warning("No prediction found for game_id %s", game_id)
            stats["not_found"] += 1
            continue

        prediction = response.data[0]

        if prediction["correct"] is not None:
            logger.info("Game %s already evaluated, skipping.", game_id)
            continue

        is_correct = prediction["predicted_winner"] == actual_winner

        supabase.table("predictions").update({"correct": is_correct}).eq("id", prediction["id"]).execute()

        stats["updated"] += 1
        if is_correct:
            stats["correct"] += 1
            logger.info("Game %s: CORRECT", game_id)
        else:
            stats["incorrect"] += 1
            logger.info("Game %s: INCORRECT (predicted %s, actual %s)", game_id, prediction["predicted_winner"], actual_winner)

    return stats


# ---------------------------------------------------------------------------
# Running record
# ---------------------------------------------------------------------------

def update_running_record(supabase: Client) -> None:
    """
    Recompute total_correct, total_incorrect, and accuracy from all evaluated predictions
    and upsert into the running_record table.
    """
    response = (
        supabase.table("predictions")
        .select("correct")
        .not_.is_("correct", "null")
        .execute()
    )

    records = response.data
    total_correct = sum(1 for r in records if r["correct"] is True)
    total_incorrect = sum(1 for r in records if r["correct"] is False)
    total = total_correct + total_incorrect
    accuracy = round(total_correct / total, 4) if total > 0 else 0.0

    supabase.table("running_record").upsert({
        "id": 1,
        "total_correct": total_correct,
        "total_incorrect": total_incorrect,
        "accuracy": accuracy,
    }).execute()

    logger.info(
        "Running record: %d correct / %d incorrect (%.1f%% accuracy)",
        total_correct, total_incorrect, accuracy * 100,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def evaluate_yesterdays_games() -> None:
    supabase = _get_supabase()
    results = fetch_yesterdays_results()

    if not results:
        logger.info("No results to evaluate.")
        return

    stats = update_predictions_with_results(results, supabase)
    logger.info("Evaluation summary: %s", stats)
    update_running_record(supabase)


if __name__ == "__main__":
    try:
        evaluate_yesterdays_games()
    except Exception as exc:
        logger.critical("evaluate.py failed: %s", exc, exc_info=True)
        sys.exit(1)
