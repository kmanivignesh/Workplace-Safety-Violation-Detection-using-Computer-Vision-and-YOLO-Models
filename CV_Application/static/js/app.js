/* ════════════════════════════════════════
   app.js – SafeGuard AI Frontend Logic
════════════════════════════════════════ */

'use strict';

// ── State ──────────────────────────────────────────────
const state = {
  cameraActive: false,
  voiceEnabled: true,
  currentTab:   'cam',
  imgOutputFile: null,
  vidJobId:      null,
  vidPollTimer:  null,
  statsTimer:    null,
  logTimer:      null,
};

// ── DOM helpers ────────────────────────────────────────
const $ = id => document.getElementById(id);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls)  e.className   = cls;
  if (html) e.innerHTML   = html;
  return e;
};

// ── Toast ──────────────────────────────────────────────
function toast(msg, type = 'success', duration = 3500) {
  const icons = { success: '✅', warning: '⚠️', danger: '🚨', info: 'ℹ️' };
  const wrap  = $('toast-container');
  const t     = el('div', `toast toast-${type}`);
  t.innerHTML = `<span class="toast-icon">${icons[type]||'ℹ️'}</span><span>${msg}</span>`;
  wrap.appendChild(t);
  setTimeout(() => {
    t.classList.add('removing');
    t.addEventListener('animationend', () => t.remove());
  }, duration);
}

// ── Tabs ───────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $(`pane-${tab}`).classList.add('active');
    state.currentTab = tab;
  });
});

// ── Global Status pill ─────────────────────────────────
function setGlobalStatus(status) {
  const pill  = $('global-status');
  const ring  = $('status-ring');
  const text  = $('status-text');
  const icon  = $('status-inner').querySelector('.status-icon');

  pill.textContent = status;
  pill.className   = `status-pill ${status}`;
  ring.className   = `status-ring ${status}`;

  const map = {
    SAFE:    { icon: '✅', color: '#00c853' },
    WARNING: { icon: '⚠️', color: '#ffd600' },
    DANGER:  { icon: '🚨', color: '#ff1744' },
    IDLE:    { icon: '💤', color: '#8892a4' },
  };
  const m = map[status] || map.IDLE;
  icon.textContent   = m.icon;
  text.textContent   = status;
  text.style.color   = m.color;
}

// ── Update stats from /api/stats ───────────────────────
function updateStats(data) {
  $('stat-persons').textContent = data.total_persons     ?? 0;
  $('stat-helmet').textContent  = data.helmet_violations ?? 0;
  $('stat-vest').textContent    = data.vest_violations   ?? 0;
  $('stat-smoking').textContent = data.smoking           ?? 0;

  if (data.fps !== undefined) $('fps-badge').textContent = `FPS: ${data.fps}`;
  if (data.timestamp)         $('ts-badge').textContent  = data.timestamp;

  setGlobalStatus(data.status || 'IDLE');
  renderAlerts(data.violations || []);

  // Flash stat cards on violations
  flashCard('card-helmet',  data.helmet_violations > 0);
  flashCard('card-vest',    data.vest_violations   > 0);
  flashCard('card-smoking', data.smoking           > 0);
}

function flashCard(id, active) {
  const c = $(id);
  if (!c) return;
  c.style.borderColor = active ? 'rgba(255,23,68,0.5)' : 'var(--border)';
}

// ── Alerts panel ───────────────────────────────────────
function renderAlerts(violations) {
  const list = $('alert-list');
  if (!violations || violations.length === 0) {
    list.innerHTML = '<div class="no-alerts">No active alerts</div>';
    return;
  }
  const iconMap = {
    'NO HELMET':       { cls: 'alert-helmet', icon: '⛑️', label: 'No Helmet Detected'     },
    'NO SAFETY VEST':  { cls: 'alert-vest',   icon: '🦺', label: 'No Safety Vest Detected' },
    'SMOKING DETECTED':{ cls: 'alert-smoke',  icon: '🚬', label: 'Smoking Detected'         },
  };
  const unique = [...new Set(violations)];
  list.innerHTML = unique.map(v => {
    const m = iconMap[v] || { cls: '', icon: '⚠️', label: v };
    return `<div class="alert-item ${m.cls}">
      <span class="alert-icon">${m.icon}</span>
      <span class="alert-text">${m.label}</span>
    </div>`;
  }).join('');
}

