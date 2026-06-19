"use client";

import { useEffect, useState } from "react";
import { getRecentPredictions, getRunningRecord } from "@/lib/supabase";
import { TEAM_NAMES } from "@/lib/teams";
import type { Prediction, RunningRecord } from "@/lib/types";
import TeamLogo from "@/components/TeamLogo";

export default function CardPage() {
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [record, setRecord] = useState<RunningRecord | null>(null);

  useEffect(() => {
    Promise.all([getRecentPredictions(1), getRunningRecord()]).then(
      ([preds, rec]) => {
        setPrediction(preds[0] ?? null);
        setRecord(rec);
      }
    );
  }, []);

  const correct = record?.total_correct ?? 0;
  const incorrect = record?.total_incorrect ?? 0;
  const total = correct + incorrect;
  const accuracy = total > 0 ? ((correct / total) * 100).toFixed(1) : "--";

  const confidence = prediction ? Math.round(prediction.confidence * 100) : null;
  const homeName = prediction ? (TEAM_NAMES[prediction.home_team] ?? prediction.home_team) : null;
  const awayName = prediction ? (TEAM_NAMES[prediction.away_team] ?? prediction.away_team) : null;
  const winnerName = prediction
    ? (TEAM_NAMES[prediction.predicted_team] ?? prediction.predicted_team)
    : null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-bg p-4">
      <div className="w-full max-w-[640px] bg-brand-card border border-brand-border rounded-2xl overflow-hidden">

        {/* Header */}
        <div className="px-6 py-4 border-b border-brand-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-brand-green text-xl">🏀</span>
            <span className="font-black tracking-tight text-white text-base">
              NBA <span className="text-brand-green">PREDICTIONS</span>
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-brand-green" style={{ animation: "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite" }} />
            <span className="text-[10px] text-brand-green tracking-widest uppercase font-bold">LIVE</span>
          </div>
        </div>

        {/* Game + Predicted winner */}
        <div className="grid grid-cols-2 divide-x divide-brand-border border-b border-brand-border">

          {/* Next game */}
          <div className="px-6 py-5">
            <p className="text-[10px] tracking-widest uppercase text-brand-muted mb-4">
              📅 NEXT GAME
            </p>
            {prediction ? (
              <div className="flex items-center gap-4">
                <div className="flex flex-col items-center gap-1.5">
                  <TeamLogo abbrev={prediction.home_team} teamId={prediction.home_team_id} size={44} />
                  <span className="text-xs font-bold text-white tracking-wide uppercase">{homeName}</span>
                </div>
                <span className="text-brand-muted text-xs font-semibold">VS</span>
                <div className="flex flex-col items-center gap-1.5">
                  <TeamLogo abbrev={prediction.away_team} teamId={prediction.away_team_id} size={44} />
                  <span className="text-xs font-bold text-white tracking-wide uppercase">{awayName}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-brand-muted">No upcoming game</p>
            )}
          </div>

          {/* Predicted winner */}
          <div className="px-6 py-5">
            <p className="text-[10px] tracking-widest uppercase text-brand-muted mb-4">
              🏆 PREDICTED WINNER
            </p>
            {prediction ? (
              <>
                <p className="text-2xl font-black text-white tracking-tight leading-none uppercase">
                  {winnerName}
                </p>
                <p className="text-sm text-brand-green font-semibold mt-2">
                  ({confidence}% Confidence)
                </p>
              </>
            ) : (
              <p className="text-sm text-brand-muted">No prediction yet</p>
            )}
          </div>
        </div>

        {/* Running record */}
        <div className="px-6 py-5">
          <p className="text-[10px] tracking-widest uppercase text-brand-muted mb-4">
            📊 RUNNING RECORD
          </p>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="flex items-end gap-1">
                <span className="text-3xl font-black text-brand-green">{correct}</span>
                <span className="text-brand-green text-lg mb-0.5">✓</span>
              </div>
              <p className="text-[10px] text-brand-muted tracking-widest mt-0.5">CORRECT</p>
            </div>
            <div>
              <div className="flex items-end gap-1">
                <span className="text-3xl font-black text-red-400">{incorrect}</span>
                <span className="text-red-400 text-lg mb-0.5">✗</span>
              </div>
              <p className="text-[10px] text-brand-muted tracking-widest mt-0.5">INCORRECT</p>
            </div>
            <div>
              <div className="flex items-end gap-1">
                <span className="text-3xl font-black text-white">{accuracy}%</span>
                <span className="text-brand-green text-lg mb-0.5">🎯</span>
              </div>
              <p className="text-[10px] text-brand-muted tracking-widest mt-0.5">ACCURACY</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
