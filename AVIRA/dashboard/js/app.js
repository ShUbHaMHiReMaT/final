/**
 * AVIRA Dashboard – app.js
 * PRANIVA – Advanced Veterinary Intelligence Research & Analytics
 * ================================================================
 * Full client-side application logic for the AVIRA web dashboard.
 * No external libraries. Pure ES6+ vanilla JavaScript.
 */

"use strict";

// ─────────────────────────────────────────────
//  Global Configuration & State
// ─────────────────────────────────────────────

let API_BASE = localStorage.getItem("avira_api_url") || "http://localhost:5000/api/v1";

const AppState = {
  currentCow:     localStorage.getItem("avira_cow_id") || "COW_001",
  currentSession: "",
  activePage:     "dashboard",
  deviceStatus:   {},
  latestAnalysis: null,
  liveChartData:  { hr: [], spo2: [], motion: [], timestamps: [] },
  connected:      false,
  _pollingTimer:  null,
  _clockTimer:    null,
  _devicePollTimer: null,
};

// ─────────────────────────────────────────────
//  API Service
// ─────────────────────────────────────────────

const API = {
  async _request(method, path, body = null, isFormData = false) {
    const opts = {
      method,
      headers: isFormData ? {} : { "Content-Type": "application/json", "Accept": "application/json" },
    };
    if (body) opts.body = isFormData ? body : JSON.stringify(body);
    try {
      const resp = await fetch(`${API_BASE}${path}`, opts);
      const data = await resp.json();
      if (!data.success && resp.status >= 400) {
        throw new Error((data.errors && data.errors[0]) || data.message || "API Error");
      }
      return data;
    } catch (err) {
      if (err.name === "TypeError") throw new Error("Cannot connect to AVIRA backend. Is it running?");
      throw err;
    }
  },
  fetchDashboard()                     { return this._request("GET", "/dashboard"); },
  uploadSensor(data)                   { return this._request("POST", "/device/upload", data); },
  uploadManual(data)                   { return this._request("POST", "/manual/upload", data); },
  uploadImage(formData)                { return this._request("POST", "/image/upload", formData, true); },
  triggerAnalysis(cowId, sessionId)    { return this._request("POST", "/analyse", { cow_id: cowId, session_id: sessionId }); },
  fetchReport(cowId, sessionId)        { return this._request("GET", `/report?cow_id=${cowId}&session_id=${sessionId}`); },
  fetchHistory(cowId, limit = 50)      { return this._request("GET", `/history?${cowId ? `cow_id=${cowId}&` : ""}limit=${limit}`); },
  fetchLogs(cowId, sessionId, file)    { return this._request("GET", `/logs?cow_id=${cowId}&session_id=${sessionId}&file=${file}`); },
  fetchDeviceStatus(cowId)             { return this._request("GET", `/device/status?cow_id=${cowId}`); },
};

// ─────────────────────────────────────────────
//  Navigation
// ─────────────────────────────────────────────

function navigateTo(page) {
  document.querySelectorAll(".page-section").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const section = document.getElementById(`page-${page}`);
  const navItem = document.getElementById(`nav-${page}`);
  if (section) section.classList.add("active");
  if (navItem) navItem.classList.add("active");

  AppState.activePage = page;

  // Page-specific on-load actions
  switch (page) {
    case "dashboard":   refreshDashboard(); break;
    case "knowledge":   loadKnowledgeBase(); break;
    case "live-sensor": initCharts(); break;
    case "history":     loadHistory(); break;
    default: break;
  }
}

// ─────────────────────────────────────────────
//  Toast Notifications
// ─────────────────────────────────────────────

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const colors = {
    success: "#10b981", error: "#ef4444", warning: "#f59e0b", info: "#3b82f6",
  };
  const icons = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };

  const toast = document.createElement("div");
  toast.style.cssText = `
    background:rgba(15,23,42,0.97);border:1px solid ${colors[type]}50;
    border-left:3px solid ${colors[type]};border-radius:8px;padding:0.75rem 1rem;
    display:flex;gap:0.6rem;align-items:center;min-width:280px;max-width:380px;
    box-shadow:0 4px 20px rgba(0,0,0,0.5);pointer-events:auto;
    animation:slideIn 0.3s ease;font-size:0.85rem;
  `;
  toast.innerHTML = `
    <span style="font-size:1.1rem">${icons[type]}</span>
    <span style="color:#f1f5f9;flex:1">${message}</span>
    <span style="cursor:pointer;color:#475569;font-size:1.1rem" onclick="this.parentElement.remove()">×</span>
  `;
  container.appendChild(toast);
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 4500);
}

// ─────────────────────────────────────────────
//  Clock
// ─────────────────────────────────────────────

function startClock() {
  const el = document.getElementById("header-time");
  function tick() {
    if (el) el.textContent = new Date().toLocaleTimeString("en-GB", { hour12: false });
  }
  tick();
  AppState._clockTimer = setInterval(tick, 1000);
}

// ─────────────────────────────────────────────
//  Dashboard Summary
// ─────────────────────────────────────────────

async function refreshDashboard() {
  try {
    const data = await API.fetchDashboard();
    renderDashboard(data);
  } catch (err) {
    updateSystemStatus(false);
  }
}

