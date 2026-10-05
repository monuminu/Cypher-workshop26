const $ = (q, root=document) => root.querySelector(q);
const examples = {
 slides: 'Create a polished 6-slide PowerPoint explaining how an enterprise should evaluate an AI agent before production. Include a title, failure modes, an evaluation approach, a concrete example, governance, and a closing checklist. Save a real .pptx in outputs/. Reopen it and check slide count, text, and layout bounds. Explain which checks you performed and any limitations.',
 excel: 'Create an Excel workbook for tracking an enterprise AI pilot. Use clearly labelled illustrative data for six workstreams, owners, milestones, risks, and readiness. Include a useful overview and formulas where appropriate. Format it for a leadership review. Save a real .xlsx in outputs/, reopen it, and check your work. Do not claim the illustrative data is real.',
 agenda: 'Using the schedule.json I attach, curate a personal conference agenda for an enterprise AI engineer interested in production agents, evaluation, and governance. Use an attendance date present in the source, explain your choice, and include a lunch break and a five-minute buffer between different halls. Do not invent sessions or access rules. Create an Excel workbook with my agenda, alternatives, preferences, and checks/sources. Reopen it and check overlaps, hall transitions, and missing information. Save it in outputs/.'
};
let runId=null, cursor=-1, busy=false, polling=false, eventSource=null;
const chats={basic:{messages:new Map(),tools:new Map()},harness:{messages:new Map(),tools:new Map()}};
const headers={'X-Opening-Demo':'1'};
async function request(url, options={}) {
 const response=await fetch(url,{...options,headers:{...headers,...options.headers}});
 if(!response.ok) { let data; try {data=await response.json();} catch {data={detail:response.statusText};} throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail)); }
 return response.json();
}
function error(message='') { $('#error').textContent=message; $('#error').hidden=!message; }
function controls(active) { busy=active; $('#modelChoice').disabled=active; $('#run').disabled=active; $('#stop').disabled=!active; $('#continue').disabled=active||!runId; }
function reset(id) {
 eventSource?.close(); eventSource=null;
 runId=id; cursor=-1; localStorage.setItem('opening-demo-run',id); $('#runId').textContent=`Run ${id}`;
 for(const name of ['basic','harness']) { const panel=$('#'+name); $('.activity',panel).replaceChildren(); $('.answer',panel).textContent=''; $('.files',panel).replaceChildren(); $('.side-error',panel).hidden=true; chats[name]={messages:new Map(),tools:new Map()}; }
 $('#harness .todos').hidden=true;
}
function node(tag,cls,text=''){const el=document.createElement(tag);el.className=cls;el.textContent=text;return el;}
function bubble(area,role,label){const row=node('div','chat-message '+role);row.append(node('div','chat-label',label));const body=node('div','chat-text');row.append(body);area.append(row);return {row,body};}
function toolCard(area,event){const row=node('details','chat-tool');const summary=node('summary','');const title=node('span','tool-name',event.name||'Tool call');const status=node('span','tool-state','Preparing');summary.append(title,status);const args=node('pre','tool-arguments');row.append(summary,args);area.append(row);return {row,title,status,args,name:event.name,message:event.message_id,started:false};}
function chatEvent(event,name){
 const area=$(`#${name} .activity`), state=chats[name];
 const follow=area.scrollHeight-area.scrollTop-area.clientHeight<100;
 const label=event.actor==='helper'?'Helper agent':name==='basic'?'Basic agent':'Harness agent';
 if(event.kind==='prompt'){bubble(area,'user','You').body.textContent=event.text;}
 else if(['model','text_delta','message_end'].includes(event.kind)){
  const key=event.message_id||'legacy-'+event.id;
  let message=state.messages.get(key);
  if(!message){message=bubble(area,'assistant',label);message.row.classList.add('streaming');message.body.dataset.placeholder='Generating…';state.messages.set(key,message);}
  if(event.kind==='text_delta'){message.body.append(document.createTextNode(event.text));delete message.body.dataset.placeholder;}
  if(event.kind==='message_end'){message.row.classList.remove('streaming');if(!message.body.textContent)message.row.hidden=true;}
 }
 else if(['tool_delta','tool_start','tool_end','tool_error','approval'].includes(event.kind)){
  const key=event.tool_id||`${event.message_id}:${event.call_id||event.name}`;
  let card=state.tools.get(key);
  if(!card&&event.kind==='tool_start')card=[...new Set(state.tools.values())].find(c=>!c.started&&c.message===event.message_id&&c.name===event.name);
  if(!card){card=toolCard(area,event);}state.tools.set(key,card);
  if(event.name){card.name=event.name;card.title.textContent=event.name+(event.actor==='helper'?' · helper':'');}
  if(event.kind==='tool_delta'){card.args.append(document.createTextNode(event.text||''));}
  if(event.kind==='tool_start'){card.started=true;card.row.classList.add('running');card.status.textContent='Running';card.args.textContent=JSON.stringify(event.arguments,null,2);}
  if(event.kind==='tool_end'||event.kind==='tool_error'){card.row.classList.remove('running');card.status.textContent=event.kind==='tool_error'?'Error':'Returned';let output=$('.tool-result',card.row);if(!output){output=node('pre','tool-result');card.row.append(node('div','tool-result-label','Result'),output);}output.textContent=event.result||event.text||'';}
  if(event.kind==='approval'){
   card.row.dataset.approval=event.approval_id;card.status.textContent='Awaiting approval';card.row.open=true;
   const actions=node('div','tool-actions');
   for(const [title,allow] of [['Allow',true],['Decline',false]]){const button=node('button','',title);button.onclick=async()=>{try{await request(`/api/runs/${runId}/approve/${event.approval_id}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({allow})});for(const b of actions.querySelectorAll('button'))b.disabled=true;}catch(e){error(e.message)}};actions.append(button);}card.row.append(actions);
  }
 }
 else if(event.kind==='message'){bubble(area,'assistant',label).body.textContent=event.text;}
 else if(event.kind==='answer'&&state.messages.size===0){bubble(area,'assistant',label).body.textContent=event.text;}
 else if(event.kind==='status'){
  if(event.status!=='running'){
   for(const message of state.messages.values()){message.row.classList.remove('streaming');if(!message.body.textContent)message.row.hidden=true;}
   for(const card of new Set(state.tools.values()))if(card.row.classList.contains('running')){card.row.classList.remove('running');card.status.textContent='Interrupted';}
  }
  area.append(node('div','chat-status',event.status==='running'?'Turn started':event.status));
 }
 if(follow)area.scrollTop=area.scrollHeight;
}
function receive(event){if(event.id<=cursor)return;for(const name of event.side==='both'?['basic','harness']:[event.side])chatEvent(event,name);cursor=event.id;}
function render(data) {
 controls(data.busy);
 for(const event of data.events||[])receive(event);
 for(const [name,state] of Object.entries(data.sides)) {
  const panel=$('#'+name), status=$('.status',panel);status.textContent=state.status;status.className='status '+state.status.replaceAll(' ','-');
  $('.calls',panel).textContent=state.model_calls??0;$('.tools',panel).textContent=state.tool_calls??0;
  $('.answer',panel).textContent=state.answer||'Waiting for the first text from the model…';
  $('.side-error',panel).textContent=state.error||'';$('.side-error',panel).hidden=!state.error;
  const list=$('.files',panel);list.replaceChildren();$('.file-count',panel).textContent=state.files.length;
  if(!state.files.length){const p=document.createElement('p');p.textContent='No output files yet. Generated files appear here when saved in outputs/.';list.append(p);}
  for(const file of state.files){const a=document.createElement('a');a.href=`/api/runs/${runId}/files/${name}/`+file.name.split('/').map(encodeURIComponent).join('/');a.download=file.name;const label=document.createElement('span');label.textContent='↓  '+file.name;const size=document.createElement('small');size.textContent=(file.bytes/1024).toFixed(1)+' KB';a.append(label,size);list.append(a);}
  if(name==='harness') { const todos=$('.todos',panel);todos.replaceChildren();todos.hidden=!state.todos?.length;for(const todo of state.todos||[]){const row=document.createElement('div');row.textContent=(todo.complete?'✓  ':'○  ')+todo.title;todos.append(row);}for(const row of panel.querySelectorAll('[data-approval]')){if(!state.pending_approvals?.includes(row.dataset.approval))for(const button of row.querySelectorAll('button'))button.disabled=true;} }
 }
 $('#providers').textContent='Harness context providers: '+(data.sides.harness.providers||[]).join(', ');
 $('#model').textContent=data.config.model;$('#provider').textContent=data.config.provider+' · same configuration on both sides';
}
function connect(){
 if(!runId)return;eventSource?.close();const id=runId;
 const source=new EventSource(`/api/runs/${id}/stream?after=${cursor}`);eventSource=source;
 source.addEventListener('activity',e=>{if(runId===id)receive(JSON.parse(e.data));});
 source.addEventListener('snapshot',e=>{if(runId===id)render(JSON.parse(e.data));});
 source.addEventListener('idle',()=>{source.close();if(eventSource===source)eventSource=null;});
 source.onerror=()=>{if(eventSource===source)$('#runId').textContent=`Run ${id} · reconnecting…`;};
 source.onopen=()=>{if(runId===id)$('#runId').textContent=`Run ${id} · live`;};
}
async function poll(){if(!runId||polling)return;polling=true;try{render(await request(`/api/runs/${runId}?after=${cursor}`));if(busy&&!eventSource)connect();}catch(e){error(e.message);controls(false);}finally{polling=false;}}
async function config(){const data=await request('/api/config');$('#model').textContent=data.model;$('#provider').textContent=data.provider+' · same configuration on both sides';const models=$('#modelChoice');models.replaceChildren();for(const model of data.models)models.add(new Option(model.label,model.value));$('#skills').textContent='Harness skills available: '+data.skills.join(', ');const select=$('#recent');select.replaceChildren(new Option('Select a run…',''));for(const run of data.recent)select.add(new Option(run.prompt.slice(0,55),run.id));}
$('#run').onclick=async()=>{error();const prompt=$('#prompt').value.trim();if(!prompt)return error('Enter a task for both agents.');controls(true);const body=new FormData();body.set('prompt',prompt);body.set('model',$('#modelChoice').value);body.set('max_calls',$('#maxCalls').value);body.set('mode',$('#mode').value);body.set('ask_tools',$('#askTools').checked);body.set('web_search',$('#webSearch').checked);for(const file of $('#files').files)body.append('files',file);try{const data=await request('/api/runs',{method:'POST',body});reset(data.id);await poll();}catch(e){error(e.message);controls(false);}};
$('#stop').onclick=async()=>{try{await request(`/api/runs/${runId}/stop`,{method:'POST'});await poll();}catch(e){error(e.message);}};
$('#continue').onclick=async()=>{const prompt=$('#followup').value.trim();if(!prompt)return error('Enter a follow-up task.');error();controls(true);try{await request(`/api/runs/${runId}/continue`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,mode:$('#mode').value})});$('#followup').value='';await poll();}catch(e){error(e.message);controls(false);}};
$('#recent').onchange=async e=>{if(!e.target.value)return;if(busy)return error('Stop or finish the active comparison before switching runs.');reset(e.target.value);await poll();};
$('#files').onchange=()=>{$('#fileNames').textContent=[...$('#files').files].map(f=>f.name).join(', ')||'Same files copied to both workspaces';};
for(const button of document.querySelectorAll('[data-example]'))button.onclick=()=>{$('#prompt').value=examples[button.dataset.example];$('#prompt').focus();};
for(const button of document.querySelectorAll('[data-tab]'))button.onclick=()=>{const panel=button.closest('.agent');for(const b of panel.querySelectorAll('[data-tab]'))b.classList.toggle('selected',b===button);for(const pane of panel.querySelectorAll('.pane'))pane.hidden=!pane.classList.contains(button.dataset.tab);};
config().then(async()=>{const previous=localStorage.getItem('opening-demo-run');if(previous){reset(previous);await poll();}}).catch(e=>error(e.message));
// Text/tool deltas use SSE. Snapshots support initial/replayed runs; no fake typing timer.
