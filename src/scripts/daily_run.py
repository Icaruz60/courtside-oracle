"""
Daily orchestration entry point for GitHub Actions.

Usage:
    python src/scripts/daily_run.py --predict    # run predictions only
    python src/scripts/daily_run.py --evaluate   # run evaluation only
    python src/scripts/daily_run.py              # run both

Required environment variables:
    SUPABASE_URL
    SUPABASE_KEY
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("daily_run")


def run_predict():
    """Fetch today's schedule and predict all games."""
    from pipeline.predict import predict_todays_games
    predictions = predict_todays_games()
    logger.info("Predictions complete: %d game(s) stored.", len(predictions))


def run_evaluate():
    """Check results for unresolved predictions."""
    from pipeline.evaluate import evaluate
    evaluate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predict",  action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    run_both = not args.predict and not args.evaluate

    errors = []

    if args.evaluate or run_both:
        logger.info("=== Evaluating results ===")
        try:
            run_evaluate()
        except Exception as exc:
            logger.error("evaluate failed: %s", exc, exc_info=True)
            errors.append(str(exc))

    if args.predict or run_both:
        logger.info("=== Generating predictions ===")
        try:
            run_predict()
        except Exception as exc:
            logger.error("predict failed: %s", exc, exc_info=True)
            errors.append(str(exc))

    if errors:
        sys.exit(1)

    logger.info("=== Done. ===")


if __name__ == "__main__":
    main()