function renderDashboard(data) {
  updateSystemStatus(true);

  // Metrics
  setEl("metric-animals", data.recent_activity?.unique_animals ?? 0);
  setEl("metric-sessions", data.recent_activity?.total_sessions ?? 0);
  setEl("metric-diseases", data.knowledge_base?.diseases?.length ?? 6);

  // Recent sessions list
  const sessions = data.recent_activity?.recent_sessions || [];
  const sessionsList = document.getElementById("recent-sessions-list");
  if (sessionsList) {
    if (sessions.length === 0) {
      sessionsList.innerHTML = `<div style="color:var(--text-muted);font-size:0.82rem;text-align:center;padding:1.5rem">No sessions yet. Upload sensor data to begin.</div>`;
    } else {
      sessionsList.innerHTML = sessions.map(s => `
        <div style="display:flex;align-items:center;gap:0.75rem;padding:0.6rem 0;border-bottom:1px solid var(--border-glass);">
          <span style="font-size:1.1rem">🐄</span>
          <div style="flex:1">
            <div style="font-size:0.85rem;font-weight:600;color:var(--text-primary)">${s.cow_id || "—"}</div>
            <div style="font-size:0.72rem;color:var(--text-muted);font-family:'JetBrains Mono',monospace">${s.session_id || ""}</div>
          </div>
          <div style="font-size:0.72rem;color:var(--text-muted)">${formatDate(s.date || "")}</div>
        </div>`).join("");
    }
  }

  // Disease library mini
  const diseases = data.knowledge_base?.diseases || [];
  const libEl = document.getElementById("disease-library-mini");
  if (libEl) {
    libEl.innerHTML = diseases.map(d => `
      <div style="display:flex;align-items:center;gap:0.6rem;padding:0.4rem 0;border-bottom:1px solid var(--border-glass);">
        <span style="font-size:0.9rem">🦠</span>
        <div style="flex:1;font-size:0.82rem;font-weight:600;color:var(--text-primary)">${d.name}</div>
        <span class="badge ${(d.urgency || "").toLowerCase()}">${d.urgency || ""}</span>
      </div>`).join("");
  }
}

function updateSystemStatus(online) {
  const dot = document.getElementById("system-status-dot");
  const text = document.getElementById("system-status-text");
  const banner = document.getElementById("system-alert");
  if (dot) dot.className = `status-dot ${online ? "" : "offline"}`;
  if (text) text.textContent = online ? "System Operational" : "Backend Offline";
  if (banner) {
    banner.className = `alert-banner ${online ? "normal" : "critical"}`;
    banner.innerHTML = online
      ? `<span class="alert-icon">✅</span><div class="alert-text"><strong>AVIRA System Operational</strong> AI livestock health monitoring is active.</div>`
      : `<span class="alert-icon">🔴</span><div class="alert-text"><strong>Backend Offline</strong> Cannot connect to AVIRA backend at ${API_BASE}. Start the Flask server.</div>`;
  }
}

// ─────────────────────────────────────────────
//  Quick Analysis
// ─────────────────────────────────────────────

async function quickAnalyse() {
  const cowId = document.getElementById("quick-cow-id")?.value?.trim()?.toUpperCase() ||
                document.getElementById("global-cow-id")?.value?.trim()?.toUpperCase() ||
                AppState.currentCow;
  const sessionId = document.getElementById("quick-session-id")?.value?.trim()?.toUpperCase();
  const resultEl = document.getElementById("quick-analyse-result");

  if (!cowId || !sessionId) {
    showToast("Enter both Cow ID and Session ID", "warning");
    return;
  }

  const btn = document.getElementById("quick-analyse-btn");
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Running…"; }
  if (resultEl) resultEl.innerHTML = `<div class="skeleton" style="height:50px;border-radius:8px;margin-top:0.5rem"></div>`;

  try {
    const resp = await API.triggerAnalysis(cowId, sessionId);
    AppState.latestAnalysis = resp;
    AppState.currentCow = cowId;
    AppState.currentSession = sessionId;
    renderAnalysisResult(resp);
    if (resultEl) resultEl.innerHTML = buildAlertBanner(resp);
    showToast("AI analysis complete!", "success");
  } catch (err) {
    if (resultEl) resultEl.innerHTML = `<div class="alert-banner critical"><span class="alert-icon">❌</span><div class="alert-text">${err.message}</div></div>`;
    showToast(err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "🧠 Run AI Analysis"; }
  }
}

function buildAlertBanner(resp) {
  const level = (resp?.vitals_summary?.alert_level || "UNKNOWN").toUpperCase();
  const cls = level === "CRITICAL" ? "critical" : level === "HIGH" ? "high" : level === "MODERATE" ? "moderate" : "normal";
  const icon = level === "CRITICAL" ? "🔴" : level === "HIGH" ? "🟠" : level === "MODERATE" ? "🟡" : "🟢";
  const top = resp?.top_diseases?.[0];
  return `
    <div class="alert-banner ${cls}">
      <span class="alert-icon">${icon}</span>
      <div class="alert-text">
        <strong>Alert: ${level}</strong>
        ${top ? `Top indicator: ${top.disease} (${pct(top.probability)}%)` : "Analysis complete."}
      </div>
    </div>`;
}

// ─────────────────────────────────────────────
//  Analysis Result Renderer
// ─────────────────────────────────────────────

