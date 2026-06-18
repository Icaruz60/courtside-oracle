import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Courtside Oracle — NBA Predictions",
  description: "XGBoost-powered NBA game outcome predictions with player ELO ratings and SHAP explanations.",
  openGraph: {
    title: "Courtside Oracle",
    description: "NBA game predictions powered by machine learning.",
    url: "https://courtside-oracle.gerritvisser.de",
    siteName: "Courtside Oracle",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-brand-bg antialiased" suppressHydrationWarning>
        <nav className="border-b border-brand-border sticky top-0 z-50 bg-brand-bg/90 backdrop-blur-sm">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="text-brand-green text-xl">🏀</span>
              <span className="font-black tracking-tight text-white">
                COURTSIDE <span className="text-brand-green">ORACLE</span>
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" />
              <span className="text-xs text-brand-green font-semibold tracking-widest">LIVE</span>
            </div>
          </div>
        </nav>

        <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
          {children}
        </main>

        <footer className="border-t border-brand-border mt-16">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 flex items-center justify-between text-xs text-brand-muted">
            <span>Courtside Oracle — XGBoost + Player ELO</span>
            <a
              href="https://gerritvisser.de"
              className="hover:text-white transition-colors"
            >
              gerritvisser.de
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
