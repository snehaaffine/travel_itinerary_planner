import type { ReactNode } from "react";
import { STEPS } from "../data";
import type { Step } from "../types";

function ProgressBar({ step }: { step: Step }) {
  const idx = Math.max(0, STEPS.indexOf(step as (typeof STEPS)[number]));
  const activeIdx = step === "feedback" ? STEPS.length - 1 : idx;
  return (
    <div className="flex items-center justify-center mb-8" style={{ gap: 15 }}>
      {STEPS.map((s, i) => (
        <div
          key={s}
          className="transition-all duration-300"
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: i <= activeIdx ? "#f5edd8" : "rgba(30,45,74,0.12)",
          }}
        />
      ))}
    </div>
  );
}

export function Screen({
  children,
  title,
  subtitle,
  step,
  onBack,
  onNext,
  nextLabel,
  nextDisabled,
  wide,
}: {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  step: Step;
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  wide?: boolean;
}) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
      <div className="flex items-center justify-between px-6 pt-8 pb-4">
        {onBack ? (
          <button
            onClick={onBack}
            className="w-10 h-10 rounded-full flex items-center justify-center transition-colors"
            style={{ background: "var(--surface)", color: "var(--cream)" }}
          >
            ←
          </button>
        ) : (
          <div className="w-10" />
        )}
        <span
          style={{
            fontFamily: "Fraunces, serif",
            color: "#333d29",
            fontSize: 32,
            fontWeight: 700,
            letterSpacing: "-0.02em",
            lineHeight: 1,
          }}
        >
          Wandr
        </span>
        <div className="w-10" />
      </div>

      <ProgressBar step={step} />

      <div className={`flex-1 overflow-visible px-6 pb-4 ${wide ? "max-w-4xl mx-auto w-full" : ""}`}>
        {(title || subtitle) && (
          <div className="mb-7 fade-up">
            {title && (
              <h1
                style={{
                  fontFamily: "Fraunces, serif",
                  fontSize: "clamp(26px, 5vw, 34px)",
                  fontWeight: 700,
                  color: "#1e2d4a",
                  lineHeight: 1.15,
                  marginBottom: 8,
                }}
              >
                {title}
              </h1>
            )}
            {subtitle && (
              <p style={{ color: "var(--cream-muted)", fontSize: 15, fontFamily: "Outfit, sans-serif" }}>
                {subtitle}
              </p>
            )}
          </div>
        )}
        {children}
      </div>

      {onNext && (
        <div className="px-6 py-6" style={{ borderTop: "1px solid var(--border)" }}>
          <button
            onClick={onNext}
            disabled={nextDisabled}
            className="w-full py-4 rounded-2xl font-semibold text-base transition-all duration-200"
            style={{
              background: nextDisabled ? "rgba(51,61,41,0.15)" : "#333d29",
              color: nextDisabled ? "rgba(30,45,74,0.35)" : "#ffffff",
              fontFamily: "Outfit, sans-serif",
              cursor: nextDisabled ? "not-allowed" : "pointer",
              boxShadow: nextDisabled ? "none" : "0 4px 20px rgba(51,61,41,0.3)",
            }}
          >
            {nextLabel ?? "Continue"}
          </button>
        </div>
      )}
    </div>
  );
}
