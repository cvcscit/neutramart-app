import React, { useEffect, useState } from "react";
import * as api from "./api.js";
import { BarChart, LineChart, MultiLineChart, SERIES_PAIR } from "./charts/Charts.jsx";

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// Validated palette roles (from the data-viz skill's reference palette).
const SERIES = "#008300";        // single-series magnitude (calories) — brand green
const MACRO = { protein: "#2a78d6", carbs: "#eb6834", fat: "#1baf7a" }; // 3 categorical slots

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
        <span><i style={{ background: MACRO.protein }} /> Protein {macros.protein.toFixed(2)}g</span>
        <span><i style={{ background: MACRO.carbs }} /> Carbs {macros.carbs.toFixed(2)}g</span>
        <span><i style={{ background: MACRO.fat }} /> Fat {macros.fat.toFixed(2)}g</span>
      </div>
    </div>
  );
}

// Bucket label for the x-axis: daily buckets show a weekday name; weekly/monthly/yearly
// buckets show the bucket's start date (meals.py returns week_start/month_start as the
// `date` field regardless of period, so this is always safe to read off `r.date`).
function nutritionBucketLabel(period, dateStr) {
  if (period === "daily") return DOW[new Date(dateStr + "T00:00:00Z").getUTCDay()];
  return (dateStr || "").slice(5); // "MM-DD"
}

function NutritionTab({ period, range }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null);
    api.getNutritionSummary(period, range)
      .then((res) => {
        const rows = (res.data || []).slice(-7);
        const week = rows.map((r) => ({
          day: nutritionBucketLabel(period, r.date),
          calories: r.total_calories || 0,
        }));
        const last = rows[rows.length - 1] || {};
        const macros = {
          protein: last.total_protein || 0,
          carbs: last.total_carbs || 0,
          fat: last.total_fat || 0,
        };
        setData({ week, macros, streak: rows.length });
      })
      .catch((e) => setErr(e.message));
  }, [period, range.startDate, range.endDate]);

  const hasWeek = data && data.week.length > 0;
  const avg = hasWeek ? data.week.reduce((a, d) => a + d.calories, 0) / data.week.length : null;
  const avgLabel = period === "daily" ? "avg kcal/day" : period === "weekly" ? "avg kcal/week" : "avg kcal/month";

  return (
    <>
      <div className="tiles">
        <div className="tile">
          <div className="tile-val">{avg != null ? avg.toFixed(2) : "—"}</div>
          <div className="tile-label">{avgLabel}</div>
        </div>
        <div className="tile">
          <div className="tile-val">{data ? data.macros.protein.toFixed(2) : "—"}g</div>
          <div className="tile-label">avg protein</div>
        </div>
        <div className="tile">
          <div className="tile-val">🔥 {data ? data.streak : "—"}</div>
          <div className="tile-label">{period} points</div>
        </div>
      </div>

      <section className="panel-section">
        <h3>Calories · recent {period}</h3>
        {err && <div className="muted-note">Couldn't load stats: {err}</div>}
        {!err && !data && <div className="muted-note">Loading…</div>}
        {hasWeek
          ? <BarChart data={data.week.map((d) => ({ label: d.day, value: d.calories }))}
              color={SERIES} ariaLabel={`Calories per ${period} period`} />
          : (data && <div className="muted-note">No meals logged in this range — scan a meal to get started.</div>)}
      </section>

      {hasWeek && (
        <section className="panel-section">
          <h3>Latest period · macros</h3>
          <MacroBar macros={data.macros} />
        </section>
      )}
    </>
  );
}

// Vitals timestamps are "YYYYMMDDTHHMMSSZ" -- format as a short day/time label for chart axes.
export function formatVitalsLabel(ts) {
  if (!ts || ts.length < 15) return "";
  const d = new Date(`${ts.slice(0, 4)}-${ts.slice(4, 6)}-${ts.slice(6, 8)}T${ts.slice(9, 11)}:${ts.slice(11, 13)}:00Z`);
  if (isNaN(d)) return "";
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
}

// Vitals have no natural "bucket" (each scan is a point reading, nothing to sum), so
// period here is just a date-range shortcut -- weekly = last 7 days, monthly = last 30 --
// applied server-side via startDate/endDate. An explicit custom range always wins.
function periodToVitalsRange(period) {
  const end = new Date();
  const start = new Date(end);
  const days = period === "daily" ? 1 : period === "weekly" ? 7 : 30;
  start.setUTCDate(start.getUTCDate() - days);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return { startDate: fmt(start), endDate: fmt(end) };
}

