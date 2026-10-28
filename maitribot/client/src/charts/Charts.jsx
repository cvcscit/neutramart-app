// Zero-dependency SVG charts, generalized from DashboardPanel.jsx's original
// calorie-specific WeeklyCalories component. No chart library exists anywhere in this
// repo -- these follow the same hand-rolled technique rather than introducing one.
//
// Colors are validated palette roles (dataviz skill's reference palette, run through
// scripts/validate_palette.js): single-series charts default to slot-1 blue (#2a78d6,
// already used for "protein" elsewhere); two-series charts (blood pressure) use the
// validated adjacent pair blue/orange (#2a78d6 / #eb6834, ALL CHECKS PASS, light mode).
import React, { useState } from "react";

export const INK_PRIMARY = "#0b0b0b";
export const INK_MUTED = "#898781";
export const BASELINE = "#c3c2b7";
export const SERIES_DEFAULT = "#2a78d6";
export const SERIES_PAIR = ["#2a78d6", "#eb6834"];

// Display formatting only -- geometry/scaling always uses the raw numeric value.
function fmt(v) {
  return Number(v).toFixed(2);
}

// Path for a bar with only the top two corners rounded, sitting on the baseline.
function roundedTop(x, y, w, h, r) {
  r = Math.min(r, h);
  return `M${x},${y + h} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + w - r},${y} Q${x + w},${y} ${x + w},${y + r} L${x + w},${y + h} Z`;
}

/** Bars anchored to a baseline, one rounded-top bar per point, hover reveals the value. */
export function BarChart({ data, color = SERIES_DEFAULT, unit = "", ariaLabel }) {
  const W = 320, H = 150, padL = 8, padB = 22, padT = 18;
  const max = Math.max(1, ...data.map((d) => d.value));
  const bw = (W - padL) / data.length;
  const barW = bw * 0.56;
  const [hover, setHover] = useState(null);
  const scale = (v) => (v / max) * (H - padT - padB);

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}>
      <line x1={0} y1={H - padB} x2={W} y2={H - padB} stroke={BASELINE} strokeWidth="1" />
      {data.map((d, i) => {
        const h = scale(d.value);
        const x = padL + i * bw + (bw - barW) / 2;
        const y = H - padB - h;
        const on = hover === i;
        return (
          <g key={d.label + i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <path d={roundedTop(x, y, barW, h, 4)} fill={color} opacity={hover === null || on ? 1 : 0.5} />
            <text x={x + barW / 2} y={y - 5} textAnchor="middle" fontSize="9"
              fill={INK_PRIMARY} fontWeight={on ? 700 : 500}>
              {on ? `${fmt(d.value)}${unit}` : ""}
            </text>
            <text x={x + barW / 2} y={H - padB + 13} textAnchor="middle" fontSize="9" fill={INK_MUTED}>
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** Shared scale/point math for one or more line series over the same x-axis labels. */
function useLineGeometry(seriesList, labels) {
  const W = 320, H = 150, padL = 8, padR = 8, padB = 22, padT = 18;
  const allValues = seriesList.flatMap((s) => s.points.filter((v) => v != null));
  const max = Math.max(1, ...allValues);
  const min = Math.min(0, ...allValues);
  const range = max - min || 1;
  const n = labels.length;
  const stepX = n > 1 ? (W - padL - padR) / (n - 1) : 0;
  const scaleX = (i) => padL + i * stepX;
  const scaleY = (v) => H - padB - ((v - min) / range) * (H - padT - padB);
  return { W, H, padB, scaleX, scaleY };
}

/** One line + dot markers, with a hover tooltip. For a single metric trend. */
export function LineChart({ data, color = SERIES_DEFAULT, unit = "", ariaLabel }) {
  const labels = data.map((d) => d.label);
  const points = data.map((d) => d.value);
  const { W, H, padB, scaleX, scaleY } = useLineGeometry([{ points }], labels);
  const [hover, setHover] = useState(null);

  const known = data.map((d, i) => (d.value != null ? [i, d.value] : null)).filter(Boolean);
  const path = known.map(([i, v], k) => `${k === 0 ? "M" : "L"}${scaleX(i)},${scaleY(v)}`).join(" ");

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}>
      <line x1={0} y1={H - padB} x2={W} y2={H - padB} stroke={BASELINE} strokeWidth="1" />
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {data.map((d, i) => {
        if (d.value == null) return null;
        // Edge labels anchor inward (start/end) instead of centering, so the first/last
        // date label doesn't clip off the left/right edge of the viewBox.
        const edgeAnchor = i === 0 ? "start" : i === data.length - 1 ? "end" : "middle";
        return (
          <g key={d.label + i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <circle cx={scaleX(i)} cy={scaleY(d.value)} r={hover === i ? 4.5 : 3} fill={color} />
            <text x={scaleX(i)} y={scaleY(d.value) - 8} textAnchor={edgeAnchor} fontSize="9"
              fill={INK_PRIMARY} fontWeight={700} opacity={hover === i ? 1 : 0}>
              {fmt(d.value)}{unit}
            </text>
            <text x={scaleX(i)} y={H - padB + 13} textAnchor={edgeAnchor} fontSize="9" fill={INK_MUTED}>
              {i === 0 || i === data.length - 1 ? d.label : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** Two lines sharing one axis (e.g. systolic/diastolic) -- a legend is required at >=2 series. */
export function MultiLineChart({ series, ariaLabel }) {
  const labels = series[0]?.points.map((_, i) => String(i)) || [];
  const { W, H, padB, scaleX, scaleY } = useLineGeometry(series, labels);

  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}>
        <line x1={0} y1={H - padB} x2={W} y2={H - padB} stroke={BASELINE} strokeWidth="1" />
        {series.map((s) => {
          const known = s.points.map((v, i) => (v != null ? [i, v] : null)).filter(Boolean);
          const path = known.map(([i, v], k) => `${k === 0 ? "M" : "L"}${scaleX(i)},${scaleY(v)}`).join(" ");
          return (
            <g key={s.label}>
              <path d={path} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
              {known.map(([i, v]) => (
                <circle key={i} cx={scaleX(i)} cy={scaleY(v)} r={3} fill={s.color} />
              ))}
            </g>
          );
        })}
      </svg>
      {/* Legend: identity must never rely on color alone. */}
      <div className="chart-legend">
        {series.map((s) => (
          <span key={s.label}><i style={{ background: s.color }} /> {s.label}</span>
        ))}
      </div>
    </div>
  );
}
