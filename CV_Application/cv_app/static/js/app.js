'use strict';

/* ── State ─────────────────────────────────────────────── */
const S = {
  camActive:false, voiceOn:true, tab:'cam',
  imgFile:null, vidJob:null, vidTimer:null, statsTimer:null, logTimer:null, snapTimer:null,
};

/* ── DOM ────────────────────────────────────────────────── */
const $=id=>document.getElementById(id);
const mk=(tag,cls,html)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(html)e.innerHTML=html;return e;};

/* ── Particle Canvas ────────────────────────────────────── */
(function(){
  const c=$('particle-canvas');if(!c)return;
  const ctx=c.getContext('2d');
  let W,H,pts=[];
  function resize(){W=c.width=window.innerWidth;H=c.height=window.innerHeight;}
  resize();window.addEventListener('resize',resize);
  for(let i=0;i<60;i++)pts.push({x:Math.random()*1920,y:Math.random()*1080,vx:(Math.random()-.5)*.3,vy:(Math.random()-.5)*.3,r:Math.random()*2+.5});
  function draw(){
    ctx.clearRect(0,0,W,H);
    pts.forEach(p=>{
      p.x+=p.vx;p.y+=p.vy;
      if(p.x<0)p.x=W;if(p.x>W)p.x=0;
      if(p.y<0)p.y=H;if(p.y>H)p.y=0;
      ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle='rgba(0,229,255,0.35)';ctx.fill();
    });
    pts.forEach((a,i)=>pts.slice(i+1).forEach(b=>{
      const d=Math.hypot(a.x-b.x,a.y-b.y);
      if(d<120){ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
        ctx.strokeStyle=`rgba(0,229,255,${.12*(1-d/120)})`;ctx.stroke();}
    }));
    requestAnimationFrame(draw);
  }
  draw();
})();

/* ── Toast ──────────────────────────────────────────────── */
function toast(msg,type='success',ms=3500){
  const icons={success:'✅',warning:'⚠️',danger:'🚨',info:'ℹ️'};
  const t=mk('div',`toast toast-${type}`);
  t.innerHTML=`<span class="t-icon">${icons[type]||'ℹ️'}</span><span>${msg}</span>`;
  $('toast-container').appendChild(t);
  setTimeout(()=>{t.classList.add('out');t.addEventListener('animationend',()=>t.remove());},ms);
}

/* ── Tabs ───────────────────────────────────────────────── */
document.querySelectorAll('.tab').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const tab=btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    $(`pane-${tab}`).classList.add('active');
    S.tab=tab;
  });
});

/* ── Safety Status ──────────────────────────────────────── */
function setStatus(st){
  // Navbar pill
  const pill=$('global-status');
  pill.className=`status-pill ${st}`;
  $('status-pill-text').textContent=st;
  // HUD
  const hud=$('hud-status');
  hud.textContent=st;
  hud.className=`hud-status ${st}`;
  // Gauge
  const arc=$('gauge-arc');
  const icon=$('gauge-icon');
  const lbl=$('gauge-label');
  arc.className=`gauge-arc ${st}`;
  icon.className=`gauge-icon ${st}`;
  lbl.className=`gauge-label ${st}`;
  lbl.textContent=st;
  // Pulse dot colour
  const pd=$('pulse-dot');
  pd.style.background=st==='DANGER'?'var(--red)':st==='WARNING'?'var(--yellow)':'var(--green)';
  pd.style.boxShadow=st==='DANGER'?'0 0 8px var(--red)':st==='WARNING'?'0 0 8px var(--yellow)':'0 0 8px var(--green)';
}

/* ── Stats update ───────────────────────────────────────── */
function updateStats(d){
  $('stat-persons').textContent = d.total_persons??0;
  $('stat-helmet').textContent  = d.helmet_violations??0;
  $('stat-vest').textContent    = d.vest_violations??0;
  $('stat-smoking').textContent = d.smoking??0;
  if(d.fps!=null) $('fps-badge').textContent=`FPS: ${d.fps}`;
  if(d.timestamp) $('ts-badge').textContent=d.timestamp;
  setStatus(d.status||'IDLE');
  renderAlerts(d.violations||[]);
  const flash=(id,on)=>{
    const c=$(id);if(!c)return;
    c.classList.toggle('active',on);
  };
  flash('card-helmet', d.helmet_violations>0);
  flash('card-vest',   d.vest_violations>0);
  flash('card-smoking',d.smoking>0);
  // Violation banner
  const banner=$('violation-banner');
  const viols=d.violations||[];
  if(viols.length){
    $('banner-text').textContent=viols.join(' | ');
    banner.style.display='flex';
  } else {
    banner.style.display='none';
  }
}

