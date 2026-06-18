"""
Player ELO calculation from per-game box score data.

Design
------
Each player has 7 skill ELOs + 1 general ELO (sum of all skills).

Every game, for each skill:
  1. Qualify players with >= MIN_MINUTES played.
  2. Compute a composite skill score (z-scored components averaged).
  3. Rank players 1..N by score (1 = best).
  4. Convert rank → raw delta via a dynamic zero-centered scale:
       Odd  N: middle player gets 0, above +1/+2/..., below -1/-2/...
       Even N: no zero; top half +1/+2/..., bottom half -1/-2/...
  5. Scale delta by sqrt(minutes / 36) — shrinks noise for short stints.
  6. Mean-subtract all scaled deltas so the game is exactly zero-sum.
  7. Add delta to each player's skill ELO.

Skills
------
  scoring     — points/36 + true shooting %
  playmaking  — assists/36 + assist-to-turnover ratio
  defense     — defensive rating (inverted) + steals/36 + blocks/36
  rebounding  — rebound percentage
  efficiency  — PIE (NBA's Player Impact Estimate)
  hustle      — speed + distance + touches/36  [skipped if no tracking file]
  three_point — 3PM/36 + 3P%  [only for players who attempted >= 1 three]

Outputs
-------
  data/processed/player_elo.parquet
    One row per player per game — the ELO snapshot BEFORE that game.
    Columns: game_id, game_date, player_id,
             pre_{skill}_elo × 7, pre_general_elo
    Use in features.py: filter by game_id to get all players' incoming ELOs.

  data/processed/player_elo_current.parquet
    Most recent ELO per player — used for today's game predictions.

Run
---
  python src/pipeline/elo.py                # build from scratch
  python src/pipeline/elo.py --force        # reprocess even if output exists
"""

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INITIAL_ELO = 1000.0
MIN_MINUTES = 10.0      # minimum minutes to qualify for ranking in a game

