// Live race UI: streams both agents over SSE and renders the reveal.
const $ = (s, el = document) => el.querySelector(s);
const SIDES = { baseline: "a", harness: "b" };
const DAY_START = 10 * 60, DAY_END = 21 * 60;

let META = null, persona = "engineer", source = null;
let lanes = {}, finals = {};

init();

async function init() {
  META = await (await fetch("/api/meta")).json();
  $("#sessionCount").textContent = META.sessions.length;
  $("#source").innerHTML = `Agenda: <a href="${META.source}">${META.source.replace("https://", "")}</a>, snapshot ${META.snapshot_at.slice(0, 10)}.`;
  const box = $("#personas");
  for (const [k, p] of Object.entries(META.personas)) {
    const b = document.createElement("button");
    b.className = "persona"; b.setAttribute("role", "radio"); b.dataset.k = k;
    b.innerHTML = `<strong>${p.name}</strong><small>${p.role.split(" at ")[0].split(" of ")[0]}</small>`;
    b.onclick = () => selectPersona(k);
    box.append(b);
  }
  selectPersona(persona);
  loadRecordings();
  $("#startBtn").onclick = startLive;
  $("#replaySel").onchange = e => e.target.value && startReplay(e.target.value);
}

async function loadRecordings() {
  const recs = await (await fetch("/api/recordings")).json();
  const sel = $("#replaySel");
  sel.length = 1;
  for (const r of recs) {
    const o = document.createElement("option");
    o.value = r.name;
    o.textContent = `${META.personas[r.persona]?.name ?? r.persona}, ${r.name.slice(r.persona.length + 1)} (plain ${r.seconds.baseline ?? "–"}s / harness ${r.seconds.harness ?? "–"}s)`;
    sel.append(o);
  }
}

function selectPersona(k) {
  persona = k;
  document.querySelectorAll(".persona").forEach(b => b.setAttribute("aria-checked", b.dataset.k === k));
  const p = META.personas[k];
  $("#brief").innerHTML = `<b>${p.name}, ${p.role}.</b> ${p.blurb}<br>` +
    p.commitments.map(c => `<span class="commit">Day ${c.day} ${c.start}–${c.end}: ${c.what}</span>`).join("") +
    `<br>Must attend: ${p.must_attend.map(id => `<b>${title(id)}</b>`).join(", ")}` +
    `<br><span class="mem">In the harness's memory from a previous chat: ${esc(p.memory.note.split("\n\n").slice(1).join(" "))}</span>`;
}

const title = id => (META.sessions.find(s => s.id === id) || {}).title || id;

// ---------- race control ----------
async function startLive() {
  reset();
  $("#startBtn").disabled = true;
  const { run_id } = await (await fetch("/api/race", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ persona }) })).json();
  listen(`/api/stream/${run_id}`);
}

function startReplay(name) {
  const p = name.split("-")[0];
  if (META.personas[p]) selectPersona(p);
  reset();
  listen(`/api/replay/${name}?speed=${$("#speedSel").value}`);
}

let ticker;
function listen(url) {
  source?.close();
  const started = performance.now(), speed = url.includes("/replay/") ? +$("#speedSel").value : 1;
  clearInterval(ticker);
  ticker = setInterval(() => {
    for (const [side, L] of Object.entries(lanes)) {
      if (!L.running) continue;
      const v = $(".metric .v", L.el);
      if (v) v.textContent = `${Math.max(L.t, (performance.now() - started) / 1000 * speed).toFixed(0)}s`;
    }
  }, 250);
  source = new EventSource(url);
  source.onmessage = e => handle(JSON.parse(e.data));
  source.addEventListener("end", () => { source.close(); clearInterval(ticker); $("#startBtn").disabled = false; loadRecordings(); });
  source.onerror = () => { $("#startBtn").disabled = false; };
}