/* ── Alert Feed ─────────────────────────────────────────── */
function renderAlerts(viols){
  const list=$('alert-list');
  $('alert-count').textContent=viols.length;
  if(!viols.length){list.innerHTML='<div class="empty-msg">No active alerts</div>';return;}
  const map={
    'NO HELMET':      {cls:'a-helmet',icon:'⛑️',text:'No Helmet Detected'},
    'NO SAFETY VEST': {cls:'a-vest',  icon:'🦺',text:'No Safety Vest'},
    'SMOKING DETECTED':{cls:'a-smoke',icon:'🚬',text:'Smoking Detected'},
  };
  list.innerHTML=[...new Set(viols)].map(v=>{
    const m=map[v]||{cls:'',icon:'⚠️',text:v};
    return `<div class="alert-item ${m.cls}"><span class="alert-icon">${m.icon}</span><span class="alert-text">${m.text}</span></div>`;
  }).join('');
}

/* ── Violation Log ──────────────────────────────────────── */
function refreshLog(){
  fetch('/api/log').then(r=>r.json()).then(rows=>{
    const list=$('log-list');
    if(!rows.length){list.innerHTML='<div class="empty-msg">No violations logged yet</div>';return;}
    list.innerHTML=rows.slice(0,30).map(r=>{
      const t=r.violation_type||'SAFE';
      const cls=t==='SAFE'?'safe':t.includes('SMOKING')?'danger':'warn';
      return `<div class="log-row">
        <span class="log-ts">${(r.timestamp||'').slice(11,19)}</span>
        <span class="log-viol ${cls}">${t}</span>
        <span class="log-info">👤${r.persons||0}</span>
      </div>`;
    }).join('');
  }).catch(()=>{});
}

/* ── Snapshots ──────────────────────────────────────────── */
function refreshSnaps(){
  fetch('/api/snapshots').then(r=>r.json()).then(d=>{
    const files=d.snapshots||[];
    $('snap-count').textContent=`${files.length} saved`;
    const grid=$('snapshot-grid');
    if(!files.length){grid.innerHTML='<div class="empty-msg">No snapshots yet</div>';return;}
    grid.innerHTML=files.slice(0,9).map(f=>{
      const src=`/static/outputs/snapshots/${f}`;
      return `<div class="snap-thumb" onclick="openModal('${src}')"><img src="${src}" alt="snapshot" /></div>`;
    }).join('');
  }).catch(()=>{});
}

/* ── Modal ──────────────────────────────────────────────── */
function openModal(src){
  $('modal-img').src=src;
  $('modal-download').href=src;
  $('modal-backdrop').style.display='flex';
}
['modal-close','modal-close2'].forEach(id=>{
  const el=$(id);if(el)el.addEventListener('click',()=>$('modal-backdrop').style.display='none');
});
$('modal-backdrop').addEventListener('click',e=>{
  if(e.target===$('modal-backdrop'))$('modal-backdrop').style.display='none';
});

/* ── Screenshot ─────────────────────────────────────────── */
$('btn-screenshot').addEventListener('click',()=>{
  try{
    const img=$('webcam-stream');
    const cv=document.createElement('canvas');
    cv.width=img.naturalWidth||img.width;
    cv.height=img.naturalHeight||img.height;
    cv.getContext('2d').drawImage(img,0,0);
    const url=cv.toDataURL('image/jpeg',.92);
    openModal(url);
    // Add to snap grid locally
    const grid=$('snapshot-grid');
    const ph=grid.querySelector('.empty-msg');if(ph)ph.remove();
    const thumb=mk('div','snap-thumb');
    thumb.innerHTML=`<img src="${url}" alt="snapshot" />`;
    thumb.onclick=()=>openModal(url);
    grid.insertBefore(thumb,grid.firstChild);
    while(grid.children.length>9)grid.removeChild(grid.lastChild);
    toast('Screenshot captured','success');
  }catch(e){toast('Screenshot failed','danger');}
});