// ── Violation log ──────────────────────────────────────
function refreshLog() {
  fetch('/api/log')
    .then(r => r.json())
    .then(rows => {
      const list = $('log-list');
      if (!rows.length) {
        list.innerHTML = '<div class="no-alerts">No violations logged yet</div>';
        return;
      }
      list.innerHTML = rows.slice(0, 30).map(r => {
        const typeStr = r.violation_type || 'SAFE';
        const cls = typeStr === 'SAFE' ? 'safe'
                  : typeStr.includes('SMOKING') ? 'danger' : 'warning';
        return `<div class="log-row">
          <span class="log-ts">${(r.timestamp||'').slice(11,19)}</span>
          <span class="log-type ${cls}">${typeStr}</span>
          <span class="log-cnt">👤${r.persons||0}</span>
        </div>`;
      }).join('');
    })
    .catch(() => {});
}

// ── Camera controls ────────────────────────────────────
$('btn-start').addEventListener('click', async () => {
  $('btn-start').disabled = true;
  try {
    const res  = await fetch('/start_camera', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      state.cameraActive = true;
      $('feed-overlay').classList.add('hidden');
      $('btn-stop').disabled       = false;
      $('btn-screenshot').disabled = false;
      // Reload the stream img
      const img = $('webcam-stream');
      img.src = '/video_feed?' + Date.now();
      startStatsPoll();
      toast('Camera started', 'success');
    } else {
      toast(data.message || 'Failed to start camera', 'danger');
      $('btn-start').disabled = false;
    }
  } catch (e) {
    toast('Server error: ' + e.message, 'danger');
    $('btn-start').disabled = false;
  }
});

$('btn-stop').addEventListener('click', async () => {
  await fetch('/stop_camera', { method: 'POST' });
  state.cameraActive = false;
  stopStatsPoll();
  $('btn-start').disabled      = false;
  $('btn-stop').disabled       = true;
  $('btn-screenshot').disabled = true;
  $('feed-overlay').classList.remove('hidden');
  $('fps-badge').textContent = 'FPS: --';
  $('ts-badge').textContent  = '--:--:--';
  setGlobalStatus('IDLE');
  renderAlerts([]);
  toast('Camera stopped', 'info');
});

// ── Stats polling ──────────────────────────────────────
function startStatsPoll() {
  stopStatsPoll();
  state.statsTimer = setInterval(async () => {
    try {
      const data = await fetch('/api/stats').then(r => r.json());
      updateStats(data);
    } catch (_) {}
  }, 800);
  state.logTimer = setInterval(refreshLog, 5000);
  refreshLog();
}

function stopStatsPoll() {
  clearInterval(state.statsTimer);
  clearInterval(state.logTimer);
  state.statsTimer = null;
  state.logTimer   = null;
}

// ── Voice toggle ───────────────────────────────────────
$('btn-voice').addEventListener('click', async () => {
  const res  = await fetch('/toggle_voice', { method: 'POST' });
  const data = await res.json();
  state.voiceEnabled = data.voice_enabled;
  const btn = $('btn-voice');
  btn.classList.toggle('voice-off', !data.voice_enabled);
  btn.title = data.voice_enabled ? 'Mute Voice Alerts' : 'Enable Voice Alerts';
  toast(data.voice_enabled ? 'Voice alerts enabled' : 'Voice alerts muted', 'info');
});

// ── Fullscreen ─────────────────────────────────────────
$('btn-fullscreen').addEventListener('click', () => {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen();
  else document.exitFullscreen();
});

