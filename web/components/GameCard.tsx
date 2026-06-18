import type { Prediction, ShapValue } from "@/lib/types";
import { TEAM_NAMES } from "@/lib/teams";
import TeamLogo from "./TeamLogo";

const FEATURE_LABELS: Record<string, string> = {
  diff_net_last10:         "Net Rating Diff (L10)",
  diff_net_last5:          "Net Rating Diff (L5)",
  elo_general_diff:        "Overall ELO Edge",
  elo_efficiency_diff:     "Efficiency ELO Edge",
  elo_scoring_diff:        "Scoring ELO Edge",
  elo_defense_diff:        "Defense ELO Edge",
  elo_playmaking_diff:     "Playmaking ELO Edge",
  elo_rebounding_diff:     "Rebounding ELO Edge",
  net_efficiency_advantage:"Scoring Efficiency Edge",
  diff_win_pct_last10:     "Win % Diff (L10)",
  diff_win_pct_last5:      "Win % Diff (L5)",
  home_general_elo:        "Home Overall ELO",
  away_general_elo:        "Away Overall ELO",
  home_efficiency_elo:     "Home Efficiency ELO",
  away_efficiency_elo:     "Away Efficiency ELO",
  home_days_rest:          "Home Rest Days",
  away_days_rest:          "Away Rest Days",
  rest_diff:               "Rest Advantage",
  home_is_back_to_back:    "Home Back-to-Back",
  away_is_back_to_back:    "Away Back-to-Back",
  home_star_player_out:    "Home Star Out",
  away_star_player_out:    "Away Star Out",
  away_availability_score: "Away Availability",
  home_availability_score: "Home Availability",
  h2h_home_win_pct:        "Head-to-Head Win %",
};

function formatFeatureName(raw: string): string {
  return FEATURE_LABELS[raw] ?? raw.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

interface Props {
  prediction: Prediction;
  shap?: ShapValue[];
}

export default function GameCard({ prediction, shap }: Props) {
  const {
    home_team, away_team, home_team_id, away_team_id,
    predicted_team, home_win_prob, away_win_prob,
    confidence, actual_winner, correct, game_date,
  } = prediction;

  const homeProb = home_win_prob ?? 0.5;
  const awayProb = away_win_prob ?? (1 - homeProb);
  const homeName = TEAM_NAMES[home_team] ?? home_team;
  const awayName = TEAM_NAMES[away_team] ?? away_team;
  const date     = new Date(game_date + "T12:00:00").toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });

  const isPending = actual_winner === null;
  const topShap   = shap?.slice(0, 5) ?? [];
  const maxShap   = Math.max(...topShap.map(s => Math.abs(s.shap_value)), 0.01);

  return (
    <div className="bg-brand-card border border-brand-border rounded-2xl overflow-hidden">

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-brand-border">
        <span className="text-xs text-brand-muted tracking-widest uppercase">
          {date}
        </span>
        {!isPending && (
          <span className={`text-xs font-bold tracking-widest px-2 py-0.5 rounded-full ${
            correct ? "bg-green-950 text-brand-green" : "bg-red-950 text-red-400"
          }`}>
            {correct ? "✓ CORRECT" : "✗ WRONG"}
          </span>
        )}
        {isPending && (
          <span className="text-xs text-brand-muted tracking-widest">PENDING</span>
        )}
      </div>

      {/* Teams */}
      <div className="flex items-center justify-between px-6 py-5 gap-4">
        {/* Away */}
        <div className="flex flex-col items-center gap-2 flex-1">
          <TeamLogo abbrev={away_team} teamId={away_team_id} size={56} />
          <span className="text-sm font-bold text-white tracking-wide">{away_team}</span>
          <span className="text-xs text-brand-muted hidden sm:block">{awayName}</span>
        </div>

        {/* VS + probability bar */}
        <div className="flex flex-col items-center gap-3 flex-[2]">
          <span className="text-xs text-brand-muted tracking-[0.3em]">VS</span>

          {/* Prob bar */}
          <div className="w-full h-2 rounded-full bg-brand-border overflow-hidden flex">
            <div
              className="h-full bg-brand-green transition-all duration-500"
              style={{ width: `${homeProb * 100}%` }}
            />
          </div>
          <div className="flex justify-between w-full text-xs text-brand-muted">
            <span>{(awayProb * 100).toFixed(0)}%</span>
            <span>{(homeProb * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Home */}
        <div className="flex flex-col items-center gap-2 flex-1">
          <TeamLogo abbrev={home_team} teamId={home_team_id} size={56} />
          <span className="text-sm font-bold text-white tracking-wide">{home_team}</span>
          <span className="text-xs text-brand-muted hidden sm:block">{homeName}</span>
        </div>
      </div>

      {/* Prediction */}
      <div className="mx-5 mb-4 px-4 py-3 bg-brand-bg rounded-xl flex items-center justify-between">
        <div>
          <p className="text-[10px] tracking-widest text-brand-muted uppercase mb-0.5">
            Predicted Winner
          </p>
          <p className="text-lg font-black text-white tracking-wide">
            {TEAM_NAMES[predicted_team] ?? predicted_team}
            <span className="text-sm font-normal text-brand-muted ml-2">
              ({(confidence * 100).toFixed(0)}% confident)
            </span>
          </p>
        </div>
        {actual_winner && (
          <div className="text-right">
            <p className="text-[10px] tracking-widest text-brand-muted uppercase mb-0.5">
              Actual
            </p>
            <p className="text-lg font-black text-white">
              {TEAM_NAMES[actual_winner] ?? actual_winner}
            </p>
          </div>
        )}
      </div>

      {/* SHAP factors */}
      {topShap.length > 0 && (
        <div className="px-5 pb-5">
          <p className="text-[10px] tracking-widest text-brand-muted uppercase mb-3">
            Top Factors
          </p>
          <div className="flex flex-col gap-2">
            {topShap.map((s) => {
              const isHome    = s.shap_value > 0;
              const pct       = (Math.abs(s.shap_value) / maxShap) * 100;
              return (
                <div key={s.id} className="flex items-center gap-3 text-xs">
                  <span className="text-brand-muted w-40 shrink-0 truncate">
                    {formatFeatureName(s.feature_name)}
                  </span>
                  <div className="flex-1 flex items-center gap-1.5">
                    <div className="flex-1 h-1.5 rounded-full bg-brand-border overflow-hidden">
                      <div
                        className={`h-full rounded-full ${isHome ? "bg-brand-green" : "bg-red-500"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className={`text-[10px] shrink-0 ${isHome ? "text-brand-green" : "text-red-400"}`}>
                      → {isHome ? home_team : away_team}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}