/* ── Camera Controls ────────────────────────────────────── */
$('btn-start').addEventListener('click',async()=>{
  $('btn-start').disabled=true;
  try{
    const res=await fetch('/start_camera',{method:'POST'});
    const d=await res.json();
    if(d.ok){
      S.camActive=true;
      $('feed-overlay').classList.add('hidden');
      $('btn-stop').disabled=false;
      $('btn-screenshot').disabled=false;
      $('webcam-stream').src='/video_feed?'+Date.now();
      $('live-indicator').classList.add('on');
      $('scan-line').classList.add('active');
      startPolling();
      toast('Camera started','success');
    }else{
      toast(d.message||'Failed to start camera','danger');
      $('btn-start').disabled=false;
    }
  }catch(e){toast('Server error: '+e.message,'danger');$('btn-start').disabled=false;}
});

$('btn-stop').addEventListener('click',async()=>{
  await fetch('/stop_camera',{method:'POST'});
  S.camActive=false;
  stopPolling();
  $('btn-start').disabled=false;
  $('btn-stop').disabled=true;
  $('btn-screenshot').disabled=true;
  $('feed-overlay').classList.remove('hidden');
  $('live-indicator').classList.remove('on');
  $('scan-line').classList.remove('active');
  $('fps-badge').textContent='FPS: --';
  $('ts-badge').textContent='--:--:--';
  $('violation-banner').style.display='none';
  setStatus('IDLE');
  renderAlerts([]);
  toast('Camera stopped','info');
});

/* ── Polling ────────────────────────────────────────────── */
function startPolling(){
  stopPolling();
  S.statsTimer=setInterval(async()=>{
    try{const d=await fetch('/api/stats').then(r=>r.json());updateStats(d);}catch(_){}
  },800);
  S.logTimer=setInterval(refreshLog,5000);
  S.snapTimer=setInterval(refreshSnaps,8000);
  refreshLog();refreshSnaps();
}
function stopPolling(){
  clearInterval(S.statsTimer);clearInterval(S.logTimer);clearInterval(S.snapTimer);
  S.statsTimer=S.logTimer=S.snapTimer=null;
}

/* ── Voice Toggle ───────────────────────────────────────── */
$('btn-voice').addEventListener('click',async()=>{
  const res=await fetch('/toggle_voice',{method:'POST'});
  const d=await res.json();
  S.voiceOn=d.voice_enabled;
  $('icon-voice-on').classList.toggle('hidden',!d.voice_enabled);
  $('icon-voice-off').classList.toggle('hidden',d.voice_enabled);
  $('btn-voice').classList.toggle('voice-off',!d.voice_enabled);
  toast(d.voice_enabled?'Voice alerts enabled':'Voice alerts muted','info');
});

/* ── Fullscreen ─────────────────────────────────────────── */
$('btn-fullscreen').addEventListener('click',()=>{
  if(!document.fullscreenElement)document.documentElement.requestFullscreen();
  else document.exitFullscreen();
});

/* ══════════════════ IMAGE UPLOAD ═══════════════════════ */
const imgDZ=$('img-dropzone'), imgIn=$('img-input');
$('btn-img-browse').addEventListener('click',()=>imgIn.click());
imgIn.addEventListener('change',()=>{if(imgIn.files[0])uploadImage(imgIn.files[0]);});
imgDZ.addEventListener('dragover',e=>{e.preventDefault();imgDZ.classList.add('drag-over');});
imgDZ.addEventListener('dragleave',()=>imgDZ.classList.remove('drag-over'));
imgDZ.addEventListener('drop',e=>{e.preventDefault();imgDZ.classList.remove('drag-over');const f=e.dataTransfer.files[0];if(f)uploadImage(f);});

async function uploadImage(file){
  imgDZ.style.display='none';
  $('img-loading').style.display='flex';
  $('img-result').style.display='none';
  const fd=new FormData();fd.append('image',file);
  try{
    const d=await fetch('/upload_image',{method:'POST',body:fd}).then(r=>r.json());
    $('img-loading').style.display='none';
    if(!d.ok){toast(d.message,'danger');resetImg();return;}
    $('img-result-display').src='data:image/jpeg;base64,'+d.image_b64;
    S.imgFile=d.output_file;
    renderChips(d.stats);
    $('img-result').style.display='flex';
    toast('Image processed','success');
  }catch(e){$('img-loading').style.display='none';toast('Upload error','danger');resetImg();}
}

