/* KrshiBandhu dashboard */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const EMOJI = { nilgai: "🐂", boar: "🐗", deer: "🦌", monkey: "🐒", bird: "🦜", cattle: "🐄", dog: "🐕", person: "🧍" };
  const CAT_EMOJI = { tiger: "🐅", leopard: "🐆", dogs: "🐕‍🦺", hawk: "🦅", eagle: "🦅", human: "📢" };
  const COLORS = ["#2f7d32", "#e9a23b", "#d64545", "#3b7dd8", "#8e5bd8", "#20a39e", "#b5651d", "#999"];

  let lang = localStorage.getItem("kb_lang") || "en";
  let settings = null;
  let state = { status: "starting", armed: true };
  let page = 0; const PAGE = 20;
  let range = "24h";
  let charts = {};
  let streamOk = false;

  const t = (k) => (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k;
  const an = (a) => (I18N[lang].animals[a] || a);
  const cn = (c) => (I18N[lang].cats[c] || c);

  // ---------- helpers ----------
  async function api(path, opts = {}) {
    const r = await fetch(path, { headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}, ...opts });
    let data = null;
    try { data = await r.json(); } catch { }
    if (!r.ok) throw new Error((data && data.detail) || r.statusText);
    return data;
  }
  function toast(msg, err = false) {
    const el = $("#toast");
    el.textContent = msg; el.className = "toast show" + (err ? " err" : "");
    clearTimeout(el._t); el._t = setTimeout(() => (el.className = "toast"), 3000);
  }
  const fmtTime = (ts) => new Date(ts * 1000).toLocaleString(lang === "hi" ? "hi-IN" : "en-IN",
    { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const snapUrl = (s) => s ? `/snapshots/${s}` : "";
  function openLightbox(src) { $("#lightboxImg").src = src; $("#lightbox").classList.remove("hidden"); }
  $("#lightbox").onclick = () => $("#lightbox").classList.add("hidden");

  // ---------- i18n ----------
  function applyLang() {
    document.documentElement.lang = lang;
    $$("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
    renderArm(); buildPlayGrid(); buildFilter();
    if (settings) { buildMapping(); loadLibrary(); }
    renderStatus();
    if ($("#tab-events").classList.contains("active")) loadEvents();
    if ($("#tab-stats").classList.contains("active")) loadStats();
  }
  $("#langBtn").onclick = () => {
    lang = lang === "en" ? "hi" : "en"; localStorage.setItem("kb_lang", lang); applyLang();
  };

  // ---------- tabs ----------
  $$(".tab").forEach((b) => b.onclick = () => {
    $$(".tab").forEach((x) => x.classList.toggle("active", x === b));
    $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + b.dataset.tab));
    if (b.dataset.tab === "events") loadEvents();
    if (b.dataset.tab === "stats") loadStats();
    if (b.dataset.tab === "settings") { loadSettings(); loadLibrary(); }
  });

  // ---------- arm ----------
  function renderArm() {
    const b = $("#armBtn");
    b.classList.toggle("off", !state.armed);
    b.setAttribute("aria-pressed", state.armed);
    $("#armText").textContent = state.armed ? t("armed") : t("disarmed");
    $(".arm-icon", b).textContent = state.armed ? "🛡️" : "⏸️";
  }
  $("#armBtn").onclick = async () => {
    try { const r = await api("/api/arm", { method: "POST", body: JSON.stringify({ armed: !state.armed }) }); state.armed = r.armed; renderArm(); }
    catch (e) { toast(e.message, true); }
  };

  // ---------- status / live ----------
  function renderStatus() {
    const pill = $("#statusPill"); const txt = $("#statusText");
    pill.className = "status-pill";
    const ov = $("#videoOverlay"), ovt = $("#overlayText");
    if (state.status === "error") {
      pill.classList.add("err"); txt.textContent = t("error");
      ov.classList.remove("hidden"); ovt.textContent = t("model_error") + ": " + (state.error || "");
    } else if (state.status === "loading_model" || state.status === "starting") {
      pill.classList.add("warn"); txt.textContent = t("loading");
      ov.classList.remove("hidden"); ovt.textContent = t("loading_model");
    } else if (!state.camera_connected) {
      pill.classList.add("err"); txt.textContent = t("offline");
      ov.classList.remove("hidden"); ovt.textContent = t("no_camera");
    } else {
      pill.classList.add("ok"); txt.textContent = `${t("running")} · ${state.fps || 0} fps`;
      ov.classList.toggle("hidden", streamOk);
      if (!streamOk) ovt.textContent = t("connecting");
    }
    $("#fpsTag").textContent = `${state.fps || 0} fps`;
  }

  function renderDetections(dets, person) {
    const ul = $("#detList");
    $("#personTag").classList.toggle("hidden", !person);
    if (!dets || !dets.length) { ul.innerHTML = `<li class="muted">${t("nothing")}</li>`; return; }
    ul.innerHTML = dets.map((d) => `<li class="${d.label === "person" ? "person" : ""}">
      <span>${EMOJI[d.label] || "❓"} ${an(d.label)}</span>
      <span class="row">${Math.round(d.confidence * 100)}%<span class="conf-bar"><i style="width:${d.confidence * 100}%"></i></span></span></li>`).join("");
  }

  function renderLastTrigger(ev) {
    const el = $("#lastTrigger");
    if (!ev) { el.className = "last-trigger muted"; el.textContent = t("no_trigger"); return; }
    el.className = "last-trigger";
    el.innerHTML = `${ev.snapshot ? `<img src="${snapUrl(ev.snapshot)}" alt="">` : ""}
      <div><b>${EMOJI[ev.animal] || ""} ${an(ev.animal)}</b><br><span class="small muted">${fmtTime(ev.ts)}</span><br>
      <span class="small">🔊 ${ev.sound || "-"}</span></div>`;
    const img = $("img", el); if (img) img.onclick = () => openLightbox(img.src);
  }

  function showAlert(ev) {
    const b = $("#alertBanner");
    b.textContent = `${EMOJI[ev.animal] || "⚠️"} ${an(ev.animal)} ${t("detected")} 🔊 ${ev.sound || ""}`;
    b.classList.remove("show"); void b.offsetWidth; b.classList.add("show");
    clearTimeout(b._t); b._t = setTimeout(() => b.classList.remove("show"), 5000);
  }

  function startStream() {
    const img = $("#stream");
    img.onload = () => { if (!streamOk) { streamOk = true; renderStatus(); } };
    img.onerror = () => { streamOk = false; renderStatus(); setTimeout(startStream, 3000); };
    img.src = "/api/stream?t=" + Date.now();
  }

  function connectWS() {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.onmessage = (m) => {
      const msg = JSON.parse(m.data);
      if (msg.type === "status") {
        const wasRunning = state.status === "running";
        Object.assign(state, msg); renderArm(); renderStatus();
        renderDetections(msg.detections, false);
        if (msg.last_trigger) renderLastTrigger(msg.last_trigger);
        if (!wasRunning && msg.status === "running") { streamOk = false; startStream(); }
      } else if (msg.type === "detections") {
        state.fps = msg.fps; state.armed = msg.armed; state.camera_connected = msg.camera_connected;
        if (state.status !== "running") state.status = "running";
        renderDetections(msg.detections, msg.person); renderStatus();
      } else if (msg.type === "event") {
        const ev = msg.event;
        if (ev.kind === "animal" && ev.sound) { renderLastTrigger(ev); showAlert(ev); }
        if ($("#tab-events").classList.contains("active") && page === 0) loadEvents();
      }
    };
    ws.onclose = () => { state.status = "starting"; renderStatus(); setTimeout(connectWS, 2000); };
  }

  function buildPlayGrid() {
    const animals = ["nilgai", "boar", "deer", "monkey", "bird", "cattle", "dog"];
    $("#playGrid").innerHTML = animals.map((a) =>
      `<button class="play-btn" data-animal="${a}"><span class="emo">${EMOJI[a]}</span>${an(a)}</button>`).join("");
    $$("#playGrid .play-btn").forEach((b) => b.onclick = async () => {
      try { const r = await api("/api/play", { method: "POST", body: JSON.stringify({ animal: b.dataset.animal }) }); toast(`🔊 ${r.played}`); }
      catch (e) { toast(e.message, true); }
    });
  }
  $("#stopSoundBtn").onclick = () => api("/api/stop-sound", { method: "POST" });

  // ---------- events ----------
  function buildFilter() {
    const sel = $("#eventFilter"); const cur = sel.value;
    sel.innerHTML = `<option value="">${t("all")}</option>` +
      Object.keys(EMOJI).map((a) => `<option value="${a}">${EMOJI[a]} ${an(a)}</option>`).join("");
    sel.value = cur;
  }
  $("#eventFilter").onchange = () => { page = 0; loadEvents(); };
  $("#refreshEvents").onclick = () => loadEvents();
  $("#prevPage").onclick = () => { if (page > 0) { page--; loadEvents(); } };
  $("#nextPage").onclick = () => { page++; loadEvents(); };

  function actionBadge(ev) {
    if (ev.kind === "manual") return `<span class="badge manual">${t("manual")} · ${ev.sound}</span>`;
    if (ev.kind === "person") return `<span class="badge person">🧍 ${an("person")}</span>`;
    if (ev.sound) return `<span class="badge sound">🔊 ${ev.sound}</span>`;
    if (ev.suppressed === "person") return `<span class="badge person">${t("no_sound_person")}</span>`;
    if (ev.suppressed === "disarmed") return `<span class="badge off">${t("no_sound_off")}</span>`;
    return `<span class="badge off">—</span>`;
  }
  async function loadEvents() {
    try {
      const f = $("#eventFilter").value;
      const d = await api(`/api/events?limit=${PAGE}&offset=${page * PAGE}${f ? "&animal=" + f : ""}`);
      const pages = Math.max(1, Math.ceil(d.total / PAGE));
      if (page >= pages) page = pages - 1;
      $("#pageInfo").textContent = `${page + 1} / ${pages} (${d.total})`;
      $("#prevPage").disabled = page === 0; $("#nextPage").disabled = page >= pages - 1;
      $("#eventsBody").innerHTML = d.items.map((ev) => `<tr>
        <td>${ev.snapshot ? `<img src="${snapUrl(ev.snapshot)}" loading="lazy" alt="">` : "—"}</td>
        <td>${fmtTime(ev.ts)}</td>
        <td>${ev.animal ? `${EMOJI[ev.animal] || ""} ${an(ev.animal)}` : "—"}</td>
        <td>${ev.confidence ? Math.round(ev.confidence * 100) + "%" : "—"}</td>
        <td>${actionBadge(ev)}${ev.notified ? " 📱" : ""}</td></tr>`).join("") ||
        `<tr><td colspan="5" class="muted">${t("nothing")}</td></tr>`;
      $$("#eventsBody img").forEach((i) => i.onclick = () => openLightbox(i.src));
    } catch (e) { toast(e.message, true); }
  }

  // ---------- stats ----------
  $$("#rangeSeg button").forEach((b) => b.onclick = () => {
    $$("#rangeSeg button").forEach((x) => x.classList.toggle("active", x === b)); range = b.dataset.range; loadStats();
  });
  function chart(id, cfg) {
    if (charts[id]) charts[id].destroy();
    if (typeof Chart === "undefined") return;
    charts[id] = new Chart($("#" + id), cfg);
  }
  async function loadStats() {
    try {
      const s = await api("/api/stats?range=" + range);
      $("#kpiAnimals").textContent = s.total_animals;
      $("#kpiSounds").textContent = s.sounds_played;
      $("#kpiPersons").textContent = s.total_persons;
      const entries = Object.entries(s.per_animal).filter(([a]) => a !== "person").sort((a, b) => b[1] - a[1]);
      $("#kpiTop").textContent = entries.length ? `${EMOJI[entries[0][0]] || ""} ${an(entries[0][0])}` : "—";
      chart("chartAnimals", {
        type: "bar",
        data: { labels: entries.map(([a]) => `${EMOJI[a] || ""} ${an(a)}`), datasets: [{ data: entries.map(([, c]) => c), backgroundColor: COLORS }] },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
      });
      chart("chartTimeline", {
        type: "line",
        data: { labels: s.timeline.labels, datasets: [{ data: s.timeline.values, borderColor: "#2f7d32", backgroundColor: "rgba(47,125,50,.15)", fill: true, tension: .3 }] },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
      });
      chart("chartHod", {
        type: "bar",
        data: { labels: [...Array(24).keys()].map((h) => `${String(h).padStart(2, "0")}:00`), datasets: [{ data: s.hour_of_day, backgroundColor: s.hour_of_day.map((_, h) => (h >= 18 || h < 6) ? "#3b4a8c" : "#e9a23b") }] },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
      });
    } catch (e) { toast(e.message, true); }
  }

  // ---------- settings ----------
  const SLIDERS = { confidence: (v) => Math.round(v * 100) + "%", hits: (v) => v, window: (v) => v, cooldown_s: (v) => v + "s", volume: (v) => v + "%", retention_days: (v) => v };
  const VAL_EL = { confidence: "confVal", hits: "hitsVal", window: "windowVal", cooldown_s: "cooldownVal", volume: "volumeVal", retention_days: "retentionVal" };
  let saveTimer = null;
  async function save(changes, quiet = true) {
    try {
      settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(changes) });
      fillSettings(false);
      if (!quiet) toast(t("saved") + " ✔");
    } catch (e) { toast(e.message, true); }
  }
  function fillSettings(full = true) {
    Object.keys(SLIDERS).forEach((k) => { $("#" + k).value = settings[k]; $("#" + VAL_EL[k]).textContent = SLIDERS[k](settings[k]); });
    ["low_light", "person_veto", "person_alert", "telegram_enabled"].forEach((k) => ($("#" + k).checked = Boolean(settings[k])));
    if (full) { $("#telegram_token").value = settings.telegram_token; $("#telegram_chat_id").value = settings.telegram_chat_id; }
  }
  async function loadSettings() {
    settings = await api("/api/settings");
    fillSettings(); buildMapping(); loadCameras(false);
    $("#uploadCat").innerHTML = settings.sound_categories.map((c) => `<option value="${c}">${CAT_EMOJI[c]} ${cn(c)}</option>`).join("");
  }
  Object.keys(SLIDERS).forEach((k) => {
    const el = $("#" + k);
    el.oninput = () => { $("#" + VAL_EL[k]).textContent = SLIDERS[k](parseFloat(el.value)); };
    el.onchange = () => {
      const v = parseFloat(el.value); const ch = { [k]: v };
      if (k === "window" && settings.hits > v) ch.hits = v;
      if (k === "hits" && settings.window < v) ch.window = v;
      save(ch);
    };
  });
  ["low_light", "person_veto", "person_alert"].forEach((k) => $("#" + k).onchange = (e) => save({ [k]: e.target.checked }));
  $("#telegram_enabled").onchange = (e) => save({ telegram_enabled: e.target.checked });
  $("#saveTg").onclick = () => save({ telegram_token: $("#telegram_token").value.trim(), telegram_chat_id: $("#telegram_chat_id").value.trim(), telegram_enabled: $("#telegram_enabled").checked }, false);
  $("#testTg").onclick = async () => {
    await save({ telegram_token: $("#telegram_token").value.trim(), telegram_chat_id: $("#telegram_chat_id").value.trim() });
    try { await api("/api/telegram/test", { method: "POST" }); toast(t("tg_ok")); } catch (e) { toast(e.message, true); }
  };

  async function loadCameras(scan = true) {
    const liveSel = $("#liveCamSelect");
    const setSel = $("#cameraSelect");
    if (!scan && settings) {
      const opt = `<option value="${settings.camera_index}">Camera ${settings.camera_index}</option>`;
      if (liveSel) liveSel.innerHTML = opt;
      if (setSel) setSel.innerHTML = opt;
      return;
    }
    const btns = [$("#scanCams"), $("#liveScanBtn")].filter(Boolean);
    btns.forEach(b => b.disabled = true);
    try {
      const r = await api("/api/cameras");
      const list = (r.cameras && r.cameras.length) ? r.cameras : [{ index: r.current, name: `Camera ${r.current}` }];
      const optionsHtml = list.map((cam) => {
        const idx = typeof cam === "object" ? cam.index : cam;
        const name = typeof cam === "object" ? cam.name : `Camera ${idx}`;
        return `<option value="${idx}" ${idx === r.current ? "selected" : ""}>${name}</option>`;
      }).join("");
      if (liveSel) liveSel.innerHTML = optionsHtml;
      if (setSel) setSel.innerHTML = optionsHtml;
      const currentObj = list.find(c => (typeof c === "object" ? c.index : c) === r.current);
      if ($("#camStatusHint") && currentObj) {
        $("#camStatusHint").textContent = typeof currentObj === "object" ? currentObj.name : `Camera ${currentObj}`;
      }
    } catch (e) { toast(e.message, true); }
    btns.forEach(b => b.disabled = false);
  }

  async function onCameraChanged(newIdx) {
    streamOk = false;
    const liveSel = $("#liveCamSelect");
    const setSel = $("#cameraSelect");
    if (liveSel) liveSel.value = newIdx;
    if (setSel) setSel.value = newIdx;
    await save({ camera_index: parseInt(newIdx) }, false);
    toast(`📷 ${t("camera_feed")} Camera ${newIdx} ✔`);
    startStream();
  }

  if ($("#scanCams")) $("#scanCams").onclick = (e) => { e.preventDefault(); loadCameras(true); };
  if ($("#liveScanBtn")) $("#liveScanBtn").onclick = (e) => { e.preventDefault(); loadCameras(true); };
  if ($("#cameraSelect")) $("#cameraSelect").onchange = (e) => onCameraChanged(e.target.value);
  if ($("#liveCamSelect")) $("#liveCamSelect").onchange = (e) => onCameraChanged(e.target.value);

  function buildMapping() {
    if (!settings) return;
    const cats = settings.sound_categories;
    const head = `<tr><th></th>${cats.map((c) => `<th title="${cn(c)}">${CAT_EMOJI[c]}<br>${cn(c)}</th>`).join("")}<th>${t("enabled")}</th></tr>`;
    const rows = settings.animals.map((a) => `<tr><td>${EMOJI[a]} ${an(a)}</td>${cats.map((c) =>
      `<td><input type="checkbox" data-a="${a}" data-c="${c}" ${settings.mapping[a].includes(c) ? "checked" : ""}></td>`).join("")}
      <td><input type="checkbox" data-en="${a}" ${settings.enabled_animals.includes(a) ? "checked" : ""}></td></tr>`).join("");
    $("#mappingTable").innerHTML = head + rows;
    $$("#mappingTable input[data-a]").forEach((cb) => cb.onchange = () => {
      const m = JSON.parse(JSON.stringify(settings.mapping));
      const a = cb.dataset.a, c = cb.dataset.c;
      m[a] = cb.checked ? [...new Set([...m[a], c])] : m[a].filter((x) => x !== c);
      save({ mapping: m });
    });
    $$("#mappingTable input[data-en]").forEach((cb) => cb.onchange = () => {
      const en = $$("#mappingTable input[data-en]").filter((x) => x.checked).map((x) => x.dataset.en);
      save({ enabled_animals: en });
    });
  }

  async function loadLibrary() {
    try {
      const lib = await api("/api/sounds");
      $("#soundLibrary").innerHTML = Object.entries(lib).map(([c, files]) => `<div class="lib-cat">
        <h4>${CAT_EMOJI[c]} ${cn(c)} <span class="muted small">(${files.length})</span></h4>
        ${files.length ? files.map((f) => `<div class="lib-item"><span title="${f}">${f}</span><span class="acts">
          <button class="btn sm ghost" data-play="${c}/${f}" title="Play on farm speaker">▶</button>
          <button class="btn sm ghost" data-preview="${c}/${f}" title="Preview in browser">🎧</button>
          <button class="btn sm danger" data-del="${c}/${f}">✕</button></span></div>`).join("")
          : `<div class="muted small">${t("no_files")}</div>`}</div>`).join("");
      $$("[data-play]").forEach((b) => b.onclick = () => api(`/api/sounds/${b.dataset.play}/play`, { method: "POST" }).catch((e) => toast(e.message, true)));
      $$("[data-preview]").forEach((b) => b.onclick = () => new Audio(`/api/sounds/${b.dataset.preview}`).play());
      $$("[data-del]").forEach((b) => b.onclick = async () => {
        if (!confirm(t("delete_q"))) return;
        try { await api(`/api/sounds/${b.dataset.del}`, { method: "DELETE" }); loadLibrary(); } catch (e) { toast(e.message, true); }
      });
    } catch (e) { toast(e.message, true); }
  }
  $("#uploadBtn").onclick = async () => {
    const f = $("#uploadFile").files[0];
    if (!f) return toast(t("choose_file"), true);
    const fd = new FormData(); fd.append("file", f);
    try { await api(`/api/sounds/${$("#uploadCat").value}`, { method: "POST", body: fd }); toast(t("uploaded") + " ✔"); $("#uploadFile").value = ""; loadLibrary(); }
    catch (e) { toast(e.message, true); }
  };

  // ---------- init ----------
  async function init() {
    applyLang();
    try {
      const s = await api("/api/status");
      Object.assign(state, s); renderArm(); renderStatus(); renderLastTrigger(s.last_trigger);
      settings = await api("/api/settings");
    } catch { }
    loadCameras(true);
    connectWS();
    startStream();
  }
  init();
})();