function renderAnalysisResult(resp) {
  const analysis = resp?.analysis || {};
  const health = analysis?.health_summary || {};
  const vitals = resp?.vitals_summary || {};

  // Right panel
  setEl("panel-cow-id",     resp?.cow_id || "—");
  setEl("panel-session-id", resp?.session_id || "—");

  const level = vitals.alert_level || "UNKNOWN";
  const alertColor = { CRITICAL: "#ef4444", HIGH: "#f59e0b", MODERATE: "#3b82f6", NORMAL: "#10b981" }[level] || "#94a3b8";
  const alertEl = document.getElementById("panel-alert-level");
  if (alertEl) { alertEl.textContent = level; alertEl.style.color = alertColor; }
  setEl("panel-stress-index", `Stress index: ${(vitals.stress_index || 0).toFixed(3)}`);

  // Top disease
  const top = (resp?.top_diseases || [])[0];
  if (top) {
    setEl("panel-top-disease", top.disease || "—");
    setEl("panel-top-prob-text", `${pct(top.probability)}% probability · ${top.confidence || ""}`);
    const fill = document.getElementById("panel-top-prob-fill");
    if (fill) fill.style.width = `${Math.round((top.probability || 0) * 100)}%`;
  }

  // Evidence
  const evidenceEl = document.getElementById("panel-evidence-list");
  if (evidenceEl && top) {
    const matched = top.matched_evidence || [];
    const missing = top.missing_evidence || [];
    evidenceEl.innerHTML = [
      ...matched.slice(0, 4).map(e => `<li class="evidence-item matched">✓ ${e}</li>`),
      ...missing.slice(0, 2).map(e => `<li class="evidence-item missing">○ ${e}</li>`),
    ].join("") || "<li style='color:var(--text-muted);font-size:0.78rem'>No evidence data</li>";
  }

  // Recommendations
  const recsEl = document.getElementById("panel-recommendations");
  if (recsEl) {
    const recs = resp?.recommendations || [];
    recsEl.innerHTML = recs.slice(0, 5).map(r => {
      const pri = r.priority || 9;
      const dotCls = pri === 1 ? "rec-priority-1" : pri <= 3 ? "rec-priority-2" : pri <= 5 ? "rec-priority-3" : "rec-priority-other";
      return `<div class="rec-card"><div class="rec-priority-dot ${dotCls}"></div><div>${r.action || r}</div></div>`;
    }).join("") || "<div style='color:var(--text-muted);font-size:0.78rem'>No recommendations</div>";
  }

  // Confidence
  const conf = analysis?.pipeline_confidence || health?.data_quality_score || 0;
  setEl("panel-confidence", `${pct(conf)}%`);

  // Disease engine page
  const diseaseCont = document.getElementById("disease-cards-container");
  if (diseaseCont) renderDiseaseCards(resp?.top_diseases || [], diseaseCont);

  // Reasoning chain page
  const chainEl = document.getElementById("reasoning-chain-content");
  if (chainEl) renderReasoningChain(resp?.reasoning_chain || [], chainEl);
}

// ─────────────────────────────────────────────
//  Disease Cards
// ─────────────────────────────────────────────

function renderDiseaseCards(diseases, container) {
  if (!container || !diseases.length) {
    if (container) container.innerHTML = `<div style="color:var(--text-muted);font-size:0.82rem">No disease data. Run an analysis first.</div>`;
    return;
  }
  container.innerHTML = diseases.map((d, i) => {
    const prob = d.probability || 0;
    const fillCls = prob >= 0.6 ? "danger" : prob >= 0.35 ? "warning" : "";
    const badgeCls = prob >= 0.6 ? "critical" : prob >= 0.35 ? "high" : prob >= 0.15 ? "medium" : "low";
    const matched = (d.matched_evidence || []).slice(0, 4).map(e => `<li class="evidence-item matched">✓ ${e}</li>`).join("");
    const missing = (d.missing_evidence || []).slice(0, 2).map(e => `<li class="evidence-item missing">○ ${e}</li>`).join("");
    return `
      <div class="disease-card fade-in" style="animation-delay:${i * 0.08}s">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.4rem">
          <div class="disease-name">#${i+1} ${d.disease || "Unknown"}</div>
          <div style="font-family:'JetBrains Mono',monospace;font-weight:800;font-size:1.1rem;color:${prob >= 0.6 ? "var(--brand-danger)" : prob >= 0.35 ? "var(--brand-warning)" : "var(--brand-primary)"}">${pct(prob)}%</div>
        </div>
        <div class="disease-probability-bar">
          <div class="disease-probability-fill ${fillCls}" style="width:${pct(prob)}%"></div>
        </div>
        <div class="disease-meta" style="margin-top:0.4rem">
          <span class="badge ${badgeCls}">${d.confidence || "N/A"}</span>
          <span class="badge ${badgeCls}">${d.urgency || "N/A"}</span>
          ${d.vet_required ? `<span class="badge critical">🏥 VET REQUIRED</span>` : ""}
          ${d.reportable ? `<span class="badge high">📢 REPORTABLE</span>` : ""}
        </div>
        ${matched || missing ? `<ul class="evidence-list" style="margin-top:0.6rem">${matched}${missing}</ul>` : ""}
      </div>`;
  }).join("");
}

// ─────────────────────────────────────────────
//  Reasoning Chain
// ─────────────────────────────────────────────

function renderReasoningChain(chain, container) {
  if (!chain.length) {
    container.innerHTML = `<div style="color:var(--text-muted);font-size:0.82rem">Run an analysis to see the reasoning chain.</div>`;
    return;
  }
  container.innerHTML = `<div class="timeline">${chain.map((step, i) => `
    <div class="timeline-entry">
      <div class="timeline-time" style="font-size:0.68rem">${step.agent || `Step ${i+1}`}</div>
      <div class="timeline-line-col">
        <div class="timeline-dot" style="background:${step.confidence >= 0.7 ? "var(--brand-primary)" : "var(--brand-warning)"}"></div>
        ${i < chain.length - 1 ? `<div class="timeline-connector"></div>` : ""}
      </div>
      <div class="timeline-content">
        <div class="timeline-event">${step.step || step.agent || "Step"}</div>
        <div style="font-size:0.78rem;color:var(--text-muted)">${step.finding || ""}</div>
        ${(step.evidence || []).length ? `<div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.2rem">${step.evidence.join(" · ")}</div>` : ""}
        <div style="font-size:0.7rem;color:var(--brand-primary);margin-top:0.2rem">Conf: ${pct(step.confidence || 0)}%</div>
      </div>
    </div>`).join("")}</div>`;
}