// ── Screenshot ─────────────────────────────────────────
$('btn-screenshot').addEventListener('click', async () => {
  try {
    const stream = $('webcam-stream');
    const canvas = document.createElement('canvas');
    canvas.width  = stream.naturalWidth  || stream.width;
    canvas.height = stream.naturalHeight || stream.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(stream, 0, 0);
    const url = canvas.toDataURL('image/jpeg', 0.9);

    $('modal-img').src         = url;
    $('modal-download').href   = url;
    $('modal-backdrop').style.display = 'flex';

    // Save snapshot thumbnail
    addSnapshotThumb(url);
    toast('Screenshot captured', 'success');
  } catch (e) {
    toast('Screenshot failed: ' + e.message, 'danger');
  }
});

// Modal close
['modal-close','modal-close2'].forEach(id => {
  $(id).addEventListener('click', () => { $('modal-backdrop').style.display = 'none'; });
});
$('modal-backdrop').addEventListener('click', e => {
  if (e.target === $('modal-backdrop')) $('modal-backdrop').style.display = 'none';
});

// ── Snapshot grid ──────────────────────────────────────
function addSnapshotThumb(src) {
  const grid = $('snapshot-grid');
  // Clear placeholder
  const placeholder = grid.querySelector('p');
  if (placeholder) placeholder.remove();

  const wrap = el('div', 'snapshot-thumb');
  wrap.innerHTML = `<img src="${src}" alt="snapshot" />`;
  wrap.addEventListener('click', () => {
    $('modal-img').src       = src;
    $('modal-download').href = src;
    $('modal-backdrop').style.display = 'flex';
  });
  grid.insertBefore(wrap, grid.firstChild);
  // Keep max 6 thumbs
  while (grid.children.length > 6) grid.removeChild(grid.lastChild);
}

// ══════════════════════════════════════════════════════
// IMAGE UPLOAD
// ══════════════════════════════════════════════════════
const imgDropzone = $('img-dropzone');
const imgInput    = $('img-input');

$('btn-img-browse').addEventListener('click', () => imgInput.click());
imgInput.addEventListener('change', () => {
  if (imgInput.files[0]) uploadImage(imgInput.files[0]);
});

// Drag-and-drop
imgDropzone.addEventListener('dragover', e => { e.preventDefault(); imgDropzone.classList.add('drag-over'); });
imgDropzone.addEventListener('dragleave', () => imgDropzone.classList.remove('drag-over'));
imgDropzone.addEventListener('drop', e => {
  e.preventDefault(); imgDropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadImage(file);
});

async function uploadImage(file) {
  imgDropzone.style.display = 'none';
  $('img-loading').style.display = 'flex';
  $('img-result').style.display  = 'none';

  const fd = new FormData();
  fd.append('image', file);

  try {
    const res  = await fetch('/upload_image', { method: 'POST', body: fd });
    const data = await res.json();

    $('img-loading').style.display = 'none';

    if (!data.ok) { toast(data.message, 'danger'); resetImageTab(); return; }

    $('img-result-display').src = 'data:image/jpeg;base64,' + data.image_b64;
    state.imgOutputFile = data.output_file;
    renderImageSummary(data.stats);
    $('img-result').style.display = 'flex';
    toast('Image processed successfully', 'success');
  } catch (e) {
    $('img-loading').style.display = 'none';
    toast('Upload error: ' + e.message, 'danger');
    resetImageTab();
  }
}

function renderImageSummary(stats) {
  const tags = [];
  if (!stats.violations || stats.violations.length === 0) {
    tags.push('<span class="viol-tag viol-safe">✅ All Safe</span>');
  } else {
    stats.violations.forEach(v => {
      if (v === 'NO HELMET')       tags.push('<span class="viol-tag viol-helmet">⛑️ No Helmet</span>');
      if (v === 'NO SAFETY VEST')  tags.push('<span class="viol-tag viol-vest">🦺 No Safety Vest</span>');
      if (v === 'SMOKING DETECTED')tags.push('<span class="viol-tag viol-smoke">🚬 Smoking</span>');
    });
  }
  tags.push(`<span class="viol-tag" style="background:rgba(255,255,255,0.06);color:var(--text2)">👤 ${stats.total_persons} person(s)</span>`);
  $('img-violation-summary').innerHTML = tags.join('');
}