SKILLS = [
    "scoring",
    "playmaking",
    "defense",
    "rebounding",
    "efficiency",
    "hustle",
    "three_point",
]


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _parse_minutes(value) -> float:
    """Parse 'MM:SS' string or bare float to float minutes. Returns 0.0 on failure."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    try:
        if ":" in s:
            mm, ss = s.split(":", 1)
            return float(mm) + float(ss) / 60.0
        return float(s)
    except ValueError:
        return 0.0


def _load_player_dataset(game_id: str, endpoint: str) -> pd.DataFrame | None:
    """
    Load the PlayerStats dataset from one box score JSON file.
    Returns None if the file is absent, a sentinel, or unreadable.
    """
    path = RAW_DIR / f"boxscore_{endpoint}_{game_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    if data.get("_absent"):
        return None
    if "PlayerStats" not in data:
        return None
    ds = data["PlayerStats"]
    return pd.DataFrame(ds["data"], columns=ds["headers"])


def load_game_players(game_id: str) -> pd.DataFrame | None:
    """
    Merge traditional + advanced + tracking box scores for one game.

    Returns a single DataFrame with one row per player containing all stats
    needed for ELO computation. Returns None if core data is missing.
    """
    trad = _load_player_dataset(game_id, "traditional")
    adv  = _load_player_dataset(game_id, "advanced")

    if trad is None or adv is None:
        return None

    # Parse minutes to float
    trad = trad.copy()
    trad["minutes_float"] = trad["minutes"].apply(_parse_minutes)

    # Keep only what we need from advanced (avoid duplicate columns)
    adv_cols = [
        "personId",
        "defensiveRating",
        "trueShootingPercentage",
        "usagePercentage",
        "assistToTurnover",
        "reboundPercentage",
        "PIE",
    ]
    adv_cols = [c for c in adv_cols if c in adv.columns]
    df = trad.merge(adv[adv_cols], on="personId", how="left")

    # Optionally add tracking (hustle skill)
    track = _load_player_dataset(game_id, "tracking")
    if track is not None:
        track_cols = [c for c in ["personId", "speed", "distance", "touches"] if c in track.columns]
        df = df.merge(track[track_cols], on="personId", how="left")

    df["personId"] = df["personId"].astype(str)
    return df


# ---------------------------------------------------------------------------
# Skill score computation
# ---------------------------------------------------------------------------

def _zscore(s: pd.Series) -> pd.Series:
    """Z-score a series within a game. Returns zeros if std == 0 or all NaN."""
    std = s.std()
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


def _per36(stat: pd.Series, minutes: pd.Series) -> pd.Series:
    """Normalize a counting stat to per-36-minutes rate."""
    return stat / minutes.clip(lower=0.01) * 36.0


def _col(df: pd.DataFrame, name: str, fill=0.0) -> pd.Series:
    """Get a column from df, filling with `fill` if absent or all-NaN."""
    if name not in df.columns:
        return pd.Series(fill, index=df.index, dtype=float)
    return df[name].fillna(fill).astype(float)


def compute_skill_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a score_{skill} column for each skill to df.

    Each skill score is the sum of z-scored components. Z-scoring within
    the game puts all components on the same scale regardless of units.
    NaN scores mean the player is excluded from that skill's ranking.
    """
    df = df.copy()
    m = df["minutes_float"]

    # ── scoring ──────────────────────────────────────────────────────────────
    pts36 = _per36(_col(df, "points"), m)
    ts    = _col(df, "trueShootingPercentage", fill=df["trueShootingPercentage"].median()
                 if "trueShootingPercentage" in df.columns else 0.0)
    df["score_scoring"] = _zscore(pts36) + _zscore(ts)

    # ── playmaking ───────────────────────────────────────────────────────────
    ast36 = _per36(_col(df, "assists"), m)
    a2t   = _col(df, "assistToTurnover", fill=0.0)
    df["score_playmaking"] = _zscore(ast36) + _zscore(a2t)

    # ── defense ──────────────────────────────────────────────────────────────
    # defensiveRating: lower = better → negate z-score
    drtg  = _col(df, "defensiveRating",
                 fill=df["defensiveRating"].median() if "defensiveRating" in df.columns else 110.0)
    stl36 = _per36(_col(df, "steals"), m)
    blk36 = _per36(_col(df, "blocks"), m)
    df["score_defense"] = -_zscore(drtg) + _zscore(stl36) + _zscore(blk36)

    # ── rebounding ───────────────────────────────────────────────────────────
    reb_pct = _col(df, "reboundPercentage",
                   fill=_per36(_col(df, "reboundsTotal"), m))
    df["score_rebounding"] = _zscore(reb_pct)

    # ── efficiency ───────────────────────────────────────────────────────────
    pie = _col(df, "PIE", fill=0.0)
    df["score_efficiency"] = _zscore(pie)

    # ── hustle (requires tracking data) ──────────────────────────────────────
    has_tracking = all(c in df.columns for c in ["speed", "distance", "touches"])
    if has_tracking:
        speed  = _col(df, "speed",    fill=0.0)
        dist   = _col(df, "distance", fill=0.0)
        tch36  = _per36(_col(df, "touches", fill=0.0), m)
        df["score_hustle"] = _zscore(speed) + _zscore(dist) + _zscore(tch36)
    else:
        df["score_hustle"] = np.nan  # skip hustle this game

    # ── three_point (only for players who attempted >= 1 three) ──────────────
    tpa   = _col(df, "threePointersAttempted", fill=0.0)
    tpm36 = _per36(_col(df, "threePointersMade"), m)
    tp_pct = _col(df, "threePointersPercentage", fill=0.0)
    three_score = _zscore(tpm36) + _zscore(tp_pct)
    df["score_three_point"] = np.where(tpa > 0, three_score, np.nan)

    return df


# ---------------------------------------------------------------------------
# Rank → delta
# ---------------------------------------------------------------------------

def rank_to_delta(rank: int, n: int) -> int:
    """
    Convert 1-indexed rank to ELO delta on a dynamic zero-centered scale.

    Odd  N=15: rank 1 → +7, rank 8 → 0,  rank 15 → -7
    Even N=20: rank 1 → +10, rank 10 → +1, rank 11 → -1, rank 20 → -10

    Sum of all deltas is always 0 (zero-sum per game per skill).
    """
    if n % 2 == 1:          # odd — single middle player gets 0
        return (n + 1) // 2 - rank
    else:                   # even — no zero, gap between the two middle ranks
        half = n // 2
        return half - rank + (1 if rank <= half else 0)


def compute_deltas(scores: pd.Series, minutes: pd.Series) -> pd.Series:
    """
    Given per-player skill scores and minutes, return minutes-weighted
    zero-sum ELO deltas.

    Players with NaN score or < MIN_MINUTES receive NaN (no ELO update).

    Steps:
      1. Filter to qualified players (score not NaN, minutes >= MIN_MINUTES)
      2. Rank by score (1 = best); ties → average rank, rounded to nearest int
      3. raw_delta = rank_to_delta(rank, n)
      4. scaled    = raw_delta × sqrt(minutes / 36)
      5. final     = scaled − mean(scaled)   ← preserves zero-sum

    Returns a Series aligned to the original index, NaN for excluded players.
    """
    valid = scores.notna() & (minutes >= MIN_MINUTES)
    if valid.sum() < 2:
        return pd.Series(np.nan, index=scores.index)

    valid_scores  = scores[valid]
    valid_minutes = minutes[valid]
    n             = len(valid_scores)

    # Rank: 1 = highest score. Average ties, round to integer.
    ranks = valid_scores.rank(ascending=False, method="average").round().astype(int)
    raw   = ranks.map(lambda r: rank_to_delta(r, n)).astype(float)

    # Scale by minutes played
    scaled = raw * np.sqrt(valid_minutes / 36.0)

    # Mean-subtract → zero-sum
    final = scaled - scaled.mean()

    return final.reindex(scores.index)   # NaN for excluded players


