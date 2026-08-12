import React, { useEffect, useState } from "react";
import * as api from "./api.js";

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// Validated palette roles (from the data-viz skill's reference palette).
const INK_PRIMARY = "#0b0b0b";
const INK_MUTED = "#898781";
const BASELINE = "#c3c2b7";
const SERIES = "#008300";        // single-series magnitude (calories) — brand green
const MACRO = { protein: "#2a78d6", carbs: "#eb6834", fat: "#1baf7a" }; // 3 categorical slots

function WeeklyCalories({ week }) {
  const W = 320, H = 150, padL = 8, padB = 22, padT = 18;
  const max = Math.max(...week.map((d) => d.calories));
  const bw = (W - padL) / week.length;
  const barW = bw * 0.56;
  const [hover, setHover] = useState(null);
  const scale = (v) => (v / max) * (H - padT - padB);

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Calories per day this week">
      {/* baseline */}
      <line x1={0} y1={H - padB} x2={W} y2={H - padB} stroke={BASELINE} strokeWidth="1" />
      {week.map((d, i) => {
        const h = scale(d.calories);
        const x = padL + i * bw + (bw - barW) / 2;
        const y = H - padB - h;
        const on = hover === i;
        return (
          <g key={d.day} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            {/* rounded-top bar anchored to baseline */}
            <path
              d={roundedTop(x, y, barW, h, 4)}
              fill={SERIES} opacity={hover === null || on ? 1 : 0.5}
            />
            {/* selective direct label */}
            <text x={x + barW / 2} y={y - 5} textAnchor="middle" fontSize="9"
              fill={INK_PRIMARY} fontWeight={on ? 700 : 500}>
              {on ? d.calories : ""}
            </text>
            <text x={x + barW / 2} y={H - padB + 13} textAnchor="middle" fontSize="9" fill={INK_MUTED}>
              {d.day}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// path for a bar with only the top two corners rounded, sitting on the baseline
function roundedTop(x, y, w, h, r) {
  r = Math.min(r, h);
  return `M${x},${y + h} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + w - r},${y} Q${x + w},${y} ${x + w},${y + r} L${x + w},${y + h} Z`;
}

function MacroBar({ macros }) {
  const total = macros.protein + macros.carbs + macros.fat;
  const seg = (v) => `${(v / total) * 100}%`;
  return (
    <div>
      <div className="macro-bar">
        <span style={{ width: seg(macros.protein), background: MACRO.protein }} />
        <span style={{ width: seg(macros.carbs), background: MACRO.carbs }} />
        <span style={{ width: seg(macros.fat), background: MACRO.fat }} />
      </div>
      <div className="macro-legend">
        <span><i style={{ background: MACRO.protein }} /> Protein {macros.protein}g</span>
        <span><i style={{ background: MACRO.carbs }} /> Carbs {macros.carbs}g</span>
        <span><i style={{ background: MACRO.fat }} /> Fat {macros.fat}g</span>
      </div>
    </div>
  );
}

export default function DashboardPanel({ onClose }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.getNutritionSummary("daily")
      .then((res) => {
        const rows = (res.data || []).slice(-7);
        const week = rows.map((r) => ({
          day: DOW[new Date(r.date + "T00:00:00Z").getUTCDay()],
          calories: Math.round(r.total_calories || 0),
        }));
        const last = rows[rows.length - 1] || {};
        const macros = {
          protein: Math.round(last.total_protein || 0),
          carbs: Math.round(last.total_carbs || 0),
          fat: Math.round(last.total_fat || 0),
        };
        setData({ week, macros, streak: rows.length });
      })
      .catch((e) => setErr(e.message));
  }, []);

  const hasWeek = data && data.week.length > 0;
  const avg = hasWeek ? Math.round(data.week.reduce((a, d) => a + d.calories, 0) / data.week.length) : "—";

  return (
    <div className="drawer-scrim" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Your stats</h2>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        <div className="tiles">
          <div className="tile">
            <div className="tile-val">{avg}</div>
            <div className="tile-label">avg kcal/day</div>
          </div>
          <div className="tile">
            <div className="tile-val">{data ? data.macros.protein : "—"}g</div>
            <div className="tile-label">avg protein</div>
          </div>
          <div className="tile">
            <div className="tile-val">🔥 {data ? data.streak : "—"}</div>
            <div className="tile-label">day streak</div>
          </div>
        </div>

        <section className="panel-section">
          <h3>Calories · recent days</h3>
          {err && <div className="muted-note">Couldn't load stats: {err}</div>}
          {!err && !data && <div className="muted-note">Loading…</div>}
          {hasWeek ? <WeeklyCalories week={data.week} />
            : (data && <div className="muted-note">No meals logged yet — scan a meal to get started.</div>)}
        </section>

        {hasWeek && (
          <section className="panel-section">
            <h3>Latest day · macros</h3>
            <MacroBar macros={data.macros} />
          </section>
        )}

        <section className="panel-section muted-note">
          🔒 Live data from your region's bucket via the existing NutraSmart backend.
        </section>
      </aside>
    </div>
  );
}
