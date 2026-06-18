"""
Incremental update for the current season.

Run this after new games are played to bring ELOs up to date.
Specifically:
  1. Re-pulls game_log_playoffs_2025-26.csv  (replaces the stale May 23 file)
  2. Re-pulls player_season_stats_2025-26.csv
  3. Finds game IDs with no box score yet
  4. Collects missing box scores (respects existing proxy/rate-limit setup)
  5. Rebuilds player ELO from scratch  (fast — ~10 min)

Run
---
  python src/pipeline/update_season.py
  python src/pipeline/update_season.py --season 2025-26   # explicit season
  PROXIES=http://... python src/pipeline/update_season.py # with proxies
"""

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _refresh_game_logs(season: str) -> set[str]:
    """Force re-pull both regular and playoff game logs for the season. Returns all game IDs."""
    from pipeline.collect import collect_game_log, RAW_DIR as CRAW

    game_ids: set[str] = set()

    for slug, season_type in [("regular", "Regular Season"), ("playoffs", "Playoffs")]:
        path = CRAW / f"game_log_{slug}_{season}.csv"
        if path.exists():
            logger.info("Removing stale %s", path.name)
            path.unlink()

        logger.info("Pulling game_log_%s_%s ...", slug, season)
        try:
            df = collect_game_log(season, season_type)
            ids = set(df["GAME_ID"].astype(str).str.zfill(10).tolist())
            game_ids.update(ids)
            logger.info("  %d games in %s %s", len(ids) // 2, slug, season)
        except Exception as exc:
            logger.error("  Failed to pull %s %s: %s", slug, season, exc)

    return game_ids


def _refresh_player_stats(season: str) -> None:
    """Force re-pull player season stats."""
    from pipeline.collect import collect_player_season_stats, RAW_DIR as CRAW

    path = CRAW / f"player_season_stats_{season}.csv"
    if path.exists():
        logger.info("Removing stale %s", path.name)
        path.unlink()

    logger.info("Pulling player_season_stats_%s ...", season)
    try:
        collect_player_season_stats(season)
        logger.info("  Done.")
    except Exception as exc:
        logger.error("  Failed: %s", exc)


def _missing_box_score_ids(game_ids: set[str]) -> list[str]:
    """Return game IDs that have no traditional box score file yet."""
    missing = []
    for gid in sorted(game_ids):
        path = RAW_DIR / f"boxscore_traditional_{gid}.json"
        if not path.exists():
            missing.append(gid)
    logger.info(
        "%d / %d games missing box scores",
        len(missing), len(game_ids),
    )
    return missing


def _collect_missing_box_scores(missing: list[str], workers: int = 1) -> None:
    """Collect box scores for a specific list of game IDs."""
    from pipeline.collect import collect_game_boxscores, _pool, ProxyPool

    if not missing:
        logger.info("No missing box scores — nothing to collect.")
        return

    logger.info("Collecting box scores for %d games (workers=%d)...", len(missing), workers)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(collect_game_boxscores, gid): gid for gid in missing}
        with tqdm(total=len(missing), desc="Box scores", unit="game", ncols=88) as pbar:
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as exc:
                    logger.error("Box score failed: %s", exc)
                pbar.update(1)


def main(season: str = "2025-26") -> None:
    # Set up proxy pool if provided
    proxy_env = os.environ.get("PROXIES", "")
    proxies   = [p.strip() for p in proxy_env.split(",") if p.strip()]
    workers   = int(os.environ.get("WORKERS", max(1, len(proxies))))

    if proxies:
        from pipeline.collect import ProxyPool, _pool
        import pipeline.collect as _col
        _col._pool = ProxyPool(proxies)
        logger.info("Proxy pool: %d slots | %d workers", len(proxies), workers)
    else:
        import pipeline.collect as _col
        from pipeline.collect import ProxyPool
        _col._pool = ProxyPool([None])
        logger.info("No proxies — single-threaded")

    # 1. Refresh game logs
    logger.info("=== Step 1: Refresh game logs for %s ===", season)
    all_game_ids = _refresh_game_logs(season)
    logger.info("Total game IDs this season: %d", len(all_game_ids))

    # 2. Refresh player stats
    logger.info("=== Step 2: Refresh player season stats ===")
    _refresh_player_stats(season)

    # 3. Find and collect missing box scores
    logger.info("=== Step 3: Collect missing box scores ===")
    missing = _missing_box_score_ids(all_game_ids)
    _collect_missing_box_scores(missing, workers=workers)

    # 4. Rebuild ELO
    logger.info("=== Step 4: Rebuild player ELO ===")
    from pipeline.elo import build_elo
    build_elo(force=True)

    logger.info("=== Update complete. ELOs are now current through today. ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Incremental season data + ELO update")
    parser.add_argument("--season", default="2025-26", help="Season to update (default: 2025-26)")
    args = parser.parse_args()
    main(season=args.season)