// ─────────────────────────────────────────────
//  Live Charts (Pure Canvas)
// ─────────────────────────────────────────────

const _chartInstances = {};

function initCharts() {
  ["hr", "spo2", "motion"].forEach(key => {
    const canvasId = `chart-${key}`;
    const canvas = document.getElementById(canvasId);
    if (canvas) {
      canvas.width = canvas.offsetWidth || 600;
      canvas.height = canvas.offsetHeight || 200;
    }
  });
  // Draw empty charts
  drawLineChart("chart-hr",     AppState.liveChartData.hr,     "Heart Rate", "#10b981",  20,  150);
  drawLineChart("chart-spo2",   AppState.liveChartData.spo2,   "SpO2",       "#00d4aa",  80,  100);
  drawLineChart("chart-motion", AppState.liveChartData.motion, "Motion",     "#7c3aed",   0,    5);
}

function drawLineChart(canvasId, data, label, color, minVal, maxVal) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width  = canvas.offsetWidth  || 600;
  const H = canvas.height = canvas.offsetHeight || 200;

  const pad = { top: 16, right: 16, bottom: 32, left: 48 };
  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top  - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  // Background
  ctx.fillStyle = "rgba(10,15,30,0.4)";
  ctx.beginPath(); ctx.roundRect(0, 0, W, H, 8); ctx.fill();

  // Grid lines
  const gridCount = 4;
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= gridCount; i++) {
    const y = pad.top + (chartH / gridCount) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + chartW, y); ctx.stroke();
    // Y labels
    const val = maxVal - ((maxVal - minVal) / gridCount) * i;
    ctx.fillStyle = "rgba(148,163,184,0.5)";
    ctx.font = "10px JetBrains Mono, monospace";
    ctx.fillText(val.toFixed(0), 4, y + 4);
  }

  if (!data || data.length < 2) {
    // No data – draw placeholder
    ctx.fillStyle = "rgba(71,85,105,0.4)";
    ctx.font = "13px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`Waiting for ${label} data…`, W / 2, H / 2);
    ctx.textAlign = "left";
    return;
  }

  const maxPts = Math.min(data.length, 60);
  const pts = data.slice(-maxPts);
  const stepX = chartW / Math.max(pts.length - 1, 1);

  const toY = v => pad.top + chartH - ((Math.min(Math.max(v, minVal), maxVal) - minVal) / (maxVal - minVal)) * chartH;

  // Fill gradient
  const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + chartH);
  grad.addColorStop(0, color + "40");
  grad.addColorStop(1, color + "00");

  ctx.beginPath();
  ctx.moveTo(pad.left, toY(pts[0]));
  pts.forEach((v, i) => {
    const x = pad.left + i * stepX;
    if (i === 0) ctx.moveTo(x, toY(v));
    else {
      const px = pad.left + (i - 1) * stepX;
      const cpx = (px + x) / 2;
      ctx.bezierCurveTo(cpx, toY(pts[i-1]), cpx, toY(v), x, toY(v));
    }
  });
  ctx.lineTo(pad.left + (pts.length - 1) * stepX, pad.top + chartH);
  ctx.lineTo(pad.left, pad.top + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  pts.forEach((v, i) => {
    const x = pad.left + i * stepX;
    if (i === 0) ctx.moveTo(x, toY(v));
    else {
      const px = pad.left + (i - 1) * stepX;
      const cpx = (px + x) / 2;
      ctx.bezierCurveTo(cpx, toY(pts[i-1]), cpx, toY(v), x, toY(v));
    }
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.shadowColor = color;
  ctx.shadowBlur = 6;
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Last value dot
  const lastX = pad.left + (pts.length - 1) * stepX;
  const lastY = toY(pts[pts.length - 1]);
  ctx.beginPath(); ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
  ctx.fillStyle = color; ctx.fill();

  // Label + last value
  ctx.fillStyle = color;
  ctx.font = "bold 12px Inter, sans-serif";
  ctx.fillText(`${label}: ${pts[pts.length - 1].toFixed(1)}`, pad.left + 4, pad.top - 2);
}

function addLiveSensorReading(hr, spo2, motion) {
  const d = AppState.liveChartData;
  const push = (arr, val) => { arr.push(val); if (arr.length > 60) arr.shift(); };
  if (hr    !== null && hr    !== undefined) push(d.hr,     hr);
  if (spo2  !== null && spo2  !== undefined) push(d.spo2,   spo2);
  if (motion !== null && motion !== undefined) push(d.motion, motion);

  drawLineChart("chart-hr",     d.hr,     "Heart Rate", "#10b981",  20,  150);
  drawLineChart("chart-spo2",   d.spo2,   "SpO2",       "#00d4aa",  80,  100);
  drawLineChart("chart-motion", d.motion, "Motion",     "#7c3aed",   0,    5);

  // Update live metric cards
  if (hr !== null)     { setEl("live-hr",     hr?.toFixed(0) ?? "--");     setLiveStatus("live-hr-status",     hr,     40, 100, "BPM"); }
  if (spo2 !== null)   { setEl("live-spo2",   spo2?.toFixed(1) ?? "--");   setLiveStatus("live-spo2-status",   spo2,   90, 100, "%");   }
  if (motion !== null) { setEl("live-motion", motion?.toFixed(3) ?? "--"); }
}

function setLiveStatus(id, val, low, high, unit) {
  const el = document.getElementById(id);
  if (!el) return;
  const cls = val < low ? "elevated" : val > high ? "high" : "normal";
  el.className = `metric-status ${cls}`;
  el.textContent = val < low ? `Low (${val.toFixed(1)} ${unit})` : val > high ? `High (${val.toFixed(1)} ${unit})` : `Normal`;
}

// ─────────────────────────────────────────────
//  Sensor Upload Form
// ─────────────────────────────────────────────

function fillSampleSensor() {
  const samples = { "s-cow-id": "COW_001", "s-device-id": "PICO_01",
    "s-hr": "65", "s-hr-valid": "true", "s-spo2": "97.5", "s-spo2-valid": "true",
    "s-ax": "0.012", "s-ay": "0.031", "s-az": "0.981", "s-motion": "1.023" };
  Object.entries(samples).forEach(([id, v]) => { const el = document.getElementById(id); if (el) el.value = v; });
}

async function submitSensorForm(e) {
  e.preventDefault();
  const btn = document.getElementById("sensor-submit-btn");
  const resultEl = document.getElementById("sensor-result");
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Uploading…"; }
  if (resultEl) resultEl.innerHTML = "";

  const cowId = (document.getElementById("s-cow-id")?.value || "").trim().toUpperCase();
  const payload = {
    cow_id:           cowId,
    device_id:        document.getElementById("s-device-id")?.value || "PICO_01",
    heart_rate:       parseFloat(document.getElementById("s-hr")?.value) || null,
    heart_rate_valid: document.getElementById("s-hr-valid")?.value === "true",
    spo2:             parseFloat(document.getElementById("s-spo2")?.value) || null,
    spo2_valid:       document.getElementById("s-spo2-valid")?.value === "true",
    accel_x:          parseFloat(document.getElementById("s-ax")?.value) || null,
    accel_y:          parseFloat(document.getElementById("s-ay")?.value) || null,
    accel_z:          parseFloat(document.getElementById("s-az")?.value) || null,
    motion_magnitude: parseFloat(document.getElementById("s-motion")?.value) || null,
  };

  try {
    const resp = await API.uploadSensor(payload);
    AppState.currentSession = resp.session_id || "";
    AppState.currentCow     = cowId;
    if (resultEl) resultEl.innerHTML = `
      <div class="alert-banner normal">
        <span class="alert-icon">✅</span>
        <div class="alert-text">
          <strong>Sensor data uploaded</strong>
          Session: <code style="font-family:monospace;color:var(--brand-primary)">${resp.session_id}</code>
          <br><small style="color:var(--text-muted)">Copy this session ID for analysis</small>
        </div>
      </div>`;
    addLiveSensorReading(payload.heart_rate, payload.spo2, payload.motion_magnitude);
    showToast("Sensor data uploaded successfully!", "success");
  } catch (err) {
    if (resultEl) resultEl.innerHTML = `<div class="alert-banner critical"><span class="alert-icon">❌</span><div class="alert-text">${err.message}</div></div>`;
    showToast(err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "📡 Upload Sensor Data"; }
  }
}

async function checkDeviceStatus() {
  const cowId = (document.getElementById("s-cow-id")?.value || AppState.currentCow).trim().toUpperCase();
  const el = document.getElementById("device-status-content");
  if (!cowId || !el) return;
  el.innerHTML = `<div class="skeleton" style="height:60px;border-radius:8px"></div>`;
  try {
    const resp = await API.fetchDeviceStatus(cowId);
    const dev = resp.device || {};
    el.innerHTML = `
      <div class="connection-card">
        <div class="conn-icon" style="background:rgba(${resp.status === "OFFLINE" ? "239,68,68" : "0,212,170"},0.12)">${resp.status === "OFFLINE" ? "📵" : "📡"}</div>
        <div>
          <div style="font-weight:700;color:${resp.status === "OFFLINE" ? "var(--brand-danger)" : "var(--brand-success)"}">${dev.status || resp.status || "UNKNOWN"}</div>
          <div style="font-size:0.75rem;color:var(--text-muted)">
            ${dev.device_id || ""} · Last seen: ${dev.last_seen ? new Date(dev.last_seen).toLocaleTimeString() : "Never"}
            ${dev.heart_rate ? `<br>HR: ${dev.heart_rate} BPM · SpO2: ${dev.spo2}%` : ""}
          </div>
        </div>
      </div>`;
  } catch (err) {
    el.innerHTML = `<div style="color:var(--brand-danger);font-size:0.82rem">${err.message}</div>`;
  }
}

// ─────────────────────────────────────────────
//  Manual Input Form
// ─────────────────────────────────────────────

function fillSampleManual() {
  const samples = { "m-cow-id": "COW_001", "m-temp": "38.5", "m-milk": "22.0",
    "m-appetite": "8", "m-rumination": "7", "m-water": "80", "m-feed": "15",
    "m-observations": "Normal appetite and behaviour. Slight drop in milk production noted." };
  Object.entries(samples).forEach(([id, v]) => { const el = document.getElementById(id); if (el) el.value = v; });
}

async function submitManualForm(e) {
  e.preventDefault();
  const btn = document.getElementById("manual-submit-btn");
  const spinner = document.getElementById("manual-spinner");
  const resultEl = document.getElementById("manual-result");
  if (btn) btn.disabled = true;
  if (spinner) spinner.classList.remove("hidden");
  if (resultEl) resultEl.innerHTML = "";

  const cowId = (document.getElementById("m-cow-id")?.value || "").trim().toUpperCase();
  const sessionId = (document.getElementById("m-session-id")?.value || "").trim().toUpperCase() || AppState.currentSession || undefined;

  const payload = {
    cow_id:          cowId,
    temperature:     parseFloat(document.getElementById("m-temp")?.value) || null,
    milk_production: parseFloat(document.getElementById("m-milk")?.value) || null,
    appetite:        parseInt(document.getElementById("m-appetite")?.value)  || null,
    rumination:      parseInt(document.getElementById("m-rumination")?.value) || null,
    water_intake:    parseFloat(document.getElementById("m-water")?.value) || null,
    feed_intake:     parseFloat(document.getElementById("m-feed")?.value) || null,
    observations:    document.getElementById("m-observations")?.value || null,
  };
  if (sessionId) payload.session_id = sessionId;

  try {
    const resp = await API.uploadManual(payload);
    AppState.currentSession = resp.session_id;
    AppState.currentCow     = cowId;

    if (resultEl) resultEl.innerHTML = `
      <div class="alert-banner normal">
        <span class="alert-icon">✅</span>
        <div class="alert-text">
          <strong>Observations recorded</strong>
          Session: <code style="font-family:monospace;color:var(--brand-primary)">${resp.session_id}</code>
        </div>
      </div>`;

    // Auto-trigger analysis
    showToast("Running AI analysis…", "info");
    const analysisResp = await API.triggerAnalysis(cowId, resp.session_id);
    AppState.latestAnalysis = analysisResp;
    renderAnalysisResult(analysisResp);
    if (resultEl) resultEl.innerHTML += buildAlertBanner(analysisResp);
    showToast("Analysis complete!", "success");
  } catch (err) {
    if (resultEl) resultEl.innerHTML = `<div class="alert-banner critical"><span class="alert-icon">❌</span><div class="alert-text">${err.message}</div></div>`;
    showToast(err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
    if (spinner) spinner.classList.add("hidden");
  }
}

// ─────────────────────────────────────────────
//  Image Upload
// ─────────────────────────────────────────────

let _selectedImageFile = null;

function handleImageSelect(event) {
  const file = event.target.files[0];
  if (file) _loadImagePreview(file);
}

function handleImageDrop(event) {
  event.preventDefault();
  document.getElementById("image-drop-zone").style.borderColor = "var(--border-glass)";
  const file = event.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) _loadImagePreview(file);
  else showToast("Please drop an image file", "warning");
}

function _loadImagePreview(file) {
  _selectedImageFile = file;
  const preview = document.getElementById("image-preview");
  const container = document.getElementById("image-preview-container");
  const btn = document.getElementById("vision-upload-btn");
  if (preview && container) {
    preview.src = URL.createObjectURL(file);
    container.style.display = "block";
  }
  if (btn) btn.disabled = false;
}

async function uploadImage() {
  if (!_selectedImageFile) { showToast("Select an image first", "warning"); return; }
  const cowId = (document.getElementById("img-cow-id")?.value || "").trim().toUpperCase() || AppState.currentCow;
  if (!cowId) { showToast("Enter a Cow ID", "warning"); return; }

  const btn = document.getElementById("vision-upload-btn");
  const spinner = document.getElementById("vision-spinner");
  if (btn) btn.disabled = true;
  if (spinner) spinner.classList.remove("hidden");

  const formData = new FormData();
  formData.append("image", _selectedImageFile);
  formData.append("cow_id", cowId);
  if (AppState.currentSession) formData.append("session_id", AppState.currentSession);

  try {
    const uploadResp = await API.uploadImage(formData);
    const sessionId = uploadResp.session_id;
    AppState.currentSession = sessionId;
    AppState.currentCow = cowId;

    showToast("Image uploaded. Running AI analysis…", "info");
    const analysisResp = await API.triggerAnalysis(cowId, sessionId);
    AppState.latestAnalysis = analysisResp;
    renderAnalysisResult(analysisResp);

    const resultCard = document.getElementById("vision-result-card");
    const resultsContent = document.getElementById("vision-results-content");
    if (resultCard) resultCard.style.display = "block";
    if (resultsContent) {
      const vision = analysisResp?.analysis?.vision_analysis || {};
      const conditions = vision.detected_conditions || [];
      resultsContent.innerHTML = `
        <div style="margin-bottom:0.75rem">${buildAlertBanner(analysisResp)}</div>
        <div style="margin-bottom:0.5rem;font-size:0.82rem;font-weight:700;color:var(--text-secondary)">Vision Findings</div>
        <div style="font-size:0.82rem;color:var(--text-secondary);margin-bottom:0.6rem">${vision.visual_summary || "Image analysed successfully."}</div>
        ${conditions.length ? conditions.map(c => `
          <div class="rec-card">
            <div class="rec-priority-dot ${c.confidence > 0.7 ? "rec-priority-1" : c.confidence > 0.4 ? "rec-priority-2" : "rec-priority-3"}"></div>
            <div><strong>${c.display_name}</strong> – Confidence: ${pct(c.confidence)}%</div>
          </div>`).join("") : "<div style='color:var(--text-muted);font-size:0.82rem'>No visual abnormalities detected.</div>"}`;
    }
    showToast("Vision analysis complete!", "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
    if (spinner) spinner.classList.add("hidden");
  }
}

// ─────────────────────────────────────────────
//  History
// ─────────────────────────────────────────────

async function loadHistory() {
  const cowFilter = (document.getElementById("history-filter-cow")?.value || "").trim().toUpperCase() || undefined;
  const container = document.getElementById("history-table-container");
  if (!container) return;
  container.innerHTML = `<div class="skeleton" style="height:200px;border-radius:8px"></div>`;

  try {
    const resp = await API.fetchHistory(cowFilter);
    const sessions = resp.sessions || [];
    if (!sessions.length) {
      container.innerHTML = `<div style="color:var(--text-muted);font-size:0.82rem;text-align:center;padding:2rem">No sessions found${cowFilter ? ` for ${cowFilter}` : ""}.</div>`;
      return;
    }
    container.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
        <thead><tr style="color:var(--text-muted);text-transform:uppercase;font-size:0.7rem;letter-spacing:0.08em">
          <th style="text-align:left;padding:0.4rem 0.6rem;border-bottom:1px solid var(--border-glass)">Date</th>
          <th style="text-align:left;padding:0.4rem 0.6rem;border-bottom:1px solid var(--border-glass)">Cow ID</th>
          <th style="text-align:left;padding:0.4rem 0.6rem;border-bottom:1px solid var(--border-glass)">Session ID</th>
          <th style="text-align:left;padding:0.4rem 0.6rem;border-bottom:1px solid var(--border-glass)">Files</th>
          <th style="padding:0.4rem 0.6rem;border-bottom:1px solid var(--border-glass)">Actions</th>
        </tr></thead>
        <tbody>${sessions.map(s => `
          <tr style="border-bottom:1px solid var(--border-glass);transition:background 0.2s" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background=''">
            <td style="padding:0.6rem;color:var(--text-muted)">${formatDate(s.date || "")}</td>
            <td style="padding:0.6rem;font-family:'JetBrains Mono',monospace;color:var(--brand-primary)">${s.cow_id || "—"}</td>
            <td style="padding:0.6rem;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--text-secondary)">${s.session_id || "—"}</td>
            <td style="padding:0.6rem;color:var(--text-muted)">${(s.files || []).join(", ") || "—"}</td>
            <td style="padding:0.6rem;text-align:center">
              <button class="btn btn-ghost btn-sm" onclick="viewSessionReport('${s.cow_id}','${s.session_id}')">📄 Report</button>
            </td>
          </tr>`).join("")}</tbody>
      </table>`;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--brand-danger);font-size:0.82rem">${err.message}</div>`;
    showToast(err.message, "error");
  }
}

function viewSessionReport(cowId, sessionId) {
  document.getElementById("report-cow-id").value = cowId;
  document.getElementById("report-session-id").value = sessionId;
  navigateTo("reports");
  loadReport();
}

// ─────────────────────────────────────────────
//  Report Viewer
// ─────────────────────────────────────────────

async function loadReport() {
  const cowId = (document.getElementById("report-cow-id")?.value || "").trim().toUpperCase();
  const sessionId = (document.getElementById("report-session-id")?.value || "").trim().toUpperCase();
  const container = document.getElementById("report-content");
  if (!cowId || !sessionId) { showToast("Enter Cow ID and Session ID", "warning"); return; }
  if (!container) return;
  container.innerHTML = `<div class="skeleton" style="height:300px;border-radius:8px"></div>`;

  try {
    const resp = await API.fetchReport(cowId, sessionId);
    const preview = resp.report_preview || resp.report_text || "No report text available.";
    container.innerHTML = `
      <div style="margin-bottom:0.75rem;display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap">
        <span style="font-size:0.82rem;color:var(--text-muted)">Session: <code style="font-family:monospace;color:var(--brand-primary)">${sessionId}</code></span>
        <span style="font-size:0.82rem;color:var(--text-muted)">Files: ${(resp.files_available || []).join(", ")}</span>
        <button class="btn btn-ghost btn-sm" onclick="copyReport()">📋 Copy</button>
      </div>
      <pre id="report-text-content" style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;
        color:var(--text-secondary);background:rgba(0,0,0,0.3);border-radius:var(--radius-sm);
        padding:1rem;max-height:600px;overflow:auto;white-space:pre-wrap;border:1px solid var(--border-glass)">${escapeHtml(preview)}</pre>`;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--brand-danger);font-size:0.82rem">${err.message}</div>`;
  }
}

function copyReport() {
  const el = document.getElementById("report-text-content");
  if (el) { navigator.clipboard.writeText(el.textContent); showToast("Report copied to clipboard", "success"); }
}

// ─────────────────────────────────────────────
//  Log Viewer
// ─────────────────────────────────────────────

async function loadLog() {
  const cowId = (document.getElementById("log-cow-id")?.value || "").trim().toUpperCase();
  const sessionId = (document.getElementById("log-session-id")?.value || "").trim().toUpperCase();
  const file = document.getElementById("log-file")?.value || "timeline";
  const content = document.getElementById("log-content");
  if (!cowId || !sessionId) { showToast("Enter Cow ID and Session ID", "warning"); return; }
  if (content) content.textContent = "Loading…";

  try {
    const resp = await API.fetchLogs(cowId, sessionId, file);
    if (content) content.textContent = resp.content || "Empty log file.";
  } catch (err) {
    if (content) content.textContent = `Error: ${err.message}`;
    showToast(err.message, "error");
  }
}

// ─────────────────────────────────────────────
//  Timeline Viewer
// ─────────────────────────────────────────────

async function loadTimeline() {
  const cowId = (document.getElementById("timeline-cow-id")?.value || "").trim().toUpperCase();
  const sessionId = (document.getElementById("timeline-session-id")?.value || "").trim().toUpperCase();
  const container = document.getElementById("timeline-content");
  if (!cowId || !sessionId) { showToast("Enter Cow ID and Session ID", "warning"); return; }
  if (!container) return;
  container.innerHTML = `<div class="skeleton" style="height:150px;border-radius:8px"></div>`;

  try {
    const resp = await API.fetchLogs(cowId, sessionId, "timeline");
    // Parse timeline text into events
    const lines = (resp.content || "").split("\n").filter(l => l.includes("[EVENT]") || l.includes("UTC"));
    if (!lines.length) { container.innerHTML = `<div style="color:var(--text-muted);font-size:0.82rem">No timeline events found.</div>`; return; }
    container.innerHTML = `<div class="timeline">${lines.slice(0, 15).map((line, i) => {
      const timeMatch = line.match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
      const time = timeMatch ? new Date(timeMatch[0]).toLocaleTimeString() : "??:??:??";
      const event = line.replace(/.*\[EVENT\]\s*/, "").replace(/\s+/g, " ").trim();
      return `<div class="timeline-entry">
        <div class="timeline-time">${time}</div>
        <div class="timeline-line-col">
          <div class="timeline-dot"></div>
          ${i < lines.length - 1 ? `<div class="timeline-connector"></div>` : ""}
        </div>
        <div class="timeline-content">
          <div class="timeline-event">${escapeHtml(event || line.trim())}</div>
        </div>
      </div>`;}).join("")}</div>`;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--brand-danger);font-size:0.82rem">${err.message}</div>`;
  }
}

// ─────────────────────────────────────────────
//  Knowledge Base
// ─────────────────────────────────────────────

async function loadKnowledgeBase() {
  const container = document.getElementById("knowledge-base-content");
  if (!container) return;

  try {
    const resp = await API.fetchDashboard();
    const diseases = resp.knowledge_base?.diseases || [];
    container.innerHTML = diseases.map((d, i) => `
      <div class="card fade-in" style="animation-delay:${i*0.07}s">
        <div class="card-header">
          <div style="display:flex;align-items:center;gap:0.75rem">
            <span style="font-size:1.4rem">🦠</span>
            <div>
              <div style="font-weight:700;font-size:0.95rem">${d.name || d.disease_id}</div>
              <div style="font-size:0.75rem;color:var(--text-muted)">${d.category || ""}</div>
            </div>
          </div>
          <div style="display:flex;gap:0.4rem;align-items:center">
            <span class="badge ${(d.urgency || "").toLowerCase()}">${d.urgency || ""}</span>
            ${d.reportable ? `<span class="badge high">📢 Reportable</span>` : ""}
            ${d.vet_required ? `<span class="badge critical">🏥 Vet</span>` : ""}
          </div>
        </div>
        <div style="font-size:0.82rem;color:var(--text-secondary)">${d.description || ""}</div>
        ${d.key_symptoms && d.key_symptoms.length ? `
          <div style="margin-top:0.6rem;font-size:0.75rem;color:var(--text-muted)">
            <span style="font-weight:600;color:var(--text-secondary)">Key symptoms:</span>
            ${d.key_symptoms.slice(0, 5).join(" · ")}
          </div>` : ""}
      </div>`).join("");
  } catch (err) {
    container.innerHTML = `<div style="color:var(--brand-danger);font-size:0.82rem">${err.message}</div>`;
  }
}

// ─────────────────────────────────────────────
//  Settings
// ─────────────────────────────────────────────

function saveSettings() {
  const url = document.getElementById("setting-api-url")?.value?.trim();
  const cowId = document.getElementById("setting-default-cow")?.value?.trim()?.toUpperCase();
  if (url) {
    API_BASE = url;
    localStorage.setItem("avira_api_url", url);
  }
  if (cowId) {
    AppState.currentCow = cowId;
    localStorage.setItem("avira_cow_id", cowId);
    const globalInput = document.getElementById("global-cow-id");
    if (globalInput) globalInput.value = cowId;
  }
  showToast("Settings saved successfully!", "success");
}

// ─────────────────────────────────────────────
//  Polling
// ─────────────────────────────────────────────

function startPolling() {
  AppState._pollingTimer = setInterval(() => {
    if (AppState.activePage === "dashboard") refreshDashboard();
  }, 30_000);
}

// ─────────────────────────────────────────────
//  Utilities
// ─────────────────────────────────────────────

function setEl(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function pct(val) {
  return Math.round((val || 0) * 100);
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return dateStr; }
}

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ─────────────────────────────────────────────
//  Initialisation
// ─────────────────────────────────────────────

function init() {
  // Load saved settings
  const savedUrl = localStorage.getItem("avira_api_url");
  const savedCow = localStorage.getItem("avira_cow_id");
  if (savedUrl) API_BASE = savedUrl;
  if (savedCow) AppState.currentCow = savedCow;

  // Populate settings form
  const settingUrl = document.getElementById("setting-api-url");
  const settingCow = document.getElementById("setting-default-cow");
  const globalCow  = document.getElementById("global-cow-id");
  if (settingUrl) settingUrl.value = API_BASE;
  if (settingCow) settingCow.value = AppState.currentCow;
  if (globalCow)  globalCow.value  = AppState.currentCow;

  // Keyboard navigation for nav items
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") item.click();
    });
  });

  // Start services
  startClock();
  startPolling();
  navigateTo("dashboard");

  // Log startup
  console.log(`%cAVIRA Dashboard v1.0.0 – PRANIVA`, "color:#00d4aa;font-weight:bold;font-size:14px");
  console.log(`%cAPI Base: ${API_BASE}`, "color:#94a3b8;font-size:12px");
}

// Start on DOM ready
document.addEventListener("DOMContentLoaded", init);