function renderChips(stats){
  const tags=[];
  if(!stats.violations||!stats.violations.length){
    tags.push('<span class="chip chip-safe">✅ All Safe</span>');
  }else{
    if(stats.violations.includes('NO HELMET'))       tags.push('<span class="chip chip-helmet">⛑️ No Helmet</span>');
    if(stats.violations.includes('NO SAFETY VEST'))  tags.push('<span class="chip chip-vest">🦺 No Vest</span>');
    if(stats.violations.includes('SMOKING DETECTED'))tags.push('<span class="chip chip-smoke">🚬 Smoking</span>');
  }
  tags.push(`<span class="chip chip-info">👤 ${stats.total_persons} person(s)</span>`);
  $('img-violation-summary').innerHTML=tags.join('');
}

$('btn-img-download').addEventListener('click',()=>{if(S.imgFile)window.location.href=`/download/${S.imgFile}`;});
$('btn-img-reset').addEventListener('click',resetImg);
function resetImg(){
  imgDZ.style.display='flex';
  $('img-result').style.display='none';
  $('img-loading').style.display='none';
  imgIn.value='';S.imgFile=null;
}

/* ══════════════════ VIDEO UPLOAD ═══════════════════════ */
const vidDZ=$('vid-dropzone'),vidIn=$('vid-input');
$('btn-vid-browse').addEventListener('click',()=>vidIn.click());
vidIn.addEventListener('change',()=>{if(vidIn.files[0])uploadVideo(vidIn.files[0]);});
vidDZ.addEventListener('dragover',e=>{e.preventDefault();vidDZ.classList.add('drag-over');});
vidDZ.addEventListener('dragleave',()=>vidDZ.classList.remove('drag-over'));
vidDZ.addEventListener('drop',e=>{e.preventDefault();vidDZ.classList.remove('drag-over');const f=e.dataTransfer.files[0];if(f)uploadVideo(f);});

async function uploadVideo(file){
  vidDZ.style.display='none';
  $('vid-progress').style.display='flex';
  $('vid-result').style.display='none';
  $('vid-pct').textContent='Uploading...';
  const fd=new FormData();fd.append('video',file);
  try{
    const d=await fetch('/upload_video',{method:'POST',body:fd}).then(r=>r.json());
    if(!d.ok){toast(d.message,'danger');resetVid();return;}
    S.vidJob=d.job_id;
    $('vid-status-text').textContent='Analysing frames...';
    pollVideo(d.job_id);
  }catch(e){toast('Upload error','danger');resetVid();}
}

function pollVideo(jobId){
  S.vidTimer=setInterval(async()=>{
    try{
      const d=await fetch(`/video_status/${jobId}`).then(r=>r.json());
      const st=d.status;
      if(st==='done'){
        clearInterval(S.vidTimer);
        $('vid-fill').style.width='100%';
        $('vid-progress').style.display='none';
        $('vid-player').src=`/static/outputs/${jobId}`;
        $('vid-result').style.display='flex';
        toast('Video processed successfully','success');
      }else if(st&&st.includes('/')){
        const [cur,tot]=st.split('/').map(Number);
        const pct=tot?Math.round(cur/tot*100):0;
        $('vid-fill').style.width=pct+'%';
        $('vid-pct').textContent=`${pct}%`;
        $('vid-status-text').textContent=`Frame ${cur} / ${tot}`;
      }
    }catch(_){}
  },1200);
}

$('btn-vid-download').addEventListener('click',()=>{if(S.vidJob)window.location.href=`/download/${S.vidJob}`;});
$('btn-vid-reset').addEventListener('click',resetVid);
function resetVid(){
  vidDZ.style.display='flex';
  $('vid-progress').style.display='none';
  $('vid-result').style.display='none';
  $('vid-fill').style.width='0%';
  vidIn.value='';clearInterval(S.vidTimer);S.vidJob=null;
}

/* ── Init ───────────────────────────────────────────────── */
(async()=>{
  try{
    const s=await fetch('/api/status').then(r=>r.json());
    S.voiceOn=s.voice_enabled;
    if(!s.voice_enabled){
      $('icon-voice-on').classList.add('hidden');
      $('icon-voice-off').classList.remove('hidden');
      $('btn-voice').classList.add('voice-off');
    }
  }catch(_){}
})();
