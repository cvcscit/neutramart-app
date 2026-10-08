// Error boundary for the Shen.AI modal.
//
// App.jsx only wraps chat messages in MessageBoundary, so anything the scan modal threw
// during render took down the whole app (blank page). This keeps the failure local and
// shows what actually broke instead of a white screen.

import React from "react";

export default class ScanBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { err: null };
  }

  static getDerivedStateFromError(err) {
    return { err };
  }

  componentDidCatch(err, info) {
    console.error("[senai_scan] scan UI crashed:", err, info);
  }

  render() {
    if (this.state.err) {
      return (
        <div className="drawer-scrim scan-scrim" onClick={this.props.onClose}>
          <aside className="scan-modal" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-head">
              <h2>Vitals Scan</h2>
              <button className="icon-btn" onClick={this.props.onClose}>✕</button>
            </div>
            <div className="scan-body">
              <div className="scan-error">
                Shen.AI scan crashed: {String(this.state.err?.message || this.state.err)}
              </div>
              <p className="muted-note">See the browser console for the full stack trace.</p>
              <button className="send-btn scan-action" onClick={this.props.onClose}>Close</button>
            </div>
          </aside>
        </div>
      );
    }
    return this.props.children;
  }
}
