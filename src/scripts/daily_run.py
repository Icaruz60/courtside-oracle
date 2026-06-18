"""
Daily orchestration entry point for GitHub Actions.

Execution order:
  1. evaluate.py — update yesterday's predictions with actual results
  2. predict.py  — generate today's predictions before games tip off

Exits with code 1 on any failure so GitHub Actions marks the run as failed.
All output is logged to stdout for GitHub Actions to capture.

Usage:
    python src/scripts/daily_run.py

Required environment variables:
    SUPABASE_URL
    SUPABASE_KEY
"""

import logging
import sys
from pathlib import Path

# Ensure src/ is on the path when called from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.evaluate import evaluate_yesterdays_games
from pipeline.predict import predict_todays_games

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("daily_run")


def main() -> None:
    errors: list[str] = []

    # Step 1 — evaluate yesterday's results
    logger.info("=== STEP 1: Evaluating yesterday's results ===")
    try:
        evaluate_yesterdays_games()
        logger.info("Step 1 complete.")
    except Exception as exc:
        msg = f"evaluate.py failed: {exc}"
        logger.error(msg, exc_info=True)
        errors.append(msg)

    # Step 2 — generate today's predictions
    logger.info("=== STEP 2: Generating today's predictions ===")
    try:
        predictions = predict_todays_games()
        logger.info("Step 2 complete. %d prediction(s) stored.", len(predictions))
    except Exception as exc:
        msg = f"predict.py failed: {exc}"
        logger.error(msg, exc_info=True)
        errors.append(msg)

    if errors:
        logger.critical("Daily run finished with %d error(s):", len(errors))
        for e in errors:
            logger.critical("  • %s", e)
        sys.exit(1)

    logger.info("=== Daily run complete. ===")


if __name__ == "__main__":
    main()
