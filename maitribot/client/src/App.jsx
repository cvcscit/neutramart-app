import React, { useEffect, useRef, useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { jwtDecode } from "jwt-decode";
import DashboardPanel from "./DashboardPanel.jsx";
import FaceScanModal from "./FaceScanModal.jsx";
import { PENDING_KEY as SENAI_PENDING_KEY } from "./senai_scan/ScanPage.jsx";
import * as api from "./api.js";

const SUGGESTIONS = [
  "📷 Scan a meal",
  "🫀 Scan my vitals",
  "📊 How did I eat this week?",
  "💊 Am I low on any minerals?",
  "💪 How's my protein?",
];

// Vitals metric formatting. heart_rate is a validated wellness estimate; bp/spo2 are
// research/experimental (see backend/agent -- they're always returned with an
// "experimental" flag + disclaimer, which must stay visible here, not be dropped.
function formatMetric(m, unit) {
  if (!m) return { text: "Not available", ok: false };
  if (m.status === "ok") {
    const value = m.sbp != null && m.dbp != null ? `${m.sbp}/${m.dbp} ${unit}` : `${m.spo2 ?? m.heart_rate_bpm} ${unit}`;
    return { text: value, ok: true, experimental: m.experimental, disclaimer: m.disclaimer };
  }
  if (m.status === "unavailable") return { text: "Not available yet", ok: false };
  return { text: m.reason || "Not reliable — please rescan", ok: false };
}

// Extra metrics the Shen.AI scan returns in `extras` (see senai_scan/adapter.js). The
// in-house face_scan_biomarkers pipeline doesn't produce these, so they're rendered only
// when present rather than showing empty tiles on that path.
// [label, key in extras, unit suffix, decimal places]
const EXTRA_METRICS = [
  ["HRV (SDNN)", "hrv_sdnn_ms", "ms", 0],
  ["Breathing Rate", "breathing_rate_bpm", "/min", 0],
  ["Stress Index", "stress_index", "", 1],
];

// Compact always-visible strip under the header showing the most recent scan, so the
// numbers don't scroll away with the chat. Shares formatMetric/EXTRA_METRICS with
// VitalsCard so the two can't drift apart.
function VitalsStrip({ data }) {
  const items = [];

  const hr = formatMetric(data?.heart_rate, "bpm");
  if (hr.ok) items.push(["Heart Rate", hr.text]);
  const bp = formatMetric(data?.bp, "mmHg");
  if (bp.ok) items.push(["Blood Pressure", bp.text]);
  if (data?.source !== "shenai") {
    const spo2 = formatMetric(data?.spo2, "%");
    if (spo2.ok) items.push(["SpO2", spo2.text]);
  }
  for (const [label, key, unit, dp] of EXTRA_METRICS) {
    const v = data?.extras?.[key];
    if (typeof v === "number" && Number.isFinite(v)) {
      items.push([label, `${v.toFixed(dp)}${unit ? ` ${unit}` : ""}`]);
    }
  }

  if (!items.length) return null;

  return (
    <div className="vitals-strip">
      {items.map(([label, value]) => (
        <div key={label} className="vitals-strip-tile">
          <div className="vitals-k">{label}</div>
          <div className="vitals-strip-v">{value}</div>
        </div>
      ))}
    </div>
  );
}

function VitalsCard({ data }) {
  const hr = formatMetric(data?.heart_rate, "bpm");
  const bp = formatMetric(data?.bp, "mmHg");
  const spo2 = formatMetric(data?.spo2, "%");
  // Shen.AI doesn't measure SpO2 at all, so the tile would permanently read "Not
  // available" on those scans. The in-house face_scan_biomarkers pipeline does produce
  // it, so the tile is kept for that path (adapter.js tags Shen.AI results with
  // source: "shenai").
  const rows = [
    ["Heart Rate", hr],
    ["Blood Pressure", bp],
    ...(data?.source === "shenai" ? [] : [["Oxygen (SpO2)", spo2]]),
  ];

  const extras = EXTRA_METRICS.map(([label, key, unit, dp]) => {
    const v = data?.extras?.[key];
    if (typeof v !== "number" || !Number.isFinite(v)) return null;
    return { label, text: `${v.toFixed(dp)}${unit ? ` ${unit}` : ""}` };
  }).filter(Boolean);

  return (
    <div className="card analysis">
      <div className="card-body">
        <div className="card-title">🫀 Vitals Scan</div>
        {/* Column count follows the tile count so hiding SpO2 doesn't leave a gap. */}
        <div className="vitals-grid" style={{ gridTemplateColumns: `repeat(${rows.length}, 1fr)` }}>
          {rows.map(([label, m]) => (
            <div key={label} className="vitals-tile">
              <div className="vitals-k">{label}</div>
              <div className="vitals-v" style={{ color: m.ok ? "var(--green)" : "var(--muted)" }}>{m.text}</div>
              {m.ok && m.experimental && <div className="vitals-disclaimer">{m.disclaimer || "Experimental — not validated"}</div>}
            </div>
          ))}
        </div>

        {extras.length > 0 && (
          <div className="vitals-grid vitals-grid-extra">
            {extras.map((m) => (
              <div key={m.label} className="vitals-tile">
                <div className="vitals-k">{m.label}</div>
                <div className="vitals-v" style={{ color: "var(--green)" }}>{m.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Must stay unique across reloads: messages are restored from sessionStorage, so a counter
// that restarts at 0 would hand out keys that collide with restored ones.
let idc = 0;
const uid = () => `m${Date.now().toString(36)}-${(++idc).toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

class MessageBoundary extends React.Component {
  constructor(props) { super(props); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(err) { console.error("[nutrasmart] message render failed:", err); }
  render() {
    if (this.state.failed) return <div className="bubble assistant">⚠️ Couldn't display this result.</div>;
    return this.props.children;
  }
}
const mdBold = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

const _show = (v) => v !== undefined && v !== null && v !== "" && v !== "N/A";

// Format the backend analysis into a readable bot reply (always renders as text).
function formatAnalysis(d) {
  if (!d) return "⚠️ Empty response from server.";
  const noFood = !_show(d.description) || /no food/i.test(String(d.description)) || !_show(d.calories);
  if (noFood) {
    return `🤔 **I couldn't find food in that photo.**\n${_show(d.recommendation) ? d.recommendation : "Try a clear, well-lit shot with the food filling the frame."}`;
  }
  const L = [];
  L.push(`🍽️ **${d.description}**`);
  L.push(`\n🔥 **${d.calories}**${_show(d.weight) ? `  ·  ${d.weight}` : ""}`);
  const macros = [
    _show(d.protein) && `Protein ${d.protein}`,
    _show(d.carbs) && `Carbs ${d.carbs}`,
    _show(d.fat) && `Fat ${d.fat}`,
    _show(d.fiber) && `Fiber ${d.fiber}`,
    _show(d.sugar) && `Sugar ${d.sugar}`,
  ].filter(Boolean);
  if (macros.length) L.push(`\n**Macros:** ${macros.join("  ·  ")}`);
  const dishes = Array.isArray(d.dishes) ? d.dishes : [];
  if (dishes.length) {
    L.push(`\n**Items detected (${dishes.length}):**`);
    dishes.forEach((x) => L.push(`• ${x.name}${_show(x.servingSize) ? ` (${x.servingSize})` : ""}${_show(x.calories) ? ` — ${x.calories} kcal` : ""}`));
  }
  const micros = Object.entries(d.micronutrients || {}).filter(([, v]) => _show(v));
  if (micros.length) L.push(`\n**Micronutrients:** ${micros.map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join("  ·  ")}`);
  if (_show(d.recommendation)) L.push(`\n💡 ${d.recommendation}`);
  return L.join("\n");
}

function TypingDots() {
  return <div className="bubble assistant typing"><span></span><span></span><span></span></div>;
}

// Render whatever the backend sends. Field names mirror the API exactly:
// description, weight, calories, protein, carbs, fat, fiber, sugar,
// dishes[{name,servingSize,calories,...}], objects[], micronutrients{...},
// summary, recommendation.
const show = (v) => v !== undefined && v !== null && v !== "" && v !== "N/A";
const num = (v) => { const m = String(v ?? "").match(/[\d.]+/); return m ? parseFloat(m[0]) : 0; };
const MICRO_LABELS = {
  vitamin_a: "Vitamin A", vitamin_c: "Vitamin C", vitamin_d: "Vitamin D", vitamin_b12: "Vitamin B12",
  iron: "Iron", calcium: "Calcium", potassium: "Potassium", sodium: "Sodium", zinc: "Zinc", magnesium: "Magnesium",
};

function AnalysisCard({ data, thumb, region }) {
  const d = data || {};
  const noFood = !show(d.description) || /no food/i.test(String(d.description)) || !show(d.calories);

  if (noFood) {
    return (
      <div className="card analysis">
        {thumb && <img className="card-thumb" src={thumb} alt="meal" />}
        <div className="card-body">
          <div className="card-title">🤔 Couldn't read this photo clearly</div>
          <div className="reco">{show(d.recommendation) ? d.recommendation : "Try a well-lit shot with the food filling the frame."}</div>
          {region && <div className="region-badge">🔒 {region.region}</div>}
        </div>
      </div>
    );
  }

  const p = num(d.protein), c = num(d.carbs), f = num(d.fat);
  const total = p + c + f || 1;
  const macros = [
    { label: "Protein", g: p, color: "#2a78d6" },
    { label: "Carbs", g: c, color: "#eb6834" },
    { label: "Fat", g: f, color: "#1baf7a" },
  ];
  const extra = [{ label: "Fiber", val: d.fiber }, { label: "Sugar", val: d.sugar }].filter((m) => show(m.val));
  const micros = Object.entries(d.micronutrients || {}).filter(([, v]) => show(v));
  const dishes = Array.isArray(d.dishes) ? d.dishes : [];

  return (
    <div className="card analysis">
      {thumb && <img className="card-thumb" src={thumb} alt="meal" />}
      <div className="card-body">
        <div className="card-title">{d.description}</div>

        <div className="hero">
          <div className="hero-cal">
            <span className="hero-num">{num(d.calories) || d.calories}</span>
            <span className="hero-unit">kcal</span>
          </div>
          {show(d.weight) && <div className="hero-weight">{d.weight}</div>}
        </div>

        <div className="macrobar">
          {macros.map((m) => m.g > 0 && (
            <span key={m.label} style={{ width: `${(m.g / total) * 100}%`, background: m.color }} title={`${m.label} ${m.g}g`} />
          ))}
        </div>
        <div className="macro-legend2">
          {macros.map((m) => (
            <span key={m.label}><i style={{ background: m.color }} />{m.label} <b>{m.g}g</b></span>
          ))}
          {extra.map((m) => (<span key={m.label} className="mm">{m.label} <b>{m.val}</b></span>))}
        </div>

        {dishes.length > 0 && (
          <div className="section">
            <div className="section-h">{dishes.length} items detected</div>
            <div className="dish-list">
              {dishes.map((dish, i) => (
                <div key={i} className="dish2">
                  <div className="dish2-main">
                    <span className="dish2-name">{dish.name}</span>
                    {show(dish.servingSize) && <span className="dish2-serve">{dish.servingSize}</span>}
                  </div>
                  {show(dish.calories) && <span className="dish2-cal">{dish.calories} kcal</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {micros.length > 0 && (
          <div className="section">
            <div className="section-h">Micronutrients</div>
            <div className="micro-grid">
              {micros.map(([k, v]) => (
                <div key={k} className="micro-tile">
                  <div className="micro-v">{v}</div>
                  <div className="micro-k">{MICRO_LABELS[k] || k.replace(/_/g, " ")}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {show(d.summary) && <div className="summary">{d.summary}</div>}
        {show(d.recommendation) && <div className="reco">💡 {d.recommendation}</div>}
        {region && <div className="region-badge">🔒 {region.region}</div>}
      </div>
    </div>
  );
}

function Bubble({ m }) {
  if (m.type === "raw") {
    return (
      <div className="raw-bubble">
        <div className="raw-label">🧾 Backend response{m.label ? ` (${m.label})` : ""}:</div>
        <pre>{typeof m.data === "string" ? m.data : JSON.stringify(m.data, null, 2)}</pre>
      </div>
    );
  }
  if (m.type === "analysis") return <AnalysisCard data={m.data} thumb={m.thumb} region={m.region} />;
  if (m.type === "vitals") return <VitalsCard data={m.data} />;
  return (
    <div className={`bubble ${m.role}`}>
      {m.thumb && <img className="bubble-thumb" src={m.thumb} alt="upload" />}
      {m.text && <span dangerouslySetInnerHTML={{ __html: mdBold(m.text) }} />}
    </div>
  );
}

function LoginGate({ onSuccess }) {
  return (
    <div className="login-gate">
      <div className="logo big">🥗</div>
      <h1>W360</h1>
      <p>Snap a meal, scan your vitals, and chat with an AI coach that remembers what you ate — sign in to get started.</p>
      <GoogleLogin onSuccess={onSuccess} onError={() => alert("Google sign-in failed")} />
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(() => {
    const t = localStorage.getItem("auth_token");
    if (!t) return null;
    try {
      const d = jwtDecode(t);
      if (d.exp * 1000 < Date.now()) { localStorage.removeItem("auth_token"); return null; }
      return { email: d.email, firstName: d.given_name, picture: d.picture };
    } catch { return null; }
  });
  const [messages, setMessages] = useState(() => {
    // Restore the conversation (incl. scan results) across refreshes -- otherwise a
    // page reload silently throws away a result the user just got back from the backend.
    try {
      const saved = JSON.parse(sessionStorage.getItem("nutrasmart_messages") || "null");
      // Re-key on restore: older saves used a counter that restarted every reload.
      if (Array.isArray(saved) && saved.length) return saved.map((m) => ({ ...m, id: uid() }));
    } catch {}
    return [
      { id: uid(), role: "assistant", text: "Hey! 👋 I'm W360. Snap a photo of your meal or ask me anything about your nutrition." },
    ];
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [dash, setDash] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const fileRef = useRef(null);
  const endRef = useRef(null);

  // Most recent scan, derived from the thread rather than kept in its own state: messages
  // already persist to sessionStorage, so the pinned strip survives a reload for free.
  const latestVitals = [...messages].reverse().find((m) => m.type === "vitals")?.data;

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  // The Shen.AI scan runs on its own isolated page (/scan.html) and hands the result back
  // through sessionStorage, since it can't live in this document (see senai_scan/README).
  useEffect(() => {
    let pending = null;
    try {
      const raw = sessionStorage.getItem(SENAI_PENDING_KEY);
      if (raw) {
        pending = JSON.parse(raw);
        sessionStorage.removeItem(SENAI_PENDING_KEY); // one-shot: don't replay on reload
      }
    } catch {}
    if (pending) add({ role: "assistant", type: "vitals", data: pending });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    try {
      // Drop blob: thumb URLs before persisting -- they're invalidated on reload anyway.
      const persistable = messages.map(({ thumb, ...rest }) => rest);
      sessionStorage.setItem("nutrasmart_messages", JSON.stringify(persistable));
    } catch {}
  }, [messages]);

  const add = (m) => setMessages((prev) => [...prev, { id: uid(), ...m }]);

  function onLogin(cred) {
    const token = cred.credential;
    localStorage.setItem("auth_token", token);
    const d = jwtDecode(token);
    setUser({ email: d.email, firstName: d.given_name, picture: d.picture });
  }
  function logout() { localStorage.removeItem("auth_token"); setUser(null); }

  async function sendText(text) {
    if (!text.trim() || busy) return;
    add({ role: "user", text });
    setInput("");
    setBusy(true);
    try {
      // Bedrock requires the conversation to start with a user turn — drop the
      // greeting / any leading assistant messages, keep only text turns.
      const convo = messages.filter((m) => m.text && (m.role === "user" || m.role === "assistant"));
      const firstUser = convo.findIndex((m) => m.role === "user");
      const history = firstUser === -1 ? [] : convo.slice(firstUser).map((m) => ({ role: m.role, content: m.text }));
      const d = await api.chat(text, history);
      add({ role: "assistant", text: d.reply || "…" });
    } catch (e) {
      add({ role: "assistant", text: `⚠️ ${e.message}` });
    } finally { setBusy(false); }
  }

  async function sendImage(file) {
    if (!file || busy) return;
    const thumb = URL.createObjectURL(file);
    add({ role: "user", thumb, text: "" });
    setBusy(true);
    try {
      // 1) presign against the user's REGIONAL bucket
      const { url, key } = await api.presign(file.name, file.type, user.email);
      const region = api.regionFromPresign(url);
      // 2) browser uploads the image bytes straight to regional S3
      await api.putToS3(url, file);
      // 3) regional agent analyzes it (real Bedrock) and returns nutrition
      const data = await api.analyze([{ key, content_type: file.type }]);
      add({ role: "assistant", text: formatAnalysis(data) });
    } catch (e) {
      add({ role: "assistant", text: `⚠️ ${e.message}` });
    } finally { setBusy(false); }
  }

  function onSuggestion(s) {
    if (s.startsWith("📷")) { fileRef.current?.click(); return; }
    // Routes to the Shen.AI scan page. (Was setScanOpen(true) for the in-house scan,
    // which is still wired up below — see the note by the composer buttons.)
    if (s.startsWith("🫀")) { window.location.href = "/scan.html"; return; }
    sendText(s.replace(/^\p{Emoji}\s*/u, ""));
  }

  function handleScanResult(data) {
    setScanOpen(false);
    add({ role: "assistant", type: "vitals", data });
  }

  if (!user) return <LoginGate onSuccess={onLogin} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">🥗</span>
          <div>
            <div className="brand-name">W360</div>
            <div className="brand-sub">Hi {user.firstName || user.email}</div>
          </div>
        </div>
        <div className="top-actions">
          <button className="dash-btn" onClick={() => setDash(true)}>📊 My stats</button>
          <button className="dash-btn" onClick={logout}>Sign out</button>
        </div>
      </header>

      {latestVitals && <VitalsStrip data={latestVitals} />}

      <main className="thread">
        {messages.map((m) => <MessageBoundary key={m.id}><Bubble m={m} /></MessageBoundary>)}
        {busy && <TypingDots />}
        <div ref={endRef} />
      </main>

      {messages.length <= 1 && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => <button key={s} className="suggestion" onClick={() => onSuggestion(s)}>{s}</button>)}
        </div>
      )}

      <form className="composer" onSubmit={(e) => { e.preventDefault(); sendText(input); }}>
        <button type="button" className="icon-btn" title="Attach photo" onClick={() => fileRef.current?.click()}>📷</button>
        {/* The in-house FaceScanModal path is fully wired and intact below, just with no
            visible trigger — to bring it back, re-add:
            <button className="icon-btn" title="Scan vitals" onClick={() => setScanOpen(true)}>🫀</button> */}
        <button type="button" className="icon-btn" title="Scan vitals (on-device)"
          onClick={() => { window.location.href = "/scan.html"; }}>🩺</button>
        <input ref={fileRef} type="file" accept="image/*" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) sendImage(f); e.target.value = ""; }} />
        <input className="text-input" placeholder="Message W360…" value={input}
          onChange={(e) => setInput(e.target.value)} disabled={busy} />
        <button className="send-btn" disabled={busy || !input.trim()}>↑</button>
      </form>

      {dash && <DashboardPanel onClose={() => setDash(false)} />}
      {scanOpen && (
        <FaceScanModal
          email={user.email}
          onClose={() => setScanOpen(false)}
          onResult={handleScanResult}
        />
      )}
    </div>
  );
}
