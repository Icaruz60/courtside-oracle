"""
Daily prediction pipeline.

Runs before games tip off each day:
  1. Fetch today's scheduled games from nba_api
  2. Build a feature vector for each game using features.py
  3. Load the trained model from models/xgb_model.pkl
  4. Generate prediction (home/away winner) + confidence probability
  5. Generate SHAP values via shap_export.py
  6. Write predictions to Supabase

Environment variables required:
  SUPABASE_URL   — your project URL
  SUPABASE_KEY   — service role key (never commit this)
"""

import logging
import os
import pickle
import sys
from pathlib import Path

import pandas as pd
from supabase import create_client, Client

from pipeline import collect, features, shap_export

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "models" / "xgb_model.pkl"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


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
# Model loading
# ---------------------------------------------------------------------------

def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run train.py first."
        )
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


# ---------------------------------------------------------------------------
# Prediction logic
# ---------------------------------------------------------------------------

def _team_id_to_abbreviation(team_id: int, game_log_df: pd.DataFrame) -> str:
    """Resolve a team ID to its abbreviation from the game log."""
    rows = game_log_df[game_log_df["TEAM_ID"] == team_id]["TEAM_ABBREVIATION"]
    return str(rows.iloc[0]) if not rows.empty else str(team_id)


def predict_todays_games() -> list[dict]:
    """
    Generate predictions for all of today's scheduled games.

    Returns:
        List of prediction dicts (also written to Supabase).
    """
    supabase = _get_supabase()
    model = load_model()

    # Today's games
    todays_games = collect.collect_todays_games()
    if todays_games.empty:
        logger.info("No games scheduled today.")
        return []

    # Load season data needed for feature engineering
    # The current season is inferred from the game dates
    sample_date = pd.to_datetime(todays_games["GAME_DATE_EST"].iloc[0])
    year = sample_date.year if sample_date.month >= 10 else sample_date.year - 1
    season = f"{year}-{str(year + 1)[2:]}"

    game_log_path = RAW_DIR / f"league_game_log_{season}.csv"
    player_stats_path = RAW_DIR / f"player_stats_{season}.csv"

    if not game_log_path.exists() or not player_stats_path.exists():
        raise FileNotFoundError(
            f"Season data for {season} not found in {RAW_DIR}. "
            "Run collect.py to pull current season data first."
        )

    game_log_df = pd.read_csv(game_log_path)
    player_stats_df = pd.read_csv(player_stats_path)

    predictions = []

    for _, game in todays_games.iterrows():
        game_id = str(game["GAME_ID"])
        game_date = str(game["GAME_DATE_EST"])[:10]
        home_team_id = str(game["HOME_TEAM_ID"])
        away_team_id = str(game["VISITOR_TEAM_ID"])
        home_team = _team_id_to_abbreviation(int(home_team_id), game_log_df)
        away_team = _team_id_to_abbreviation(int(away_team_id), game_log_df)

        logger.info("Predicting: %s vs %s (%s)", away_team, home_team, game_date)

        try:
            feature_dict = features.build_feature_matrix(
                game_id=game_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                game_date=game_date,
                season=season,
                game_log_df=game_log_df,
                player_stats_df=player_stats_df,
            )
        except Exception as exc:
            logger.error("Feature engineering failed for %s: %s", game_id, exc)
            continue

        feature_row = pd.DataFrame([feature_dict])
        prob_home_win = float(model.predict_proba(feature_row)[0][1])
        predicted_winner = "home" if prob_home_win >= 0.5 else "away"
        confidence = prob_home_win if predicted_winner == "home" else 1 - prob_home_win
        predicted_team = home_team if predicted_winner == "home" else away_team

        prediction_record = {
            "game_id": game_id,
            "game_date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "predicted_winner": predicted_winner,
            "predicted_team": predicted_team,
            "confidence": round(confidence, 4),
        }

        # Write to Supabase
        try:
            response = supabase.table("predictions").insert(prediction_record).execute()
            prediction_id = response.data[0]["id"]
            logger.info(
                "Stored prediction: %s wins (%.0f%% confidence) → id=%s",
                predicted_team, confidence * 100, prediction_id,
            )

            # Generate and store SHAP values
            shap_export.export_shap_for_prediction(
                prediction_id=prediction_id,
                model=model,
                feature_row=feature_row,
                supabase=supabase,
            )

        except Exception as exc:
            logger.error("Supabase write failed for game %s: %s", game_id, exc)
            continue

        predictions.append(prediction_record)

    logger.info("Predictions complete: %d game(s) processed.", len(predictions))
    return predictions


if __name__ == "__main__":
    try:
        predict_todays_games()
    except Exception as exc:
        logger.critical("predict.py failed: %s", exc, exc_info=True)
        sys.exit(1)
