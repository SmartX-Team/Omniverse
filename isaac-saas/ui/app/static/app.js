let auto=true, timer=null;
const $=s=>document.querySelector(s);
const esc=s=>(s==null?"":String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function toast(msg,kind){const t=document.createElement('div');t.className='toast '+(kind||'');t.textContent=msg;
 $('#toasts').appendChild(t);setTimeout(()=>t.remove(),4200);}
function stClass(r){if(r.phase==='Running'&&r.ready)return['ok','Running'];
 if(r.phase==='Failed'||r.phase==='CrashLoopBackOff')return['bad',r.phase];
 if(r.phase==='Running'&&!r.ready)return['wait','Not ready'];
 if(r.phase==='-'||!r.phase)return['mut','Pending'];return['wait',r.phase];}

async function refresh(){
 try{
   const [ri,rg]=await Promise.all([
     fetch('/api/instances',{cache:'no-store'}), fetch('/api/gpu',{cache:'no-store'})]);
   render(await ri.json()); renderGpu(await rg.json());
   $('#updated').textContent='updated '+new Date().toLocaleTimeString();
 }catch(e){toast('refresh failed','err');}
 loadCollect();   // per-pod collection verification (fail-soft, real-time)
}

// ---- per-pod collection verification panel (network, real-time) ----
async function loadCollect(){
 let d; try{d=await (await fetch('/api/metrics/verify',{cache:'no-store'})).json();}
 catch(e){d={available:false,reason:'request failed'};}
 renderCollect(d);
}
function renderCollect(d){
 const el=$('#collectBody'), st=$('#collectStatus');
 if(!d||!d.available){
   st.innerHTML='<span class="cdot bad"></span>Prometheus unreachable';
   el.innerHTML='<div class="hint">Prometheus \uc5f0\uacb0 \uc548\ub428 \u2014 \uc218\uc9d1 \uac80\uc99d \ubd88\uac00. (\uc218\uc9d1\uae30\uac00 \uc548 \ub3cc\uc544\ub3c4 \uc778\uc2a4\ud134\uc2a4\ub294 \uc815\uc0c1 \ub3d9\uc791\ud569\ub2c8\ub2e4.)'
     +(d&&d.reason?' <span class="mono" style="font-size:11px;color:var(--mut)">'+esc(d.reason)+'</span>':'')+'</div>';
   return;
 }
 const all=d.podsTotal>0&&d.podsUp===d.podsTotal;
 st.innerHTML='<span class="cdot '+(all?'ok':(d.podsUp>0?'warn':'bad'))+'"></span>'+d.podsUp+'/'+d.podsTotal+' pods scraped &middot; up=1';
 if(!d.pods||!d.pods.length){
   el.innerHTML='<div class="hint">\uc218\uc9d1 \ub300\uc0c1 pod\uc774 \uc544\uc9c1 \uc5c6\uc2b5\ub2c8\ub2e4 \u2014 \uc778\uc2a4\ud134\uc2a4 \uc0dd\uc131 \ud6c4 \uba87 \ubd84 \ub4a4 \uc790\ub3d9\uc73c\ub85c \ub098\ud0c0\ub0a9\ub2c8\ub2e4.</div>';return;
 }
 el.innerHTML='<table class="ctab"><thead><tr><th>pod</th><th>owner</th><th>scrape</th>'
   +'<th class="num">samples</th><th class="num">\u2191 tx</th><th class="num">\u2193 rx</th></tr></thead><tbody>'
   +d.pods.map(p=>'<tr><td class="mono pn">'+esc(p.pod)+'</td><td>'+esc(p.owner||'-')+'</td>'
     +'<td>'+(p.up===1?'<span class="cdot ok"></span>up':(p.up===0?'<span class="cdot bad"></span>down':'<span class="cdot warn"></span>?'))+'</td>'
     +'<td class="num mono">'+(p.samples!=null?p.samples:'-')+'</td>'
     +'<td class="num mono">'+(p.txBps!=null?fmtBps(p.txBps):'-')+'</td>'
     +'<td class="num mono">'+(p.rxBps!=null?fmtBps(p.rxBps):'-')+'</td></tr>').join('')
   +'</tbody></table><div class="chint">updated '+new Date(d.ts*1000).toLocaleTimeString()
   +' \u00b7 auto-refresh \u00b7 up=1 + samples&gt;0 + tx/rx \ud750\ub974\uba74 \uc815\uc0c1 \uc218\uc9d1</div>';
}
let _gpu=null;   // last /api/gpu payload (ban-modal pickers read node/UUID lists from it)
function renderGpu(g){
 _gpu=g;
 const el=$('#gpu'); if(!g||!g.nodes){el.innerHTML='';return;}
 if(!g.nodes.length){el.innerHTML='<div class="gpuhead"><span class="warn">'
   +'No GPUs recognized by the cluster \u2014 GPU Operator may be disabled on the other nodes.</span></div>';return;}
 const t=g.totals;
 const head='<div class="gpuhead">'
   +'<span class="ghl">You can launch <b>'+g.launchable+'</b> more instance'+(g.launchable===1?'':'s')+'</span>'
   +'<span class="gsub">cluster GPUs: '+t.free+' free / '+t.total+' total'
   +(g.usageKnown?'':' \u00b7 usage needs cluster pods:list RBAC')+'</span></div>';
 const legend='<div class="legend">'
   +'<span><span class="pip used"></span>this UI</span>'
   +'<span><span class="pip ext"></span>other workloads</span>'
   +'<span><span class="pip ban"></span>banned</span>'
   +'<span><span class="pip denied"></span>product-denied</span>'
   +'<span><span class="pip free"></span>free</span></div>';
 const cards=g.nodes.map(n=>{
   const gb=n.gpuBans||[];
   // under DRA every UUID ban is schedule-time enforced (CEL) -> always show all
   const nban=(g.banAsUsed||g.draEnabled)?gb.length:gb.filter(b=>!b.applied).length;
   const banCls=g.banAsUsed?'usedban':'ban';
   const banTip=g.banAsUsed?'banned \u00b7 counted as used'
     :(g.draEnabled?'banned \u00b7 DRA-enforced at schedule time':'UUID-banned GPU');
   const nden=n.deniedGpus||0;
   // used splits into: this UI's instances (blue) vs other cluster workloads (purple)
   const nui=Math.min(n.uiUsed||0,n.used), next=n.used-nui;
   let pips='';
   for(let i=0;i<n.total;i++){
     if(i<nui)pips+='<span class="pip used" title="in use by an instance of this UI"></span>';
     else if(i<nui+next)pips+='<span class="pip ext" title="in use by another workload on the cluster (not this UI)"></span>';
     else if(i<n.used+nban)pips+='<span class="pip '+banCls+'" title="'+banTip+'"></span>';
     else if(i<n.used+nban+nden)pips+='<span class="pip denied" title="incompatible product \u00b7 excluded per-GPU by DRA CEL"></span>';
     else pips+='<span class="pip free"></span>';
   }
   const badge=n.nvenc?'':'<span class="nob" title="no hardware encoder">no NVENC</span>';
   const off=n.allowed?'':'<span class="nob" title="not in instance node set">off-target</span>';
   const ban=n.banned?'<span class="banb" title="'+esc((n.banReasons||[]).join('; '))+'">BANNED</span>':'';
   const deny=n.denied?'<span class="banb" title="'+esc(n.deniedReason||'')+'">INCOMPATIBLE</span>':'';
   const uuids=gb.length?'<details class="gc-bans"><summary>'+(g.banAsUsed?'reserved':'banned')+' ('+gb.length+')</summary>'+gb.map(b=>
     esc((b.uuid||'').slice(0,20))+'&hellip;'+(b.reason?' \u2014 '+esc(b.reason):'')
     +(g.draEnabled?' (enforced)':(b.applied?' (applied)':' (pending)'))).join('<br>')+'</details>':'';
   const blocked=n.banned||n.denied;
   const sel=n.allowed&&!blocked&&(n.draExact||n.nvenc);
   return '<div class="gcard'+(sel?' on':'')+(blocked?' banned':'')+'">'
     +'<div class="gc-h"><span class="gc-n">'+esc(n.node)+'</span>'+ban+deny+badge+off+'</div>'
     +'<div class="gc-p">'+esc(n.product)+'</div>'
     +'<div class="pips">'+pips+'</div>'
     +'<div class="gc-f">'+(g.usageKnown?(n.free+' free / '+n.total):(n.total+' total'))+'</div>'
     +(n.extUsed?'<div class="gc-ext">'+n.extUsed+' in use by other workloads</div>':'')
     +uuids+'</div>';
 }).join('');
 el.innerHTML=head+'<div class="gcards">'+cards+'</div>'+legend;
}
function render(items){
 const tot=items.length, run=items.filter(i=>i.phase==='Running'&&i.ready).length,
   wait=items.filter(i=>!(i.phase==='Running'&&i.ready)&&i.phase!=='Failed').length,
   bad=items.filter(i=>i.phase==='Failed').length;
 $('#stats').innerHTML=
   stat('Total',tot,'')+stat('Running',run,'r')+stat('Pending',wait,'w')+stat('Failed',bad,'b');
 const tb=$('#rows');
 if(!items.length){tb.innerHTML='<tr><td colspan="7" class="empty">No instances. Click \u201c+ New instance\u201d.</td></tr>';return;}
 tb.innerHTML=items.map(r=>{
   const [c,t]=stClass(r);
   let ip=esc(r.ip);
   if(r.ip&&r.ip!=='-'&&r.adv!==r.ip)ip+=' <span class="tag">syncing</span>';
   else if(r.ip&&r.ip!=='-')ip+=' <button class="copy" onclick="copy(\''+esc(r.ip)+'\')">copy</button>';
   return '<tr>'
    +'<td><div class="nm">'+esc(r.name)+'</div>'+(r.owner?'<div class="sub">'+esc(r.owner)+'</div>':'')+'</td>'
    +'<td><span class="st '+c+'"><span class="dot"></span>'+esc(t)+(r.restarts?' \u00b7 '+r.restarts+'\u21bb':'')+'</span></td>'
    +'<td class="mono">'+esc(r.age||'-')+'</td>'
    +'<td class="mono">'+esc(r.node)+'</td>'
    +'<td class="mono" style="font-size:12px">'+esc(r.gpu)+'</td>'
    +'<td class="mono">'+ip+'</td>'
    +'<td><div class="row-actions">'
      +'<button onclick="openDrawer(\''+esc(r.name)+'\')">Details</button>'
      +(r.vscode?'<button class="vs" onclick="window.open(\''+esc(r.vscode)+'\',\'_blank\')" title="open bundled VSCode (password in Details)">VSCode</button>':'')
      +'<button class="danger" onclick="doDelete(\''+esc(r.name)+'\')">Delete</button>'
    +'</div></td></tr>';
 }).join('');
}
const stat=(l,n,k)=>'<div class="stat '+k+'"><div class="n">'+n+'</div><div class="l">'+l+'</div></div>';
function copy(t){
 // navigator.clipboard exists only in secure contexts (https/localhost); this UI is
 // served over plain http on the LAN, so fall back to a hidden textarea + execCommand.
 const ok=()=>toast('copied '+t,'ok'), fail=()=>toast('copy failed — '+t,'err');
 if(navigator.clipboard&&window.isSecureContext){
  navigator.clipboard.writeText(t).then(ok,()=>{legacyCopy(t)?ok():fail();});return;
 }
 legacyCopy(t)?ok():fail();
}
function legacyCopy(t){
 const ta=document.createElement('textarea');
 ta.value=t;ta.setAttribute('readonly','');
 ta.style.cssText='position:fixed;top:0;left:0;opacity:0';
 document.body.appendChild(ta);ta.focus();ta.select();
 let done=false;
 try{done=document.execCommand('copy');}catch(e){}
 document.body.removeChild(ta);
 return done;
}

async function openDrawer(name){
 $('#scrim').classList.add('on');$('#drawer').classList.add('on');
 $('#dTitle').innerHTML='<span class="st mut"><span class="dot"></span></span>'+esc(name);
 $('#dBody').innerHTML='<div class="empty">loading\u2026</div>';
 const d=await (await fetch('/api/instance?name='+encodeURIComponent(name),{cache:'no-store'})).json();
 if(d._error){$('#dBody').innerHTML='<div class="empty">not found</div>';return;}
 const [c,t]=stClass(d);
 $('#dTitle').innerHTML='<span class="st '+c+'"><span class="dot"></span></span>'+esc(d.name);
 const kv=o=>Object.entries(o).map(([k,v])=>'<div class="k">'+k+'</div><div class="v">'+esc(v||'-')+'</div>').join('');
 let html='<div class="kv">'+kv({
   'status':t+(d.restarts?'  ('+d.restarts+' restarts)':''),
   'created':d.created, 'age':d.age, 'owner':d.owner, 'created by':d.createdBy,
 })+'</div>';
 if(d.description)html+='<div class="sect">Description</div><div style="font-size:13px;white-space:pre-wrap">'+esc(d.description)+'</div>';
 html+='<div class="sect">Runtime</div><div class="kv">'+kv({
   'node':d.node,'gpu':d.gpu,'gpu UUID':d.gpuUUID||'-','image':d.image,'pod':d.podName,'pod IP':d.podIP,
   'stream IP':d.streamIP,'advertised':d.advertised,
 })+'</div>';
 if(d.ports&&d.ports.length)html+='<div class="sect">Ports</div><div class="kv">'+
   d.ports.map(p=>'<div class="k">'+esc(p.name)+'</div><div class="v">'+p.port+'/'+p.protocol+'</div>').join('')+'</div>';
 if(d.codeServerURL){
   html+='<div class="sect">VSCode (code-server)</div>'
    +'<div class="vscode">'
    +'<a class="vsbtn" href="'+esc(d.codeServerURL)+'" target="_blank" rel="noopener">Open VSCode \u2197</a>'
    +(d.codeServerPassword
       ?'<div class="vspw">password <code>'+esc(d.codeServerPassword)+'</code>'
         +'<button class="copy" onclick="copy(\''+esc(d.codeServerPassword)+'\')">copy</button></div>'
       :'')
    +(d.workspaceDir?'<div class="hint">editing <code>'+esc(d.workspaceDir)+'</code> \u00b7 shared live with the sim</div>':'')
    +'</div>';
 }
 html+='<div class="sect">Recent events</div>';
 html+=(d.events&&d.events.length)?d.events.slice().reverse().map(e=>
   '<div class="ev '+esc(e.type)+'"><span class="r">'+esc(e.reason)+'</span> <span style="color:var(--mut)">'+esc(e.time)+'</span>'
   +'<div class="m">'+esc(e.message)+'</div></div>').join('')
   :'<div class="hint">no events</div>';
 $('#dBody').innerHTML=html;
}
function closeDrawer(){$('#scrim').classList.remove('on');$('#drawer').classList.remove('on');}

function openBans(){$('#banModal').classList.add('on');banFormSync();loadBans();}
function closeBans(){$('#banModal').classList.remove('on');}
function banFormSync(){
 const k=$('#bKind').value;
 $('#bfNode').style.display=(k==='node'||k==='gpu')?'':'none';
 $('#bfProduct').style.display=(k==='product')?'':'none';
 $('#bfUuid').style.display=(k==='gpu')?'':'none';
 $('#bHint').textContent=k==='gpu'
   ?'With DRA (default): enforced at schedule time \u2014 the UUID goes into every new instance\u2019s ResourceClaim CEL deny-list. Without DRA it is display-only unless you exclude the UUID node-side and press \u201capplied\u201d.'
   :k==='product'?'case-insensitive substring, matched per GPU against the DRA productName attribute (A100 hits NVIDIA A100-PCIE-40GB); node labels are not used'
   :'node is removed from every new instance\u2019s nodeAffinity';
 banFillPickers();
}
function banFillPickers(){
 // datalists from the live DRA inventory (/api/gpu devices) - pick, don't type
 if(!_gpu||!_gpu.nodes)return;
 const nl=$('#nodeList'), ul=$('#uuidList'), pl=$('#productList');
 if(nl)nl.innerHTML=_gpu.nodes.map(n=>'<option value="'+esc(n.node)+'">'
   +esc(n.product)+'</option>').join('');
 if(pl){
  const ps={};
  _gpu.nodes.forEach(n=>(n.devices||[]).forEach(d=>{if(d.product)ps[d.product]=1;}));
  pl.innerHTML=Object.keys(ps).sort().map(p=>'<option value="'+esc(p)+'"></option>').join('');
 }
 if(ul){
  const node=$('#bNode').value.trim();
  const rows=[];
  _gpu.nodes.forEach(n=>{
    if(node&&n.node!==node)return;
    (n.devices||[]).forEach(d=>{
      rows.push('<option value="'+esc(d.uuid)+'">'+esc(d.product||'?')+' \u00b7 '+esc(n.node)
        +(d.banned?' \u00b7 already banned':'')+(d.denied?' \u00b7 product-denied':'')+'</option>');
    });
  });
  ul.innerHTML=rows.join('');
 }
}
async function loadBans(){
 const d=await (await fetch('/api/bans',{cache:'no-store'})).json();
 const el=$('#banList');
 if(!d.ok){el.innerHTML='<div class="hint">ban store unavailable ('+esc(d.store)+')</div>';return;}
 if(!d.bans.length){el.innerHTML='<div class="hint">no bans \u00b7 store: '+esc(d.store)+'</div>';return;}
 el.innerHTML=d.bans.map(b=>{
   const tgt=b.kind==='node'?b.node:b.kind==='product'?b.product:b.node+' \u00b7 '+b.uuid+(b.index!=null&&b.index!==''?' (#'+b.index+')':'');
   const ap=b.kind==='gpu'?(b.applied
     ?'<span class="applied">applied</span><button onclick="banApplied(\''+b.id+'\',false)">undo</button>'
     :'<span class="pending">pending</span><button onclick="banApplied(\''+b.id+'\',true)" title="node-side device-plugin exclusion done">applied</button>'):'';
   return '<div class="banrow"><span class="bk">'+esc(b.kind)+'</span><span class="bt">'+esc(tgt)
     +(b.reason?'<br><span class="br">'+esc(b.reason)+'</span>':'')+'</span>'+ap
     +'<button class="danger" onclick="doUnban(\''+b.id+'\')">remove</button></div>';
 }).join('');
}
async function submitBan(){
 const k=$('#bKind').value;
 const body={kind:k,node:$('#bNode').value.trim(),product:$('#bProduct').value.trim(),
   uuid:$('#bUuid').value.trim(),index:$('#bIndex').value.trim(),reason:$('#bReason').value.trim()};
 $('#bGo').disabled=true;
 const r=await (await fetch('/api/ban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
 $('#bGo').disabled=false;
 toast(r.msg||(r.ok?'banned':'failed'),r.ok?'ok':'err');
 if(r.ok){$('#bNode').value='';$('#bProduct').value='';$('#bUuid').value='';$('#bIndex').value='';$('#bReason').value='';loadBans();refresh();}
}
async function doUnban(id){
 const r=await (await fetch('/api/unban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})).json();
 toast(r.msg||'removed',r.ok?'ok':'err');loadBans();refresh();
}
async function banApplied(id,applied){
 const r=await (await fetch('/api/ban-applied',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,applied})})).json();
 toast(r.msg||'updated',r.ok?'ok':'err');loadBans();refresh();
}

// ---- metrics dashboard (network) ----
let _metrics=null, _metricsWindow=3600;
function openMetrics(){$('#metricsModal').classList.add('on');loadMetrics(_metricsWindow);}
function closeMetrics(){$('#metricsModal').classList.remove('on');}
function fmtBps(b){const u=['B/s','KB/s','MB/s','GB/s'];let i=0;b=+b||0;
 while(b>=1024&&i<u.length-1){b/=1024;i++;}return (b<10&&i>0?b.toFixed(1):Math.round(b))+' '+u[i];}
async function loadMetrics(w){
 _metricsWindow=w;
 document.querySelectorAll('#metricsModal .mrange button[data-w]').forEach(b=>b.classList.toggle('on',+b.dataset.w===w));
 $('#metricsBody').innerHTML='<div class="empty">loading\u2026</div>';
 let d; try{d=await (await fetch('/api/metrics?window='+w,{cache:'no-store'})).json();}
 catch(e){d={available:false,reason:'request failed'};}
 _metrics=d; renderMetrics(d);
}
function sparkline(tx,rx){
 const W=300,H=64,p=4, all=tx.concat(rx);
 if(!all.length)return '<div class="hint">no data in window</div>';
 const ts=all.map(a=>a[0]), t0=Math.min.apply(null,ts), t1=Math.max.apply(null,ts);
 const max=Math.max(1,Math.max.apply(null,all.map(a=>a[1])));
 const X=t=>p+(t1>t0?(t-t0)/(t1-t0):0)*(W-2*p), Y=v=>H-p-(v/max)*(H-2*p);
 const d=pts=>pts.length?'M'+pts.map(a=>X(a[0]).toFixed(1)+' '+Y(a[1]).toFixed(1)).join(' L '):'';
 return '<svg class="spark" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'
   +'<path class="l-tx" d="'+d(tx)+'"/><path class="l-rx" d="'+d(rx)+'"/></svg>'
   +'<div class="mc-leg"><span class="lt">\u2191 tx</span><span class="lr">\u2193 rx</span>'
   +'<span class="mut">peak '+fmtBps(max)+'</span></div>';
}
function renderMetrics(d){
 const el=$('#metricsBody');
 if(!d||!d.available){
   el.innerHTML='<div class="hint">\uba54\ud2b8\ub9ad\uc744 \ubd88\ub7ec\uc62c \uc218 \uc5c6\uc2b5\ub2c8\ub2e4 \u2014 Prometheus \ubbf8\uc5f0\uacb0 \ub610\ub294 \uc218\uc9d1 \ub370\uc774\ud130 \uc5c6\uc74c. (\uc218\uc9d1\uae30\uac00 \uc548 \ub3cc\uc544\ub3c4 \uc778\uc2a4\ud134\uc2a4\ub294 \uc815\uc0c1 \ub3d9\uc791\ud569\ub2c8\ub2e4.)'
     +(d&&d.reason?'<br><span class="mono" style="font-size:11px;color:var(--mut)">'+esc(d.reason)+'</span>':'')+'</div>';
   return;
 }
 if(!d.instances||!d.instances.length){
   el.innerHTML='<div class="hint">\uc544\uc9c1 \uc218\uc9d1\ub41c \ub370\uc774\ud130\uac00 \uc5c6\uc2b5\ub2c8\ub2e4 \u2014 \uc778\uc2a4\ud134\uc2a4 \uc0dd\uc131 \ud6c4 \uba87 \ubd84 \ub4a4 \ub2e4\uc2dc \ud655\uc778\ud558\uc138\uc694.</div>';return;
 }
 el.innerHTML='<div class="mcards">'+d.instances.map(m=>{
   const lt=m.tx.length?m.tx[m.tx.length-1][1]:0, lr=m.rx.length?m.rx[m.rx.length-1][1]:0;
   return '<div class="mcard"><div class="mc-h"><span class="mc-n">'+esc(m.app)+'</span>'
     +(m.owner?'<span class="mc-o">'+esc(m.owner)+'</span>':'')+'</div>'
     +'<div class="mc-now">\u2191 '+fmtBps(lt)+' &middot; \u2193 '+fmtBps(lr)+'</div>'
     +sparkline(m.tx,m.rx)+'</div>';
 }).join('')+'</div>';
}
function exportMetrics(fmt){
 if(!_metrics||!_metrics.available||!_metrics.instances||!_metrics.instances.length){toast('no data to export','err');return;}
 let blob,name;
 if(fmt==='json'){blob=new Blob([JSON.stringify(_metrics,null,2)],{type:'application/json'});name='isaac-metrics.json';}
 else{
   const rows=[['timestamp_iso','app','owner','tx_bytes_per_s','rx_bytes_per_s']];
   _metrics.instances.forEach(m=>{
     const rx={}; m.rx.forEach(pt=>rx[pt[0]]=pt[1]);
     m.tx.forEach(pt=>rows.push([new Date(pt[0]*1000).toISOString(),m.app,m.owner||'',pt[1],rx[pt[0]]!=null?rx[pt[0]]:'']));
   });
   const csv=rows.map(r=>r.map(c=>{c=String(c);return /[",\n]/.test(c)?'"'+c.replace(/"/g,'""')+'"':c;}).join(',')).join('\n');
   blob=new Blob([csv],{type:'text/csv;charset=utf-8'});name='isaac-metrics.csv';
 }
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;
 document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
 toast('exported '+name,'ok');
}

// ---- scene load history (which USD stage stressed which GPU) ----
function openScenes(){$('#sceneModal').classList.add('on');loadScenes();}
function closeScenes(){$('#sceneModal').classList.remove('on');}
const pct=v=>v==null?'-':(+v).toFixed(0)+'%';
const gib=v=>v==null?'-':((+v)/1024).toFixed(1)+' GiB';
async function loadScenes(){
 let d; try{d=await (await fetch('/api/scenes',{cache:'no-store'})).json();}
 catch(e){d={available:false};}
 const agg=$('#sceneAgg'), ses=$('#sceneSessions');
 if(!d||!d.available){agg.innerHTML='<div class="hint">scene store unavailable</div>';ses.innerHTML='';return;}
 agg.innerHTML=d.byScene.length?'<table class="ctab"><thead><tr><th>scene</th><th>GPU model</th>'
   +'<th class="num">runs</th><th class="num">util avg</th><th class="num">util p95</th>'
   +'<th class="num">util max</th><th class="num">NVENC max</th><th class="num">VRAM max</th></tr></thead><tbody>'
   +d.byScene.map(a=>'<tr><td class="mono pn" title="'+esc(a.stage)+'">'+esc(a.stageShort)+'</td>'
     +'<td class="mono">'+esc(a.gpuModel)+'</td><td class="num mono">'+a.n+'</td>'
     +'<td class="num mono">'+pct(a.utilAvg)+'</td><td class="num mono">'+pct(a.utilP95)+'</td>'
     +'<td class="num mono">'+pct(a.utilMax)+'</td><td class="num mono">'+pct(a.encMax)+'</td>'
     +'<td class="num mono">'+gib(a.fbMaxMiB)+'</td></tr>').join('')+'</tbody></table>'
   :'<div class="hint">아직 기록 없음 — 6.0+ 이미지 인스턴스에서 USD를 열면 자동 기록됩니다.</div>';
 ses.innerHTML=d.sessions.length?'<table class="ctab"><thead><tr><th>scene</th><th>instance</th><th>GPU</th>'
   +'<th class="num">util avg/max</th><th class="num">VRAM max</th><th>start</th><th></th></tr></thead><tbody>'
   +d.sessions.slice(0,30).map(s=>{const st=s.stats||{};
     return '<tr><td class="mono pn" title="'+esc(s.stage)+'">'+esc(s.stageShort)+'</td>'
     +'<td class="mono">'+esc(s.instance)+'</td><td class="mono" style="font-size:11px">'+esc(s.gpuModel||'-')+'</td>'
     +'<td class="num mono">'+pct(st.utilAvg)+' / '+pct(st.utilMax)+'</td>'
     +'<td class="num mono">'+gib(st.fbMaxMiB)+'</td>'
     +'<td class="mono" style="font-size:11px">'+esc((s.start||'').replace('T',' ').replace('Z',''))+'</td>'
     +'<td>'+(s.open?'<span class="tag">open</span>':'')+'</td></tr>';}).join('')+'</tbody></table>'
   :'<div class="hint">no sessions</div>';
}
function openCreate(){$('#modal').classList.add('on');$('#mName').focus();loadImages();}
function closeCreate(){$('#modal').classList.remove('on');}
// ---- image catalog (registry) for the Create modal ----
const shortImg=ref=>esc((ref||'').split('/').pop());   // 10.38.../dt-saas/isaac-sim:6.0 -> isaac-sim:6.0
async function loadImages(){
 const sel=$('#mImage'), hint=$('#mImageHint');
 let d; try{d=await (await fetch('/api/images',{cache:'no-store'})).json();}
 catch(e){d={available:false,reason:'request failed'};}
 if(!d||!d.available){
   sel.innerHTML='<option value="">'+shortImg(d&&d.default||'default')+' (default)</option>';
   hint.textContent='registry unreachable — default image only'+(d&&d.reason?' · '+d.reason:'');
   return;
 }
 sel.innerHTML=d.images.map(i=>'<option value="'+esc(i.image)+'"'+(i.image===d.default?' selected':'')
   +' title="'+esc(i.image)+'">'+shortImg(i.image)+(i.image===d.default?' · default':'')+'</option>').join('');
 hint.textContent=d.images.length+' image(s) · source: '+d.source;
}
async function submitCreate(){
 const name=$('#mName').value.trim();if(!name){toast('enter a name','err');return;}
 $('#mGo').disabled=true;
 const body={name,owner:$('#mOwner').value.trim(),description:$('#mDesc').value.trim(),
   image:$('#mImage').value};
 const r=await (await fetch('/api/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
 $('#mGo').disabled=false;
 if(r.ok){toast(r.msg,'ok');$('#mName').value='';$('#mOwner').value='';$('#mDesc').value='';closeCreate();refresh();}
 else toast(r.msg||'create failed','err');
}
async function doDelete(name){
 if(!confirm('Delete instance "'+name+'"? This removes its Deployment and Service.'))return;
 const r=await (await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})})).json();
 toast(r.msg||'deleted',r.ok?'ok':'err');refresh();
}
async function doPrune(){
 const r=await (await fetch('/api/prune',{method:'POST'})).json();toast(r.msg||'pruned',r.ok?'ok':'err');refresh();
}
$('#live').onclick=()=>{auto=!auto;$('#live').classList.toggle('off',!auto);$('#liveTxt').textContent=auto?'live \u00b7 10s':'paused';
 if(auto)tick();else clearInterval(timer);};
function tick(){clearInterval(timer);timer=setInterval(refresh,10000);}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeDrawer();closeCreate();closeBans();closeMetrics();closeScenes();}});
refresh();tick();
