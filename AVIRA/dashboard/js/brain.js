/*
 * AVIRA Brain Visualization – Neural Network Decision Graph
 * ==========================================================
 * Pure Canvas JS force-directed neural network showing how
 * all 12 AI agents connect and how data flows through them.
 *
 * Features:
 *  - 12 agent nodes arranged in layers (Input → Processing → Synthesis)
 *  - Animated "fire" pulses flowing along edges during analysis
 *  - Confidence scores displayed on each node
 *  - Color-coded by alert level
 *  - Click node to expand detail panel
 *  - Live updates via polling
 */

(function() {
  'use strict';

  // ── Canvas Setup ──────────────────────────────────────────────────
  const canvas = document.getElementById('brain-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  function resize() {
    canvas.width  = canvas.parentElement.offsetWidth  || 900;
    canvas.height = canvas.parentElement.offsetHeight || 520;
  }
  resize();
  window.addEventListener('resize', () => { resize(); layoutNodes(); });

  // ── Agent Definitions ─────────────────────────────────────────────
  const AGENTS = [
    // Input layer
    { id: 'A1',  label: 'Vital Signs',    sublabel: 'Agent 1',  layer: 0, color: '#00e5cc', icon: '💓' },
    { id: 'A2',  label: '16-Disease',     sublabel: 'Agent 2',  layer: 0, color: '#ff6b6b', icon: '🦠' },
    { id: 'A3',  label: 'Vision',         sublabel: 'Agent 3',  layer: 0, color: '#ffd93d', icon: '👁' },
    // Processing layer 1
    { id: 'A4',  label: 'Cross Valid.',   sublabel: 'Agent 4',  layer: 1, color: '#6bcb77', icon: '✅' },
    { id: 'A7',  label: 'Temporal',       sublabel: 'Agent 7',  layer: 1, color: '#845ef7', icon: '📈' },
    { id: 'A8',  label: 'Anomaly',        sublabel: 'Agent 8',  layer: 1, color: '#ff922b', icon: '⚠️' },
    // Processing layer 2
    { id: 'A5',  label: 'Recommend.',     sublabel: 'Agent 5',  layer: 2, color: '#4dabf7', icon: '💊' },
    { id: 'A9',  label: 'Survival Risk',  sublabel: 'Agent 9',  layer: 2, color: '#f06595', icon: '⚕️' },
    { id: 'A10', label: 'XGBoost Score',  sublabel: 'Agent 10', layer: 2, color: '#66d9e8', icon: '📊' },
    { id: 'A11', label: 'PPO Treat.',     sublabel: 'Agent 11', layer: 2, color: '#a9e34b', icon: '🎯' },
    // Synthesis layer
    { id: 'A6',  label: 'Report Gen.',    sublabel: 'Agent 6',  layer: 3, color: '#74c0fc', icon: '📋' },
    { id: 'A12', label: 'NVIDIA LLM',     sublabel: 'Agent 12', layer: 3, color: '#ff6b9d', icon: '🧠' },
  ];

  // ── Edge Definitions (from → to) ──────────────────────────────────
  const EDGES = [
    // A1 feeds
    { from: 'A1', to: 'A4', weight: 0.9 },
    { from: 'A1', to: 'A7', weight: 0.7 },
    { from: 'A1', to: 'A8', weight: 0.6 },
    { from: 'A1', to: 'A9', weight: 0.8 },
    { from: 'A1', to: 'A10', weight: 0.8 },
    // A2 feeds
    { from: 'A2', to: 'A4', weight: 0.9 },
    { from: 'A2', to: 'A9', weight: 0.7 },
    { from: 'A2', to: 'A10', weight: 0.7 },
    { from: 'A2', to: 'A11', weight: 0.8 },
    // A3 feeds
    { from: 'A3', to: 'A4', weight: 0.6 },
    // Processing feeds synthesis
    { from: 'A4', to: 'A5', weight: 0.85 },
    { from: 'A4', to: 'A12', weight: 0.9 },
    { from: 'A7', to: 'A12', weight: 0.7 },
    { from: 'A8', to: 'A12', weight: 0.6 },
    { from: 'A5', to: 'A6', weight: 0.9 },
    { from: 'A5', to: 'A12', weight: 0.8 },
    { from: 'A9', to: 'A11', weight: 0.75 },
    { from: 'A9', to: 'A12', weight: 0.8 },
    { from: 'A10', to: 'A11', weight: 0.7 },
    { from: 'A10', to: 'A12', weight: 0.75 },
    { from: 'A11', to: 'A12', weight: 0.9 },
    { from: 'A6', to: 'A12', weight: 0.85 },
  ];

  // ── Node state ────────────────────────────────────────────────────
  const nodeMap = {};
  AGENTS.forEach(a => {
    nodeMap[a.id] = Object.assign({}, a, {
      x: 0, y: 0, vx: 0, vy: 0,
      confidence: 0.5,
      active: false,
      firing: false,
      fireTime: 0,
    });
  });

  // ── Pulses (animated signals on edges) ───────────────────────────
  const pulses = [];

  function spawnPulse(fromId, toId, color) {
    pulses.push({ fromId, toId, t: 0, color, speed: 0.008 + Math.random() * 0.006 });
  }

  function triggerAnalysisAnimation() {
    // Simulate data flow through the network
    const delay_ms = [0, 200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2400];
    EDGES.forEach((e, i) => {
      setTimeout(() => spawnPulse(e.from, e.to, nodeMap[e.from].color), delay_ms[i % delay_ms.length]);
    });
    // Mark nodes as firing in sequence
    const order = ['A1','A2','A3','A4','A7','A8','A5','A9','A10','A11','A6','A12'];
    order.forEach((id, i) => {
      setTimeout(() => {
        nodeMap[id].firing = true;
        nodeMap[id].fireTime = Date.now();
      }, i * 180);
    });
  }

  // ── Layout ────────────────────────────────────────────────────────
  function layoutNodes() {
    const W = canvas.width, H = canvas.height;
    const layers = [[], [], [], []];
    AGENTS.forEach(a => layers[a.layer].push(a.id));

    const layerX = [W * 0.12, W * 0.35, W * 0.62, W * 0.88];

    layers.forEach((ids, li) => {
      const count = ids.length;
      ids.forEach((id, i) => {
        const node = nodeMap[id];
        node.x = layerX[li];
        node.y = H * 0.12 + (H * 0.76) * (i / Math.max(count - 1, 1));
      });
    });
  }
  layoutNodes();

  // ── Alert Level → Glow Color ──────────────────────────────────────
  const ALERT_COLORS = {
    NORMAL:   '#00e5cc',
    LOW:      '#6bcb77',
    MODERATE: '#ffd93d',
    HIGH:     '#ff922b',
    CRITICAL: '#ff4757',
  };
  let currentAlertColor = ALERT_COLORS.NORMAL;

  // ── Draw Helpers ──────────────────────────────────────────────────
  function drawGlow(x, y, radius, color, alpha = 0.25) {
    const g = ctx.createRadialGradient(x, y, radius * 0.3, x, y, radius * 1.8);
    g.addColorStop(0, color + Math.round(alpha * 255).toString(16).padStart(2, '0'));
    g.addColorStop(1, 'transparent');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, radius * 1.8, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawEdge(e, now) {
    const from = nodeMap[e.from];
    const to   = nodeMap[e.to];
    if (!from || !to) return;

    // Edge line
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.strokeStyle = `rgba(255,255,255,${0.06 + e.weight * 0.08})`;
    ctx.lineWidth = 1 + e.weight;
    ctx.stroke();
  }

  function drawPulse(p) {
    const from = nodeMap[p.fromId];
    const to   = nodeMap[p.toId];
    if (!from || !to) return;

    const x = from.x + (to.x - from.x) * p.t;
    const y = from.y + (to.y - from.y) * p.t;

    const grd = ctx.createRadialGradient(x, y, 0, x, y, 8);
    grd.addColorStop(0, p.color + 'ff');
    grd.addColorStop(1, 'transparent');
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawNode(node, now) {
    const R = 30;
    const isFiring = node.firing && (now - node.fireTime < 1200);
    const pulse = isFiring ? Math.sin((now - node.fireTime) / 80) * 5 : 0;
    const r = R + pulse;

    // Glow
    drawGlow(node.x, node.y, r, isFiring ? node.color : '#ffffff', isFiring ? 0.4 : 0.1);

    // Circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
    const grad = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 2, node.x, node.y, r);
    grad.addColorStop(0, isFiring ? node.color : '#2d3748');
    grad.addColorStop(1, isFiring ? node.color + '88' : '#1a202c');
    ctx.fillStyle = grad;
    ctx.fill();

    // Border
    ctx.strokeStyle = isFiring ? node.color : 'rgba(255,255,255,0.2)';
    ctx.lineWidth = isFiring ? 2.5 : 1;
    ctx.stroke();

    // Icon
    ctx.font = `${r * 0.65}px serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.icon, node.x, node.y);

    // Label below
    ctx.font = `bold 10px "Inter", sans-serif`;
    ctx.fillStyle = isFiring ? node.color : 'rgba(255,255,255,0.75)';
    ctx.fillText(node.label, node.x, node.y + r + 12);

    ctx.font = `9px "Inter", sans-serif`;
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.fillText(node.sublabel, node.x, node.y + r + 23);

    // Confidence bar (tiny arc)
    const conf = node.confidence;
    if (conf > 0) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 5, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * conf);
      ctx.strokeStyle = node.color + 'aa';
      ctx.lineWidth = 3;
      ctx.stroke();
    }
  }

  // ── Layer Labels ──────────────────────────────────────────────────
  function drawLayerLabels() {
    const W = canvas.width, H = canvas.height;
    const labels = ['INPUT', 'LAYER 1', 'LAYER 2', 'SYNTHESIS'];
    const xs = [W * 0.12, W * 0.35, W * 0.62, W * 0.88];
    ctx.font = '10px "Inter", monospace';
    ctx.textAlign = 'center';
    xs.forEach((x, i) => {
      ctx.fillStyle = 'rgba(255,255,255,0.2)';
      ctx.fillText(labels[i], x, 18);
      // Vertical guide line
      ctx.beginPath();
      ctx.moveTo(x, 26);
      ctx.lineTo(x, H - 10);
      ctx.strokeStyle = 'rgba(255,255,255,0.04)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 8]);
      ctx.stroke();
      ctx.setLineDash([]);
    });
  }

  // ── Main Animation Loop ───────────────────────────────────────────
  let animFrame;
  function render() {
    const now = Date.now();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Background
    const bg = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    bg.addColorStop(0, '#0a0f1e');
    bg.addColorStop(1, '#0d1529');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    drawLayerLabels();

    // Draw edges
    EDGES.forEach(e => drawEdge(e, now));

    // Update and draw pulses
    for (let i = pulses.length - 1; i >= 0; i--) {
      pulses[i].t += pulses[i].speed;
      if (pulses[i].t >= 1) {
        pulses.splice(i, 1);
      } else {
        drawPulse(pulses[i]);
      }
    }

    // Draw nodes
    AGENTS.forEach(a => drawNode(nodeMap[a.id], now));

    // Title
    ctx.font = 'bold 13px "Inter", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillStyle = currentAlertColor;
    ctx.fillText('🧠 AVIRA Decision Brain – 12-Agent Neural Pipeline', 16, canvas.height - 14);

    animFrame = requestAnimationFrame(render);
  }
  render();

  // ── Click: identify which node was clicked ────────────────────────
  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    AGENTS.forEach(a => {
      const node = nodeMap[a.id];
      const dist = Math.hypot(mx - node.x, my - node.y);
      if (dist < 34) {
        showNodeDetail(node);
      }
    });
  });

  function showNodeDetail(node) {
    const panel = document.getElementById('brain-detail-panel');
    const title = document.getElementById('brain-detail-title');
    const body  = document.getElementById('brain-detail-body');
    if (!panel) return;
    title.textContent = `${node.icon} ${node.label} (${node.sublabel})`;
    body.innerHTML = `
      <p><strong>Agent ID:</strong> ${node.id}</p>
      <p><strong>Confidence:</strong> ${(node.confidence * 100).toFixed(0)}%</p>
      <p><strong>Status:</strong> ${node.active ? '✅ Active' : '⏸ Idle'}</p>
      <p><strong>Layer:</strong> ${['Input', 'Processing 1', 'Processing 2', 'Synthesis'][node.layer]}</p>
    `;
    panel.style.display = 'block';
  }

  // ── Public API: update from analysis result ───────────────────────
  window.AVIRABrain = {
    /**
     * Update node confidence values from a pipeline result.
     * @param {Object} pipelineResult - The /analyse API response body
     */
    updateFromResult(pipelineResult) {
      const r = pipelineResult;
      if (!r) return;

      // Alert color
      const alert = (r.final_alert || r.master_synthesis?.final_alert || 'NORMAL').toUpperCase();
      currentAlertColor = ALERT_COLORS[alert] || ALERT_COLORS.NORMAL;

      // Agent confidence map from Agent 12
      const confMap = r.master_synthesis?.agent_confidence_map || {};

      const confMappings = {
        'A1':  r.vital_analysis?.confidence                   || confMap.VITAL_SIGNS || 0.5,
        'A2':  r.disease_results?.agent_confidence            || confMap.DISEASE_REASON || 0.5,
        'A3':  r.vision_findings?.has_detections ? 0.8 : 0.3,
        'A4':  r.validation_results?.confidence              || confMap.CROSS_VALID || 0.5,
        'A5':  r.recommendation_output?.confidence           || 0.7,
        'A6':  0.85,
        'A7':  r.temporal_trend?.trend_confidence            || confMap.TEMPORAL || 0.3,
        'A8':  r.anomaly_result?.confidence                  || confMap.ANOMALY || 0.5,
        'A9':  r.survival_risk?.confidence                   || confMap.SURVIVAL_RISK || 0.5,
        'A10': r.structured_risk?.confidence                 || confMap.STRUCTURED || 0.5,
        'A11': r.ppo_actions?.policy_confidence              || confMap.PPO_TREATMENT || 0.5,
        'A12': 0.9,
      };

      Object.entries(confMappings).forEach(([id, conf]) => {
        if (nodeMap[id]) {
          nodeMap[id].confidence = Math.max(0, Math.min(1, conf));
          nodeMap[id].active = true;
        }
      });

      triggerAnalysisAnimation();
    },

    /**
     * Trigger a demo pulse animation (call on page load)
     */
    demo() {
      triggerAnalysisAnimation();
    },

    /**
     * Reset all nodes to idle state
     */
    reset() {
      AGENTS.forEach(a => {
        nodeMap[a.id].confidence = 0.5;
        nodeMap[a.id].active = false;
        nodeMap[a.id].firing = false;
      });
      currentAlertColor = ALERT_COLORS.NORMAL;
    }
  };

  // Demo pulse on load
  setTimeout(() => window.AVIRABrain.demo(), 500);

})();
