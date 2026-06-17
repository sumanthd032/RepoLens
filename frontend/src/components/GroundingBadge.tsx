// Circular SVG ring that animates from 0 to the grounding score on mount. Colour encodes the
// verdict so grounding is legible at a glance (and never by colour alone — the % is shown too).

import { useEffect, useState } from "react";

import type { Grounding } from "../lib/types";

const SIZE = 52;
const STROKE = 4;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const VERDICT_COLOR: Record<Grounding["verdict"], string> = {
  high: "var(--color-success)",
  medium: "var(--color-warning)",
  low: "var(--color-danger)",
  none: "var(--text-muted)",
};

export function GroundingBadge({ grounding }: { grounding: Grounding }) {
  const [progress, setProgress] = useState(0);
  const percent = Math.round(grounding.score * 100);
  const color = VERDICT_COLOR[grounding.verdict];

  useEffect(() => {
    // Defer one frame so the transition runs from 0 → score.
    const frame = requestAnimationFrame(() => setProgress(grounding.score));
    return () => cancelAnimationFrame(frame);
  }, [grounding.score]);

  const offset = CIRCUMFERENCE * (1 - progress);

  return (
    <div className="flex items-center gap-3">
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label={`${percent} percent grounded (${grounding.verdict})`}
      >
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--bg-muted)"
          strokeWidth={STROKE}
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={color}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
        />
        <text
          x="50%"
          y="50%"
          dominantBaseline="central"
          textAnchor="middle"
          className="font-mono text-xs font-medium"
          fill="var(--text-primary)"
        >
          {percent}
        </text>
      </svg>
      <div className="text-xs text-text-secondary">
        <div className="font-medium text-text-primary capitalize">{grounding.verdict}</div>
        <div>{percent}% grounded</div>
      </div>
    </div>
  );
}