function reset() {
  finals = {};
  $("#results").hidden = true;
  for (const side of Object.keys(SIDES)) {
    const el = $(`#lane-${side}`);
    lanes[side] = { el, trace: $("[data-trace]", el), m: {}, t: 0, running: true, loops: 0 };
    $("[data-trace]", el).innerHTML = "";
    renderMetrics(side);
    el.querySelectorAll(".pillars li").forEach(li => li.classList.remove("on"));
  }
  const h = $("#lane-harness");
  $("[data-todos]", h).innerHTML = `<li class="empty">No plan yet</li>`;
  $("[data-todocount]", h).textContent = "";
  $("[data-loop]", h).textContent = "0";
  $("[data-scout]", h).innerHTML = `<li class="empty">No research delegated yet</li>`;
  $("[data-scoutstate]", h).textContent = "idle";
  $("[data-loopr]", h).textContent = "Waiting for the first attempt";
}

// ---------- event handling ----------
function handle(ev) {
  const L = lanes[ev.side];
  if (!L) return;
  L.t = ev.t;
  switch (ev.type) {
    case "start":
      if (ev.side === "baseline") add(L, `<div class="say">No memory of previous conversations. Starts from the prompt alone.</div>`);
      break;
    case "tool_call": {
      const harnessTool = !!ev.pillar && !ev.agent;
      const by = ev.agent ? `<span class="by">${esc(ev.agent)}</span>` : "";
      const li = add(L, `${by}<span class="tool ${harnessTool ? "harness-tool" : ""}"><b>${esc(ev.name)}</b> <span class="args">${esc(fmtArgs(ev.args))}</span></span>`, ev.agent ? "scoutcall" : "");
      if (ev.agent) scout(L, `<b>${esc(ev.name)}</b> ${esc(fmtArgs(ev.args))}`);
      else L.pending = li;
      if (ev.pillar) light(ev.side, ev.pillar);
      break;
    }
    case "tool_result":
      if (ev.agent) break;
      if (L.pending) {
        const d = document.createElement("details");
        d.innerHTML = `<summary>${ev.ok ? `${(ev.chars ?? 0).toLocaleString()} chars returned` : "tool failed"}</summary><pre>${esc(ev.preview || "")}</pre>`;
        L.pending.append(d);
        if (!ev.ok) L.pending.classList.add("bad");
        L.pending = null;
      }
      break;
    case "assistant":
      add(L, `<div class="say">${esc(ev.text)}</div>`);
      break;
    case "metrics":
      L.m = ev; renderMetrics(ev.side);
      break;
    case "todos": {
      const ul = $("[data-todos]", L.el);
      if (!ul) break;
      ul.innerHTML = ev.items.map(i => `<li class="${i.done ? "done" : ""}">${esc(i.title)}</li>`).join("") || `<li class="empty">No plan yet</li>`;
      $("[data-todocount]", L.el).textContent = `${ev.items.filter(i => i.done).length}/${ev.items.length}`;
      break;
    }
    case "memory_seed":
      add(L, `<div class="say"><b>Memory from a previous conversation</b> (${esc(ev.file)})\n${esc(ev.note)}</div>`, "compact");
      break;
    case "memory":
      light(ev.side, "memory");
      if (ev.op === "read") L.recalled = true;
      add(L, `<div class="say">${ev.op === "read" ? "Recalled from memory" : "Saved to memory"}: ${esc(ev.path)}</div>`, "compact");
      break;
    case "compaction":
      light(ev.side, "compaction");
      add(L, `<div class="say">Context compacted (${ev.phase} model call). Old tool output evicted, notes and todos kept.</div>`, "compact");
      $(".metric.ctx", L.el)?.classList.remove("flash"); void L.el.offsetWidth; $(".metric.ctx", L.el)?.classList.add("flash");
      break;
    case "skill_run":
      light(ev.side, "skills");
      add(L, `<div class="say">Skill <b>${esc(ev.skill)}</b> ran ${esc(ev.script)} (exit ${ev.exit})\n${esc(ev.output)}</div>`, ev.exit === 0 ? "skill" : "bad");
      break;
    case "background": {
      light(ev.side, "background");
      const st = $("[data-scoutstate]", L.el);
      const label = { start_task: "researching", wait_for_first_completion: "waiting", get_task_results: "results in", get_all_tasks: "checking" }[ev.action] || ev.action.replaceAll("_", " ");
      if (st) st.textContent = label;
      scout(L, `<b>${esc(ev.action.replaceAll("_", " "))}</b> ${esc(ev.detail.slice(0, 140))}`);
      break;
    }
    case "submission": {
      const n = (ev.itinerary?.days || []).reduce((k, d) => k + (d.items || []).length, 0);
      add(L, `<div class="say">Submitted itinerary: ${n} items across ${(ev.itinerary?.days || []).length} days.</div>`, "good");
      break;
    }
    case "loop": {
      light(ev.side, "verify");
      const n = $("[data-loop]", L.el), r = $("[data-loopr]", L.el);
      if (n) n.textContent = ev.iteration;
      if (r) r.textContent = ev.cont ? ev.reason : "Done: plan submitted, deliverables built, research in, todos closed.";
      add(L, `<div class="say">Harness completion check, pass ${ev.iteration}: ${ev.cont ? esc(ev.reason) : "everything is done, stopping."}</div>`, ev.cont ? "verify" : "good");
      break;
    }
    case "final_text":
      if (ev.text) add(L, `<div class="say">${esc(ev.text)}</div>`, "final");
      break;
    case "error":
      add(L, `<div class="say">Run stopped: ${esc(ev.message)}</div>`, "bad");
      break;
    case "done":
      L.running = false;
      finals[ev.side] = ev;
      renderMetrics(ev.side);
      if (finals.baseline && finals.harness) reveal();
      break;
  }
}

