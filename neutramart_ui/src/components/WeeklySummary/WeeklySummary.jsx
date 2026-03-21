import { useState, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { getWeeklySummary } from "../../services/api";
import "./WeeklySummary.css";

export default function WeeklySummary({ refreshTrigger }) {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getWeeklySummary(token)
      .then((data) => setSummary(data.summary))
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [token, refreshTrigger]);

  if (loading) {
    return (
      <div className="weekly-card">
        <div className="weekly-header">
          <h3 className="weekly-title">7-Day Eating Summary</h3>
        </div>
        <div className="weekly-loading">
          <span className="weekly-spinner" />
          <p>Loading summary...</p>
        </div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="weekly-card">
      <div className="weekly-header" onClick={() => setExpanded(!expanded)}>
        <h3 className="weekly-title">7-Day Eating Summary</h3>
        <button className="weekly-toggle">{expanded ? "Hide" : "Show"}</button>
      </div>
      {expanded && (
        <div className="weekly-body">
          {summary.split("\n").map((line, i) => {
            if (line.match(/^\d+\.\s|^#+\s|^[A-Z\s&]{5,}$/)) {
              return <h4 key={i} className="weekly-section-title">{line.replace(/^#+\s*/, "")}</h4>;
            }
            if (line.trim() === "") return <br key={i} />;
            return <p key={i} className="weekly-line">{line}</p>;
          })}
        </div>
      )}
    </div>
  );
}