function VitalsTab({ period, range }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const effectiveRange = range.startDate && range.endDate ? range : periodToVitalsRange(period);

  useEffect(() => {
    setData(null);
    api.getVitalsSummary({ ...effectiveRange, limit: 60 })
      .then((res) => setData(res.data || []))
      .catch((e) => setErr(e.message));
  }, [period, range.startDate, range.endDate]);

  if (err) return <div className="muted-note">Couldn't load vitals: {err}</div>;
  if (!data) return <div className="muted-note">Loading…</div>;
  if (data.length === 0) {
    return <div className="muted-note">No vitals scans in this range — try the 🩺 scan.</div>;
  }

  const recent = data.slice(-14);
  const latest = recent[recent.length - 1];
  const hrPoints = recent.filter((d) => d.heart_rate_bpm != null);
  const bpPoints = recent.filter((d) => d.systolic != null && d.diastolic != null);

  return (
    <>
      <div className="tiles">
        <div className="tile">
          <div className="tile-val">{latest.heart_rate_bpm != null ? latest.heart_rate_bpm.toFixed(2) : "—"}</div>
          <div className="tile-label">latest bpm</div>
        </div>
        <div className="tile">
          <div className="tile-val">{latest.hrv_sdnn_ms != null ? latest.hrv_sdnn_ms.toFixed(2) : "—"}</div>
          <div className="tile-label">latest HRV (ms)</div>
        </div>
        <div className="tile">
          <div className="tile-val">{latest.stress_index != null ? latest.stress_index.toFixed(2) : "—"}</div>
          <div className="tile-label">stress index</div>
        </div>
      </div>

      <section className="panel-section">
        <h3>Heart rate · recent scans</h3>
        {hrPoints.length > 0
          ? <LineChart
              data={hrPoints.map((d) => ({ label: formatVitalsLabel(d.date), value: d.heart_rate_bpm }))}
              unit=" bpm" ariaLabel="Heart rate over recent scans" />
          : <div className="muted-note">No heart-rate readings in recent scans.</div>}
      </section>

      <section className="panel-section">
        <h3>Blood pressure · recent scans</h3>
        {bpPoints.length > 0
          ? <MultiLineChart
              ariaLabel="Blood pressure over recent scans"
              series={[
                { label: "Systolic", color: SERIES_PAIR[0], points: bpPoints.map((d) => d.systolic) },
                { label: "Diastolic", color: SERIES_PAIR[1], points: bpPoints.map((d) => d.diastolic) },
              ]}
            />
          : <div className="muted-note">No blood-pressure readings in recent scans.</div>}
        <div className="muted-note" style={{ borderTop: "none", paddingTop: 6 }}>
          Wellness estimates — not a medical measurement.
        </div>
      </section>
    </>
  );
}

const PERIODS = ["daily", "weekly", "monthly"];

// Shared by both tabs: Daily/Weekly/Monthly pills, plus a "Custom" pill that reveals a
// From/To date-range pair. A set custom range always takes priority over the period pill
// (both tabs' effective-range logic checks range.startDate/endDate first).
function RangeControls({ period, setPeriod, range, setRange }) {
  const customActive = !!(range.startDate || range.endDate);

  return (
    <div className="range-controls">
      <div className="panel-tabs">
        {PERIODS.map((p) => (
          <button key={p} className={`panel-tab ${period === p && !customActive ? "active" : ""}`}
            onClick={() => { setRange({ startDate: "", endDate: "" }); setPeriod(p); }}>
            {p[0].toUpperCase() + p.slice(1)}
          </button>
        ))}
        <button className={`panel-tab ${customActive ? "active" : ""}`}
          onClick={() => setRange((r) => (customActive ? { startDate: "", endDate: "" } : { ...r, startDate: r.startDate || isoDaysAgo(7), endDate: r.endDate || isoDaysAgo(0) }))}>
          📅 Custom
        </button>
      </div>
      {customActive && (
        <div className="date-range-row">
          <input type="date" value={range.startDate}
            onChange={(e) => setRange((r) => ({ ...r, startDate: e.target.value }))} />
          <span>to</span>
          <input type="date" value={range.endDate}
            onChange={(e) => setRange((r) => ({ ...r, endDate: e.target.value }))} />
        </div>
      )}
    </div>
  );
}

function isoDaysAgo(days) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function DashboardPanel({ onClose }) {
  const [tab, setTab] = useState("nutrition");
  const [period, setPeriod] = useState("daily");
  const [range, setRange] = useState({ startDate: "", endDate: "" });

  return (
    <div className="drawer-scrim" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Your stats</h2>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        <div className="panel-tabs">
          <button className={`panel-tab ${tab === "nutrition" ? "active" : ""}`} onClick={() => setTab("nutrition")}>
            🍽️ Nutrition
          </button>
          <button className={`panel-tab ${tab === "vitals" ? "active" : ""}`} onClick={() => setTab("vitals")}>
            🫀 Vitals
          </button>
        </div>

        <RangeControls period={period} setPeriod={setPeriod} range={range} setRange={setRange} />

        {tab === "nutrition" ? <NutritionTab period={period} range={range} /> : <VitalsTab period={period} range={range} />}
      </aside>
    </div>
  );
}