function add(L, html, cls = "") {
  const li = document.createElement("li");
  if (cls) li.className = cls;
  li.innerHTML = `<span class="t">${L.t.toFixed(1)}s</span>${html}`;
  const atBottom = L.trace.scrollHeight - L.trace.scrollTop - L.trace.clientHeight < 60;
  L.trace.append(li);
  if (atBottom) L.trace.scrollTop = L.trace.scrollHeight;
  return li;
}

function scout(L, html) {
  const ul = $("[data-scout]", L.el);
  if (!ul) return;
  ul.querySelector(".empty")?.remove();
  const li = document.createElement("li");
  li.innerHTML = html;
  ul.append(li);
  ul.scrollTop = ul.scrollHeight;
}

function light(side, pillar, pulse = true) {
  const li = $(`#lane-${side} .pillars li[data-p="${pillar}"]`);
  if (!li || li.parentElement.classList.contains("off")) return;
  li.classList.add("on");
  if (pulse) { li.classList.remove("pulse"); void li.offsetWidth; li.classList.add("pulse"); }
}

function renderMetrics(side) {
  const L = lanes[side], m = L.m || {};
  const ctx = m.context_tokens || 0;
  $("[data-metrics]", L.el).innerHTML = `
    <div class="metric"><div class="v">${L.t.toFixed(0)}s</div><div class="k">elapsed</div></div>
    <div class="metric"><div class="v">${m.tool_calls ?? 0}</div><div class="k">tool calls</div></div>
    <div class="metric"><div class="v">${m.model_calls ?? 0}</div><div class="k">model calls</div></div>
    <div class="metric"><div class="v">${kfmt((m.input_tokens || 0) + (m.output_tokens || 0))}</div><div class="k">tokens, $${(m.cost_usd || 0).toFixed(2)}</div></div>
    <div class="metric ctx"><div class="v">${kfmt(ctx)}</div><div class="k">context now</div><div class="bar"><i style="width:${Math.min(100, ctx / 600)}%"></i></div></div>`;
}