$('btn-img-download').addEventListener('click', () => {
  if (state.imgOutputFile) window.location.href = `/download/${state.imgOutputFile}`;
});
$('btn-img-reset').addEventListener('click', resetImageTab);

function resetImageTab() {
  imgDropzone.style.display      = 'flex';
  $('img-result').style.display  = 'none';
  $('img-loading').style.display = 'none';
  imgInput.value = '';
  state.imgOutputFile = null;
}

// ══════════════════════════════════════════════════════
// VIDEO UPLOAD
// ══════════════════════════════════════════════════════
const vidDropzone = $('vid-dropzone');
const vidInput    = $('vid-input');

$('btn-vid-browse').addEventListener('click', () => vidInput.click());
vidInput.addEventListener('change', () => {
  if (vidInput.files[0]) uploadVideo(vidInput.files[0]);
});

vidDropzone.addEventListener('dragover', e => { e.preventDefault(); vidDropzone.classList.add('drag-over'); });
vidDropzone.addEventListener('dragleave', () => vidDropzone.classList.remove('drag-over'));
vidDropzone.addEventListener('drop', e => {
  e.preventDefault(); vidDropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadVideo(file);
});

async function uploadVideo(file) {
  vidDropzone.style.display        = 'none';
  $('vid-progress').style.display  = 'flex';
  $('vid-result').style.display    = 'none';
  $('vid-pct').textContent         = '…';
  $('vid-status-text').textContent = 'Uploading…';

  const fd = new FormData();
  fd.append('video', file);

  try {
    const res  = await fetch('/upload_video', { method: 'POST', body: fd });
    const data = await res.json();
    if (!data.ok) { toast(data.message, 'danger'); resetVideoTab(); return; }

    state.vidJobId = data.job_id;
    $('vid-status-text').textContent = 'Processing frames…';
    pollVideoStatus(data.job_id);
  } catch (e) {
    toast('Upload error: ' + e.message, 'danger');
    resetVideoTab();
  }
}

function pollVideoStatus(jobId) {
  let ticks = 0;
  state.vidPollTimer = setInterval(async () => {
    ticks++;
    // Animate progress ring
    const offset = Math.max(0, 213.6 - (ticks % 60) / 60 * 213.6);
    $('ring-fill').style.strokeDashoffset = offset;
    $('vid-pct').textContent = '⏳';

    try {
      const res  = await fetch(`/video_status/${jobId}`);
      const data = await res.json();
      if (data.status === 'done') {
        clearInterval(state.vidPollTimer);
        $('ring-fill').style.strokeDashoffset = 0;
        $('vid-pct').textContent              = '✓';
        $('vid-progress').style.display       = 'none';

        // Show result
        $('vid-player').src = `/static/outputs/${jobId}`;
        $('vid-result').style.display = 'flex';
        toast('Video processed successfully', 'success');
      }
    } catch (_) {}
  }, 1000);
}

$('btn-vid-download').addEventListener('click', () => {
  if (state.vidJobId) window.location.href = `/download/${state.vidJobId}`;
});
$('btn-vid-reset').addEventListener('click', resetVideoTab);

function resetVideoTab() {
  vidDropzone.style.display       = 'flex';
  $('vid-progress').style.display = 'none';
  $('vid-result').style.display   = 'none';
  vidInput.value = '';
  clearInterval(state.vidPollTimer);
  state.vidJobId = null;
}

// ── Init: fetch server status ──────────────────────────
(async () => {
  try {
    const s = await fetch('/api/status').then(r => r.json());
    state.voiceEnabled = s.voice_enabled;
    if (!s.voice_enabled) $('btn-voice').classList.add('voice-off');
  } catch (_) {}
})();
