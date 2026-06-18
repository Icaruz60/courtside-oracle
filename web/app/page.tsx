import { getRecentPredictions, getRunningRecord, getShapValues } from "@/lib/supabase";
import GameCard from "@/components/GameCard";
import RecordStats from "@/components/RecordStats";
import type { ShapValue } from "@/lib/types";

export const revalidate = 300; // revalidate every 5 minutes

export default async function HomePage() {
  const [predictions, record] = await Promise.all([
    getRecentPredictions(50).catch(() => []),
    getRunningRecord().catch(() => null),
  ]);

  const today = new Date().toISOString().split("T")[0];
  const todaysPredictions  = predictions.filter(p => p.game_date === today);
  const recentPredictions  = predictions.filter(p => p.game_date !== today);

  // Fetch SHAP values for today's games
  const shapMap: Record<string, ShapValue[]> = {};
  await Promise.all(
    todaysPredictions.map(async (p) => {
      try {
        shapMap[p.id] = await getShapValues(p.id);
      } catch {
        shapMap[p.id] = [];
      }
    })
  );

  return (
    <div className="space-y-12">

      {/* Today's predictions */}
      <section>
        <SectionHeader icon="📅" label="TODAY'S PREDICTIONS" />
        {todaysPredictions.length === 0 ? (
          <EmptyState message="No games scheduled today — check back tomorrow." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {todaysPredictions.map(p => (
              <GameCard key={p.id} prediction={p} shap={shapMap[p.id]} />
            ))}
          </div>
        )}
      </section>

      {/* Running record */}
      <section>
        <SectionHeader icon="📊" label="RUNNING RECORD" />
        <div className="bg-brand-card border border-brand-border rounded-2xl px-6 py-5">
          <RecordStats record={record} />
        </div>
      </section>

      {/* Recent predictions */}
      {recentPredictions.length > 0 && (
        <section>
          <SectionHeader icon="🕐" label="RECENT PREDICTIONS" />
          <div className="bg-brand-card border border-brand-border rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border text-brand-muted text-xs tracking-widest uppercase">
                  <th className="text-left px-5 py-3">Date</th>
                  <th className="text-left px-5 py-3">Matchup</th>
                  <th className="text-left px-5 py-3 hidden sm:table-cell">Predicted</th>
                  <th className="text-right px-5 py-3 hidden sm:table-cell">Confidence</th>
                  <th className="text-right px-5 py-3">Result</th>
                </tr>
              </thead>
              <tbody>
                {recentPredictions.map((p, i) => (
                  <tr
                    key={p.id}
                    className={`border-b border-brand-border last:border-0 hover:bg-white/[0.02] transition-colors ${
                      i % 2 === 0 ? "" : "bg-white/[0.01]"
                    }`}
                  >
                    <td className="px-5 py-3 text-brand-muted whitespace-nowrap">
                      {new Date(p.game_date + "T12:00:00").toLocaleDateString("en-US", {
                        month: "short", day: "numeric",
                      })}
                    </td>
                    <td className="px-5 py-3 font-medium">
                      {p.away_team} <span className="text-brand-muted">@</span> {p.home_team}
                    </td>
                    <td className="px-5 py-3 text-brand-green hidden sm:table-cell">
                      {p.predicted_team}
                    </td>
                    <td className="px-5 py-3 text-right text-brand-muted hidden sm:table-cell">
                      {(p.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-5 py-3 text-right">
                      {p.correct === null ? (
                        <span className="text-brand-muted">—</span>
                      ) : p.correct ? (
                        <span className="text-brand-green font-bold">✓</span>
                      ) : (
                        <span className="text-red-400 font-bold">✗</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

    </div>
  );
}

function SectionHeader({ icon, label }: { icon: string; label: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="text-brand-green">{icon}</span>
      <h2 className="text-xs font-bold tracking-[0.2em] text-brand-muted uppercase">
        {label}
      </h2>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="bg-brand-card border border-brand-border rounded-2xl px-6 py-10 text-center text-brand-muted text-sm">
      {message}
    </div>
  );
}