// ---------- reveal ----------
function reveal() {
  const A = finals.baseline, B = finals.harness;
  $("#results").hidden = false;
  const items = f => (f.itinerary?.days || []).reduce((k, d) => k + (d.items || []).length, 0);
  const link = (f, name) => (f.files || []).includes(name)
    ? `<a href="/out/${f.workspace}/${name}" download>${name}</a>` : `<span class="none">not produced</span>`;
  const rows = [
    ["Time to finish", f => `${Math.round(f.t)}s`],
    ["Itinerary submitted", f => f.submitted ? `${items(f)} items over ${(f.itinerary?.days || []).length} days` : `<span class="none">no</span>`],
    ["Remembered the last conversation", (f, L) => L.recalled ? "yes, read it from memory" : (f.side === "baseline" ? "no memory to read" : "no")],
    ["Speakers researched", f => f.researched?.length ? `${f.researched.length}: ${esc(f.researched.slice(0, 4).join(", "))}${f.researched.length > 4 ? "…" : ""}` : `<span class="none">none</span>`],
    ["Excel workbook", f => link(f, "cypher_plan.xlsx")],
    ["Briefing deck", f => link(f, "cypher_briefing.pptx")],
    ["Calendar", f => f.ics ? `<a href="/out/${f.ics}" download>cypher_plan.ics</a>` : `<span class="none">not produced</span>`],
    ["Model calls / tool calls", f => `${f.metrics.model_calls} / ${f.metrics.tool_calls}`],
    ["Tokens and cost", f => `${kfmt(f.metrics.input_tokens + f.metrics.output_tokens)}, $${f.metrics.cost_usd.toFixed(2)}`],
    ["Peak context", f => kfmt(f.metrics.peak_context_tokens)],
  ];
  $("#checks tbody").innerHTML = rows.map(([label, fn], i) =>
    `<tr style="animation-delay:${i * 90}ms"><td>${label}</td><td class="cell">${fn(A, lanes.baseline)}</td><td class="cell">${fn(B, lanes.harness)}</td></tr>`).join("");
  renderTimeline(A, B);
  setTimeout(() => $("#results").scrollIntoView({ behavior: "smooth", block: "start" }), 400);
}

function picks(final) {
  const ids = new Set();
  for (const d of final.itinerary?.days || []) for (const i of d.items || []) ids.add(String(i.session_id));
  return ids;
}

function renderTimeline(A, B) {
  const pa = picks(A), pb = picks(B);
  const p = META.personas[persona];
  const pct = m => ((m - DAY_START) / (DAY_END - DAY_START)) * 100;
  const toMin = s => +s.slice(0, 2) * 60 + +s.slice(3, 5);
  const tl = $("#timeline");
  tl.innerHTML = "";
  for (const day of [1, 2, 3]) {
    const d = document.createElement("div");
    d.className = "day";
    const date = META.sessions.find(s => s.day === day)?.date;
    let html = `<h3>Day ${day}, ${new Date(date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" })}</h3>`;
    html += `<div class="axis"><span></span><div class="ticks">${[10, 12, 14, 16, 18, 20].map(h => `<span style="left:${pct(h * 60)}%">${h}:00</span>`).join("")}</div></div>`;
    for (const hall of [1, 2, 3]) {
      const busy = p.commitments.filter(c => c.day === day).map(c =>
        `<div class="busy" style="left:${pct(Math.max(DAY_START, toMin(c.start)))}%;width:${pct(Math.min(DAY_END, toMin(c.end))) - pct(Math.max(DAY_START, toMin(c.start)))}%"></div>`).join("");
      const blocks = META.sessions.filter(s => s.day === day && s.hall === hall).map(s => {
        const cls = ["blk", s.category === "Break / Lunch" ? "lunch" : "", pa.has(s.id) ? "pa" : "", pb.has(s.id) ? "pb" : ""].join(" ");
        const l = pct(toMin(s.start)), w = pct(toMin(s.end)) - l;
        return `<div class="${cls}" style="left:${l}%;width:calc(${w}% - 2px)" data-tip="${esc(`${s.id}  ${s.start}–${s.end}  ${s.title}`)}"><span class="st a"></span><span class="st b"></span></div>`;
      }).join("");
      html += `<div class="hall"><span class="name">Hall ${hall}</span><div class="track">${busy}${blocks}</div></div>`;
    }
    d.innerHTML = html;
    tl.append(d);
  }
}

// tooltips on timeline blocks
let tip;
document.addEventListener("mouseover", e => {
  const b = e.target.closest?.(".blk");
  if (!b) { tip?.remove(); tip = null; return; }
  tip ??= document.body.appendChild(Object.assign(document.createElement("div"), { className: "tip" }));
  tip.textContent = b.dataset.tip;
});
document.addEventListener("mousemove", e => { if (tip) { tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 14 + "px"; } });

// ---------- utils ----------
function fmtArgs(a) {
  if (!a || !Object.keys(a).length) return "()";
  const short = v => {
    const t = typeof v === "string" ? v : JSON.stringify(v);
    return t.length > 70 ? t.slice(0, 70) + "…" : t;
  };
  return "(" + Object.entries(a).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => `${k}=${typeof v === "string" ? JSON.stringify(short(v)) : short(v)}`).join(", ") + ")";
}
const kfmt = n => n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
