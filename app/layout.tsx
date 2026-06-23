import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LLM Eval Observatory",
  description:
    "A living dashboard that measures open-source LLMs every night — capability drift, prompt-injection robustness, and LLM-as-judge bias. Every number is computed by a scheduled GitHub Action, not hand-typed.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
