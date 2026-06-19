import { getRunningRecord } from "@/lib/supabase";

export const revalidate = 300;

export default async function CardPage() {
  const record = await getRunningRecord().catch(() => null);

  const correct   = record?.total_correct   ?? 0;
  const incorrect = record?.total_incorrect ?? 0;
  const total     = correct + incorrect;
  const accuracy  = total > 0
    ? ((correct / total) * 100).toFixed(1)
    : null;

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-transparent">
      <div className="w-full max-w-[420px] bg-brand-card border border-brand-border rounded-2xl overflow-hidden">

        {/* Header */}
        <div className="px-5 pt-5 pb-4 border-b border-brand-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-brand-green text-lg">🏀</span>
            <span className="font-black tracking-tight text-white text-sm">
              COURTSIDE <span className="text-brand-green">ORACLE</span>
            </span>
          </div>
          <span className="text-[10px] text-brand-muted tracking-widest uppercase">
            NBA Predictions
          </span>
        </div>

        {/* Record */}
        <div className="px-5 py-5">
          <p className="text-[10px] tracking-widest uppercase text-brand-muted mb-3">
            Season Record
          </p>
          <div className="flex items-end gap-6">
            <div>
              <span className="text-4xl font-black text-brand-green">{correct}</span>
              <span className="text-brand-green text-xl ml-1">✓</span>
              <p className="text-[10px] text-brand-muted tracking-widest mt-0.5">CORRECT</p>
            </div>
            <div>
              <span className="text-4xl font-black text-red-400">{incorrect}</span>
              <span className="text-red-400 text-xl ml-1">✗</span>
              <p className="text-[10px] text-brand-muted tracking-widest mt-0.5">WRONG</p>
            </div>
            {accuracy && (
              <div className="ml-auto text-right">
                <span className="text-4xl font-black text-white">{accuracy}%</span>
                <p className="text-[10px] text-brand-muted tracking-widest mt-0.5">ACCURACY</p>
              </div>
            )}
          </div>
        </div>

        {/* Description */}
        <div className="px-5 pb-4 text-xs text-brand-muted leading-relaxed">
          XGBoost binary classifier trained on 14,108 NBA games with player ELO ratings
          across 7 skill dimensions. Daily predictions with SHAP explainability.
        </div>

        {/* Tech tags + link */}
        <div className="px-5 pb-5 flex items-center justify-between">
          <div className="flex gap-1.5 flex-wrap">
            {["XGBoost", "Player ELO", "SHAP", "Next.js"].map(tag => (
              <span
                key={tag}
                className="text-[10px] text-brand-muted border border-brand-border rounded-full px-2 py-0.5"
              >
                {tag}
              </span>
            ))}
          </div>
          <a
            href="https://courtside-oracle.gerritvisser.de"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-brand-green hover:underline shrink-0 ml-3"
          >
            View live →
          </a>
        </div>

      </div>
    </div>
  );
}
