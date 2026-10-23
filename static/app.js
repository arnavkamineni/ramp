const $ = id => document.getElementById(id);
let state = {requests: [], results: [], documents: [], ledger: [], approvals: {}, filter: 'all', csv: ''};
const labels = {ready:'Evidence ready', needs_review:'Needs judgment', missing:'Missing evidence', approved:'Approved'};
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toCSV(rows) { return 'id,request,owner\n' + rows.map(r => [r.id,r.request,r.owner].map(v => '"'+String(v).replaceAll('"','""')+'"').join(',')).join('\n'); }
function toast(message) { $('message').textContent=message; $('message').style.display='block'; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('message').style.display='none',6000); }
async function api(path, payload) {
 const response = await fetch(path, payload ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)} : {});
 if(!response.ok) {const error=await response.json();throw Error(error.error || 'Request failed');} return response;
}
function download(blob,name) {const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function render() {
 const counts={ready:0,needs_review:0,missing:0};state.results.forEach(r=>counts[r.status]++);
 $('total').textContent=state.results.length;$('count').textContent=state.results.length;$('ready').textContent=counts.ready;$('judgment').textContent=counts.needs_review;$('missing').textContent=counts.missing;
 const approved=Object.values(state.approvals).filter(Boolean).length;
 $('progress-label').textContent=`${counts.ready} of ${state.results.length} requests have ready evidence · ${approved} reviewer-approved`;
 $('progress').style.width=(counts.ready/Math.max(1,state.results.length)*100)+'%';
 const query=$('search').value.toLowerCase();
 const rows=state.results.filter(r=>(state.filter==='all'||r.status===state.filter)&&(r.request+' '+r.id+' '+r.owner).toLowerCase().includes(query));
 $('rows').innerHTML=rows.map(r=>`<tr><td><small>${esc(r.id)}</small><strong>${esc(r.request)}</strong></td><td>${esc(r.owner)}</td><td>${r.evidence.length} source${r.evidence.length===1?'':'s'}${r.population?`<br><small>${r.population.matched}/${r.population.total} covered</small>`:''}</td><td><span class="badge ${state.approvals[r.id]?'approved':r.status}">${labels[state.approvals[r.id]?'approved':r.status]}</span></td><td><button class="review" data-id="${esc(r.id)}">Review →</button></td></tr>`).join('')||'<tr><td colspan="5" class="empty">No matching requests.</td></tr>';
 document.querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>detail(b.dataset.id));
}
function sourceHTML(e) {
 const d=state.documents.find(d=>d.id===e.document_id);if(!d)return '';
 const parts=d.text.split(e.highlight);
 return `<details class="evidence"><summary>${esc(d.name)} · ${esc(d.id)}</summary><p>${esc(e.reason)}</p><pre>${parts.map(esc).join('<mark>'+esc(e.highlight)+'</mark>')}</pre></details>`;
}
function detail(id) {
 const r=state.results.find(r=>r.id===id);$('detail-id').textContent=r.id;$('detail-title').textContent=r.request;
 $('detail-body').innerHTML=`<div class="detail-section"><span class="badge ${r.status}">${labels[r.status]}</span><p>${esc(r.explanation)}</p>${r.population?`<p><strong>Coverage: ${r.population.matched} / ${r.population.total}</strong><br>${esc(r.population.basis)}</p>`:''}</div>${r.missing.length?`<div class="detail-section"><h3>What’s still missing</h3>${r.missing.map(m=>`<div class="gap">${esc(m)}</div>`).join('')}<p>Follow-up owner: <strong>${esc(r.owner)}</strong></p></div>`:''}<div class="detail-section"><h3>Source evidence · ${r.evidence.length} documents</h3>${r.evidence.map(sourceHTML).join('')||'<p>No supporting documents found.</p>'}</div><div class="approval">${r.status==='ready'?`<label><input type="checkbox" id="ack" ${state.approvals[id]?'checked':''}> I reviewed the source evidence and confirmed the requested period and scope.</label><button class="primary" id="approve">${state.approvals[id]?'Revoke approval':'Approve evidence'}</button><p><small>Approval lasts for this page session. No authenticated audit trail in this prototype.</small></p>`:'<strong>Approval blocked</strong><p>Resolve missing support or judgment items before approving. This prototype cannot upload replacement evidence.</p>'}</div>`;
 if(r.status==='ready') {
  const button=$('approve');button.disabled=!state.approvals[id];
  $('ack').onchange=()=>button.disabled=!state.approvals[id]&&!$('ack').checked;
  button.onclick=()=>{state.approvals[id]=!state.approvals[id];render();detail(id);toast(state.approvals[id]?'Evidence approved for this demo session.':'Approval revoked.');};
 }
 if(!$('detail').open)$('detail').showModal();
}
async function loadDemo() {
 const data=await (await api('/api/demo')).json();Object.assign(state,data,{approvals:{},csv:toCSV(data.requests)});render();
}
$('close').onclick=()=>$('detail').close();
$('detail').onclick=e=>{if(e.target===$('detail')){const r=$('detail').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('detail').close();}};
$('search').oninput=render;
 document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{state.filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('selected',x===b));render();});
$('upload').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>900000)throw Error('Please use a CSV smaller than 900 KB.');const csv=await file.text();const data=await(await api('/api/analyze',{csv})).json();Object.assign(state,data,{csv,approvals:{}});render();toast('Requests imported and checked against the demo corpus.');}catch(e){toast(e.message);}finally{$('upload').value='';}};
$('sample').onclick=()=>download(new Blob([toCSV([{id:'PBC-01',request:'All invoices over $10,000 from Q3 2026',owner:'Accounts payable'},{id:'PBC-02',request:'September 2026 operating bank statement',owner:'Treasury'}])],{type:'text/csv'}),'sample-requests.csv');
$('reset').onclick=async()=>{try{await loadDemo();toast('Demo requests restored.');}catch(e){toast(e.message);}};
$('export').onclick=async()=>{const b=$('export');b.disabled=true;try{const response=await api('/api/export',{csv:state.csv,approvals:state.approvals});download(await response.blob(),'auditready-evidence.zip');toast('Exported sources, index, and all unresolved gaps.');}catch(e){toast(e.message);}finally{b.disabled=false;}};
$('corpus').onclick=()=>{$('detail-id').textContent='SOURCE CORPUS';$('detail-title').textContent='8 documents. One visible evidence trail.';$('detail-body').innerHTML='<p>All documents and ledger entries are synthetic. The quote is deliberately excluded from invoice matching.</p>'+state.documents.map(d=>`<details class="evidence"><summary>${esc(d.name)} · ${esc(d.type)}</summary><pre>${esc(d.text)}</pre></details>`).join('')+'<h3>Ledger population</h3><pre>'+esc(state.ledger.map(t=>`${t.id}  ${t.date}  ${t.vendor}  $${t.amount.toLocaleString()}`).join('\n'))+'</pre>';$('detail').showModal();};
loadDemo().catch(e=>toast('Could not load demo: '+e.message));