# ---------------------------------------------------------------------------
# Game date index
# ---------------------------------------------------------------------------

def build_game_date_index() -> pd.DataFrame:
    """
    Return a DataFrame of (GAME_ID, GAME_DATE) sorted chronologically,
    built from all game log CSVs collected in Phase 1.
    """
    frames = []
    for csv in sorted(RAW_DIR.glob("game_log_*.csv")):
        df = pd.read_csv(csv, usecols=["GAME_ID", "GAME_DATE"])
        frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No game_log_*.csv files found in {RAW_DIR}")

    index = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates("GAME_ID")
        .assign(
            GAME_ID   = lambda d: d["GAME_ID"].astype(str).str.zfill(10),
            GAME_DATE = lambda d: pd.to_datetime(d["GAME_DATE"]),
        )
        .sort_values("GAME_DATE")
        .reset_index(drop=True)
    )
    return index


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_elo(force: bool = False) -> pd.DataFrame:
    """
    Process all games chronologically and compute the full player ELO history.

    Args:
        force: Reprocess and overwrite even if output already exists.

    Returns:
        DataFrame with pre-game ELO snapshots (one row per player per game).
    """
    out_path = PROCESSED_DIR / "player_elo.parquet"

    if out_path.exists() and not force:
        logger.info("ELO already built — loading from %s", out_path)
        return pd.read_parquet(out_path)

    game_index = build_game_date_index()
    logger.info("Building ELO across %d games", len(game_index))

    # Live ELO state: player_id → {skill → float}
    elo: dict[str, dict[str, float]] = defaultdict(
        lambda: {s: INITIAL_ELO for s in SKILLS}
    )

    records: list[dict] = []

    for _, row in tqdm(game_index.iterrows(), total=len(game_index), desc="ELO  games"):
        game_id   = str(row["GAME_ID"]).zfill(10)
        game_date = row["GAME_DATE"]

        df = load_game_players(game_id)
        if df is None or df.empty:
            continue

        # Keep only players who qualify (>= MIN_MINUTES)
        df = df[df["minutes_float"] >= MIN_MINUTES].copy()
        if df.empty:
            continue

        # ── Snapshot PRE-game ELO for every qualifying player ────────────────
        for pid in df["personId"].unique():
            player_elo = elo[pid]
            rec = {
                "game_id":        game_id,
                "game_date":      game_date,
                "player_id":      pid,
                "pre_general_elo": sum(player_elo[s] for s in SKILLS),
            }
            for skill in SKILLS:
                rec[f"pre_{skill}_elo"] = player_elo[skill]
            records.append(rec)

        # ── Compute skill scores ──────────────────────────────────────────────
        # Deduplicate personId — a player traded same-day can appear for both
        # teams in one game file. Keep the entry with the most minutes.
        df = compute_skill_scores(df)
        df = (df.sort_values("minutes_float", ascending=False)
                .drop_duplicates("personId", keep="first")
                .set_index("personId"))

        # ── For each skill: rank → delta → update ELO ────────────────────────
        for skill in SKILLS:
            score_col = f"score_{skill}"
            if score_col not in df.columns:
                continue

            deltas = compute_deltas(df[score_col], df["minutes_float"])

            for pid, delta in deltas.items():
                if pd.notna(delta):
                    elo[pid][skill] = elo[pid][skill] + float(delta)

    if not records:
        raise RuntimeError("No ELO records generated — verify box score files exist")

    result = pd.DataFrame(records)

    # Enforce column order
    ordered_cols = (
        ["game_id", "game_date", "player_id", "pre_general_elo"]
        + [f"pre_{s}_elo" for s in SKILLS]
    )
    result = result[ordered_cols]

    result.to_parquet(out_path, index=False)
    logger.info("Saved ELO history: %d records → %s", len(result), out_path)

    # Current (most recent) ELO per player — used for prediction on new games
    current = (
        result.sort_values("game_date")
              .groupby("player_id", as_index=False)
              .last()
    )
    current_path = PROCESSED_DIR / "player_elo_current.parquet"
    current.to_parquet(current_path, index=False)
    logger.info("Saved current ELO: %d players → %s", len(current), current_path)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build player ELO from box score data")
    parser.add_argument("--force", action="store_true", help="Reprocess even if output exists")
    args = parser.parse_args()

    df = build_elo(force=args.force)
    print(f"\nDone. {len(df):,} records, {df['player_id'].nunique():,} unique players.")
    print(df.head(3).to_string())
