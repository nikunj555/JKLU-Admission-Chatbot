/* JKLU Information Assistant - chat logic.  Talks to the FastAPI backend (same origin). */
(function () {
  "use strict";
  var qs = new URLSearchParams(location.search);
  var API = qs.get("api") || (location.protocol === "file:" ? "http://127.0.0.1:8000" : "");
  var EXAMPLES = [
    "What is the eligibility for B.Tech admission?",
    "What is the tuition fee for B.Tech in 2026-27?",
    "What scholarship can I get with JEE Main percentile above 95?",
    "What are the hostel rules for visitors?",
    "Which letter grades are awarded at JKLU?",
    "How can I contact the admissions office?"
  ];
  var LABEL = { admission: "Admission", academics: "Academics", hostel: "Hostel", fees: "Fees", examination: "Examination",
    scholarships: "Scholarships", contact: "Contact", notices: "Notices", general: "General" };
  var BADGE = {
    answer:   { text: "Answer",                        cls: "bg-emerald-50 text-emerald-700 border-emerald-300", dot: "bg-emerald-600", bar: "bg-emerald-600", glow: "glow-answer" },
    clarify:  { text: "Needs clarification",           cls: "bg-amber-50 text-amber-700 border-amber-300",       dot: "bg-amber-600",   bar: "bg-amber-500",   glow: "glow-clarify" },
    escalate: { text: "Please contact the university", cls: "bg-red-50 text-red-700 border-red-300",             dot: "bg-red-600",     bar: "bg-red-500",     glow: "glow-escalate" }
  };

  var S = { busy: false, history: [], lastQuestion: null, msgId: 0 };
  var $ = function (id) { return document.getElementById(id); };
  var thread = $("thread"), canvas = $("thread-canvas"), input = $("input"), sendBtn = $("send");
  var ic = window.ic;

  /* ------------------------------------------------------------- helpers */
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function isHttp(u) { return /^https?:\/\//i.test(u || ""); }
  function startYear(y) { var m = /^(20\d{2})/.exec(y || ""); return m ? +m[1] : null; }
  function nowTime() { return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); }
  function scene(fn) { try { if (window.Scene3D && window.Scene3D[fn]) window.Scene3D[fn].apply(null, [].slice.call(arguments, 1)); } catch (e) {} }

  /** Safe mini-markdown: escape first, then **bold**, bullet lists, line breaks, clickable [n] citations. */
  function fmt(text, id) {
    var html = "", inList = false;
    function inline(t) {
      return esc(t)
        .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-primary">$1</strong>')
        .replace(/\[(\d{1,2})\]/g, function (_, n) {
          return '<button type="button" class="cite font-code text-xs text-primary bg-surface-container hover:bg-surface-container-high hover:-translate-y-0.5 px-1.5 py-0.5 rounded-md border border-outline-variant font-semibold ml-0.5 transition-all" data-cite="' + id + ":" + n + '">[' + n + "]</button>";
        });
    }
    String(text || "").split("\n").forEach(function (raw) {
      var m = /^\s*(?:[-*\u2022])\s+(.*)$/.exec(raw);
      if (m) { if (!inList) { html += '<ul class="list-disc pl-5 space-y-1.5">'; inList = true; } html += "<li>" + inline(m[1]) + "</li>"; }
      else { if (inList) { html += "</ul>"; inList = false; } if (raw.trim()) html += "<p>" + inline(raw) + "</p>"; }
    });
    if (inList) html += "</ul>";
    return html || "<p></p>";
  }

  function openSource(id, n) {
    var d = $("src-" + id); if (!d) return;
    d.open = true;
    var row = $("src-" + id + "-" + n);
    (row || d).scrollIntoView({ behavior: "smooth", block: "nearest" });
    if (row) { row.classList.add("ring-2", "ring-surface-tint"); setTimeout(function () { row.classList.remove("ring-2", "ring-surface-tint"); }, 1600); }
  }
  function scrollDown() { requestAnimationFrame(function () { canvas.scrollTo({ top: canvas.scrollHeight, behavior: "smooth" }); }); }
  window.toggleSidebar = function () { $("sidebar").classList.toggle("-translate-x-full"); $("scrim").classList.toggle("hidden"); };
  function closeSidebarOnMobile() { if (window.innerWidth < 768 && !$("sidebar").classList.contains("-translate-x-full")) window.toggleSidebar(); }

  /* ----------------------------------------------------------- rendering */
  function userBubble(text) {
    return '<div class="msg rise flex justify-end"><div class="zg-target max-w-2xl bg-primary-container text-white rounded-2xl rounded-br-md p-4 text-[15px] shadow-float">' +
      '<div class="flex items-center gap-2 mb-1 text-xs text-white/70"><span class="font-semibold text-white">You</span><span>\u2022</span><span>' + nowTime() + "</span></div>" +
      '<p class="whitespace-pre-wrap break-words">' + esc(text) + "</p></div></div>";
  }

  function sourcesBlock(res, id) {
    var src = res.sources || [];
    if (!src.length) return "";
    var years = src.map(function (s) { return startYear(s.academic_year); }).filter(Boolean);
    var newest = years.length ? Math.max.apply(null, years) : null;
    var tag = function (t, extra) { return '<span class="px-1.5 py-0.5 rounded-md text-xs border ' + (extra || "bg-surface-container text-secondary border-outline-variant") + '">' + t + "</span>"; };
    var rows = src.map(function (s) {
      var y = startYear(s.academic_year), outdated = newest && y && y < newest;
      var title = isHttp(s.url)
        ? '<a href="' + esc(s.url) + '" target="_blank" rel="noopener" class="font-semibold text-primary hover:underline break-words">' + esc(s.title) + "</a>"
        : '<span class="font-semibold text-primary break-words">' + esc(s.title) + "</span>";
      var tags = (s.category ? tag(esc(LABEL[s.category] || s.category)) : "") +
        (s.page ? tag("p. " + esc(s.page) + (s.page_end && s.page_end !== s.page ? "-" + esc(s.page_end) : "")) : "") +
        (s.academic_year ? tag(esc(s.academic_year)) : "") +
        (outdated ? tag("may be outdated", "bg-amber-50 text-amber-700 border-amber-200") : "");
      return '<div id="src-' + id + "-" + s.n + '" data-tilt="3" class="p-3 bg-white/80 rounded-xl border border-outline-variant text-sm space-y-1.5">' +
        '<div class="flex flex-wrap items-center gap-2"><span class="font-code text-xs text-primary bg-surface-container px-1.5 rounded">[' + s.n + "]</span>" + title + "</div>" +
        '<div class="flex flex-wrap gap-1.5">' + tags + "</div>" +
        '<p class="text-secondary italic text-xs leading-relaxed">' + esc(s.snippet) + "</p></div>";
    }).join("");
    return '<div class="border-t border-outline-variant/60 pt-3"><details id="src-' + id + '" class="group">' +
      '<summary class="flex items-center justify-between cursor-pointer text-xs text-secondary hover:text-primary select-none">' +
      '<span class="flex items-center gap-2 font-semibold">' + ic("book-open", 18, "text-primary") + "Sources (" + src.length + ")</span>" +
      ic("chevron-down", 20, "transition-transform duration-200 group-open:rotate-180") + "</summary>" +
      '<div class="mt-3 space-y-2.5">' + rows + "</div></details></div>";
  }

  function whyBlock(res) {
    var mode = res.provider && res.provider !== "extractive" ? "AI-generated (" + esc(res.provider) + ")" : "extracted from documents";
    return '<div class="border-t border-outline-variant/40 pt-2"><details class="group">' +
      '<summary class="flex items-center gap-1.5 text-xs text-secondary hover:text-primary cursor-pointer select-none">' + ic("info", 16) + "<span>Why this response?</span>" +
      ic("chevron-down", 14, "transition-transform duration-200 group-open:rotate-180") + "</summary>" +
      '<div class="mt-2 p-2.5 bg-surface-container-low rounded-lg border border-outline-variant text-xs text-secondary">' +
      esc(res.reason || "") + "<br/>" + Number(res.latency_ms || 0) + " ms \u2022 " + mode + "</div></details></div>";
  }

  function contactsBlock(res) {
    var rows = (res.contacts || []).map(function (c) {
      return '<div data-tilt="3" class="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white/60">' +
        '<div class="font-semibold text-primary text-sm">' + esc(c.office) + "</div>" +
        '<div class="font-code text-sm flex flex-wrap items-center gap-x-4 gap-y-1">' +
        (c.phone ? '<a href="tel:' + esc(String(c.phone).replace(/[^+\d]/g, "")) + '" class="inline-flex items-center gap-1 text-primary hover:underline">' + ic("phone", 16) + esc(c.phone) + "</a>" : "") +
        (c.email ? '<a href="mailto:' + esc(String(c.email).split(",")[0].trim()) + '" class="text-secondary hover:underline break-all">' + esc(c.email) + "</a>" : "") +
        "</div></div>";
    }).join("");
    var link = isHttp(res.contact_page)
      ? '<a href="' + esc(res.contact_page) + '" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">Open JKLU contact page' + ic("external-link", 16) + "</a>" : "";
    return (rows ? '<div class="rounded-xl border border-outline-variant divide-y divide-outline-variant/60 overflow-hidden">' + rows + "</div>" : "") + '<div class="pt-1">' + link + "</div>";
  }

  function chipsBlock(res) {
    var chips = res.suggestions || [];
    if (!chips.length) return "";
    return '<div class="pt-2"><span class="block text-xs text-secondary mb-2">Pick one to continue:</span><div class="flex flex-wrap gap-2">' +
      chips.map(function (c) { return '<button type="button" data-tilt="9" data-q="' + esc(c.question) + '" class="chip px-3.5 py-2 rounded-xl border border-outline-variant bg-white/90 hover:border-surface-tint hover:bg-surface-container-low text-sm font-medium text-primary shadow-soft">' + esc(c.label) + "</button>"; }).join("") +
      "</div></div>";
  }

  function assistantCard(res) {
    var id = ++S.msgId;
    if (res.status === "smalltalk") {
      return '<div class="msg rise flex justify-start"><article class="zg-target max-w-3xl w-full glass-card border border-outline-variant rounded-2xl p-5 sm:p-6 text-[16px] leading-relaxed space-y-3 shadow-soft"><div data-body class="space-y-3">' + fmt(res.answer, id) + "</div></article></div>";
    }
    var b = BADGE[res.status] || BADGE.escalate;
    var pct = Math.max(0, Math.min(100, Math.round((res.confidence || 0) * 100)));
    var body = res.status === "escalate" ? fmt((res.answer || "").split("\n\n")[0], id) + contactsBlock(res)
      : res.status === "clarify" ? fmt(res.clarification || res.answer, id) + chipsBlock(res)
      : fmt(res.answer, id);
    return '<div class="msg rise flex justify-start"><article data-tilt="1.6" class="zg-target max-w-3xl w-full glass-card border border-outline-variant rounded-2xl p-5 sm:p-6 space-y-4 ' + b.glow + '">' +
      '<div class="flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant/60 pb-3">' +
      '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ' + b.cls + '"><span class="w-1.5 h-1.5 rounded-full ' + b.dot + '"></span>' + b.text + "</span>" +
      '<span class="flex items-center gap-2 text-xs text-secondary">Confidence <span class="font-semibold text-on-surface font-code" data-count>0%</span>' +
      '<span class="w-20 h-1.5 bg-surface-container rounded-full overflow-hidden"><span data-bar="' + pct + '" class="bar-fill block h-full rounded-full ' + b.bar + '" style="width:0%"></span></span></span></div>' +
      '<div data-body class="text-[16px] leading-relaxed space-y-3 break-words">' + body + "</div>" +
      sourcesBlock(res, id) + whyBlock(res) + "</article></div>";
  }

  function errorCard(msg) {
    return '<div class="error-slot rise"><div class="bg-red-50/95 border border-red-200 rounded-2xl p-5 flex items-start gap-4 shadow-soft">' +
      ic("circle-alert", 24, "text-red-600") + '<div class="space-y-3 flex-1"><div><h4 class="font-semibold text-red-900">Could not reach the assistant</h4>' +
      '<p class="text-[15px] text-red-800 mt-1">' + esc(msg) + "</p></div>" +
      '<button type="button" class="retry px-4 py-2 rounded-xl bg-red-700 text-white text-sm font-medium hover:bg-red-800 inline-flex items-center gap-1.5">' + ic("refresh-cw", 16) + "Retry</button></div></div></div>";
  }

  /* ---------------------------------------------------------------- send */
  function append(html) {
    var d = document.createElement("div"); d.innerHTML = html;
    var el = d.firstElementChild; thread.appendChild(el); return el;
  }

  function ask(question) {
    question = (question || "").trim();
    if (!question || S.busy) return Promise.resolve();
    S.busy = true; S.lastQuestion = question; refreshSend();
    $("welcome").classList.add("hidden");
    thread.querySelectorAll(".error-slot").forEach(function (e) { e.remove(); });
    append(userBubble(question));
    var loader = append('<div class="msg rise flex justify-start"><div class="glass-card border border-outline-variant rounded-2xl px-4 py-3 flex items-center gap-3 shadow-soft">' +
      '<div class="orbit" aria-hidden="true"><span></span><span></span></div><span class="text-[15px] text-primary font-medium">Searching JKLU documents...</span></div></div>');
    scrollDown(); scene("search");
    var k = +$("topk").value;
    return fetch(API + "/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, category: $("topic").value || null, top_k: k, history: S.history.slice(-8) })
    }).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return {}; }).then(function (d) { throw new Error(d.detail || "Server returned " + r.status); });
      return r.json();
    }).then(function (res) {
      loader.remove();
      var el = append(assistantCard(res));
      var card = el.querySelector("article");
      var body = card.querySelector("[data-body]");
      if (body) window.FX.stagger(body, ":scope > *", 70);
      window.FX.confidence(card);
      scene("result", res.status === "smalltalk" ? "answer" : res.status, k);
      S.history.push({ role: "user", content: question },
        { role: "assistant", content: String(res.status === "clarify" ? (res.clarification || res.answer) : res.answer || "").slice(0, 1500) });
    }).catch(function (e) {
      loader.remove(); scene("idle");
      var msg = e.message === "Failed to fetch" ? "The server is not responding. Make sure `python run.py` is still running." : e.message;
      var el = append(errorCard(msg));
      el.querySelector(".retry").onclick = function () { el.remove(); retry(); };
    }).then(function () { S.busy = false; refreshSend(); scrollDown(); });
  }
  function retry() {
    var last = thread.lastElementChild; if (last) last.remove();     // drop the failed user bubble
    var q = S.lastQuestion; S.lastQuestion = null; ask(q);
  }
  window.__ask = ask;   // used by tests

  /* ------------------------------------------------------------ controls */
  function refreshSend() { sendBtn.disabled = S.busy || !input.value.trim(); }
  function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; }
  input.addEventListener("input", function () { $("counter").textContent = input.value.length + " / 600"; autosize(); refreshSend(); });
  input.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("form").requestSubmit(); } });
  $("form").addEventListener("submit", function (e) {
    e.preventDefault(); var q = input.value; input.value = ""; $("counter").textContent = "0 / 600"; autosize(); refreshSend(); ask(q);
  });
  function fill() { var t = $("topk"); t.style.setProperty("--fill", ((t.value - t.min) / (t.max - t.min)) * 100 + "%"); }
  $("topk").addEventListener("input", function (e) { $("topk-val").textContent = e.target.value; fill(); });
  fill();
  $("clear").addEventListener("click", function () {
    thread.innerHTML = ""; S.history = []; S.lastQuestion = null; $("welcome").classList.remove("hidden"); canvas.scrollTop = 0; scene("idle"); closeSidebarOnMobile();
  });
  $("zg-btn").addEventListener("click", function () { window.FX.setZeroG(!window.FX.zero); });
  thread.addEventListener("click", function (e) {
    var c = e.target.closest(".chip"); if (c) { ask(c.dataset.q); return; }
    var cite = e.target.closest("[data-cite]");
    if (cite) { var p = cite.getAttribute("data-cite").split(":"); openSource(p[0], p[1]); }
  });

  $("examples").innerHTML = EXAMPLES.map(function (q) {
    return '<button type="button" data-tilt="7" class="ex w-full text-left text-sm px-3.5 py-2.5 rounded-xl border border-outline-variant/70 bg-white/80 hover:border-surface-tint hover:text-primary shadow-soft">' + esc(q) + "</button>";
  }).join("");
  $("examples").addEventListener("click", function (e) { var b = e.target.closest(".ex"); if (b) { closeSidebarOnMobile(); ask(b.textContent); } });

  /* -------------------------------------------------------------- status */
  function loadStatus() {
    return Promise.all([fetch(API + "/health").then(function (r) { return r.json(); }), fetch(API + "/categories").then(function (r) { return r.json(); })]).then(function (rs) {
      var h = rs[0], c = rs[1], ok = h.status === "ok";
      $("st-dot").className = "w-2 h-2 rounded-full " + (ok ? "bg-emerald-500" : "bg-red-500");
      $("st-text").textContent = ok ? "Ready" : "Unavailable";
      $("st-chunks").textContent = (h.chunks || 0).toLocaleString();
      $("st-ret").textContent = h.retrieval === "semantic+bm25" ? "semantic + keyword" : "keyword only";
      $("st-llm").textContent = h.llm_provider && h.llm_provider !== "none" ? "AI-generated (" + h.llm_provider + ")" : "extracted from documents";
      $("topic").innerHTML = '<option value="">All topics (' + (h.chunks || 0).toLocaleString() + " passages)</option>" +
        (c.categories || []).map(function (x) { return '<option value="' + esc(x.name) + '"' + (x.chunks ? "" : " disabled") + ">" + esc(LABEL[x.name] || x.name) + " (" + x.chunks + " passages)</option>"; }).join("");
    }).catch(function () {
      $("st-dot").className = "w-2 h-2 rounded-full bg-red-500"; $("st-text").textContent = "Offline";
    });
  }
  if (window.innerWidth < 640) input.placeholder = "Ask about JKLU...";
  window.hydrateIcons();
  loadStatus(); refreshSend();
})();
