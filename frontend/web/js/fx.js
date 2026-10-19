/* UI effects: 3D tilt + glare, Zero-G (weightless drag-and-throw), count-up, toast. */
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var FX = (window.FX = { zero: false });
  var $ = function (id) { return document.getElementById(id); };

  /* ------------------------------------------------------------ 3D tilt */
  var tiltEl = null, raf = 0, pending = null;
  function applyTilt() {
    raf = 0;
    if (!pending || !tiltEl) return;
    var e = pending, r = tiltEl.getBoundingClientRect();
    var max = parseFloat(tiltEl.getAttribute("data-tilt")) || 5;
    var px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
    var ry = (px - 0.5) * 2 * max, rx = -(py - 0.5) * 2 * max;
    tiltEl.style.transform = "perspective(900px) rotateX(" + rx.toFixed(2) + "deg) rotateY(" + ry.toFixed(2) + "deg) translateZ(" + (max > 3 ? 8 : 3) + "px)";
    tiltEl.style.setProperty("--mx", (px * 100).toFixed(1) + "%");
    tiltEl.style.setProperty("--my", (py * 100).toFixed(1) + "%");
  }
  function resetTilt(el) {
    if (!el) return;
    el.classList.remove("is-tilting");
    el.style.transform = "";
  }
  if (!reduce) {
    document.addEventListener("pointermove", function (e) {
      if (e.pointerType !== "mouse" || FX.zero) return;
      var el = e.target.closest && e.target.closest("[data-tilt]");
      if (el !== tiltEl) { resetTilt(tiltEl); tiltEl = el; if (el) el.classList.add("is-tilting"); }
      if (!el) return;
      pending = e;
      if (!raf) raf = requestAnimationFrame(applyTilt);
    }, { passive: true });
    document.addEventListener("pointerleave", function () { resetTilt(tiltEl); tiltEl = null; }, true);
  }

  /* ----------------------------------------------------------- toast */
  var toastTimer = 0;
  FX.toast = function (text) {
    var t = $("toast"); if (!t) return;
    t.textContent = text; t.classList.remove("opacity-0", "translate-y-2");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.add("opacity-0", "translate-y-2"); }, 3800);
  };

  /* --------------------------------------------- entrance + count-up */
  FX.stagger = function (root, sel, step) {
    if (reduce) return;
    var kids = root.querySelectorAll(sel);
    for (var i = 0; i < kids.length; i++) {
      kids[i].classList.add("fade-up");
      kids[i].style.animationDelay = (120 + i * (step || 60)) + "ms";
    }
  };
  FX.confidence = function (root) {
    var bar = root.querySelector("[data-bar]"), num = root.querySelector("[data-count]");
    if (!bar || !num) return;
    var target = +bar.getAttribute("data-bar") || 0;
    if (reduce) { bar.style.width = target + "%"; num.textContent = target + "%"; return; }
    bar.style.width = "0%";
    requestAnimationFrame(function () { requestAnimationFrame(function () { bar.style.width = target + "%"; }); });
    var t0 = performance.now(), dur = 1000;
    (function tick(t) {
      var p = Math.min(1, (t - t0) / dur), eased = 1 - Math.pow(1 - p, 3);
      num.textContent = Math.round(target * eased) + "%";
      if (p < 1) requestAnimationFrame(tick);
    })(t0);
  };

  /* ------------------------------------------------------------ Zero-G */
  var items = new Set(), st = new WeakMap(), loop = 0, lastT = 0, drag = null;
  var SEL = "#thread .zg-target, #examples .ex, #welcome";

  function bounds(el) {
    var cont = $("thread-canvas").getBoundingClientRect(), s = st.get(el);
    var r = el.getBoundingClientRect();
    var restL = r.left - s.x, restR = r.right - s.x, restT = r.top - s.y, restB = r.bottom - s.y;
    var inSide = el.closest("#sidebar");
    var box = inSide ? $("sidebar").getBoundingClientRect() : cont;
    s.minX = box.left + 6 - restL; s.maxX = box.right - 6 - restR;
    s.minY = Math.max(-170, box.top + 4 - restT); s.maxY = Math.min(170, box.bottom - 4 - restB);
    if (s.minX > s.maxX) s.minX = s.maxX = 0;
    if (s.minY > s.maxY) s.minY = s.maxY = 0;
  }
  function register(el) {
    if (items.has(el)) return;
    st.set(el, { x: 0, y: 0, vx: (Math.random() - 0.5) * 14, vy: -(4 + Math.random() * 8), r: 0, ph: Math.random() * 6.28, dirty: true });
    items.add(el);
    el.classList.add("zg-item");
  }
  function scan() { document.querySelectorAll(SEL).forEach(register); }
  var mo = new MutationObserver(function () { if (FX.zero) { scan(); items.forEach(function (el) { if (!document.body.contains(el)) items.delete(el); }); } });
  mo.observe(document.body, { childList: true, subtree: true });
  window.addEventListener("resize", function () { items.forEach(function (el) { var s = st.get(el); if (s) s.dirty = true; }); });
  $("thread-canvas") && $("thread-canvas").addEventListener("scroll", function () { items.forEach(function (el) { var s = st.get(el); if (s) s.dirty = true; }); }, { passive: true });

  function step(t) {
    if (!FX.zero) { loop = 0; return; }
    loop = requestAnimationFrame(step);
    var dt = Math.min((t - lastT) / 1000, 0.05); lastT = t; var sec = t / 1000;
    items.forEach(function (el) {
      var s = st.get(el); if (!s) return;
      if (s.dirty) { bounds(el); s.dirty = false; }
      if (s.drag) return;
      s.vx += (Math.random() - 0.5) * 16 * dt;            // faint random wander
      s.vy += (Math.random() - 0.5) * 16 * dt - 1.2 * dt; // slight upward bias = anti-gravity
      s.vx *= 1 - 0.55 * dt; s.vy *= 1 - 0.55 * dt;
      s.x += s.vx * dt; s.y += s.vy * dt + Math.sin(sec * 0.9 + s.ph) * 0.18;
      if (s.x < s.minX) { s.x = s.minX; s.vx = Math.abs(s.vx) * 0.6; }
      if (s.x > s.maxX) { s.x = s.maxX; s.vx = -Math.abs(s.vx) * 0.6; }
      if (s.y < s.minY) { s.y = s.minY; s.vy = Math.abs(s.vy) * 0.6; }
      if (s.y > s.maxY) { s.y = s.maxY; s.vy = -Math.abs(s.vy) * 0.6; }
      var tr = Math.max(-5, Math.min(5, s.vx * 0.18)) + Math.sin(sec * 0.7 + s.ph) * 0.8;
      s.r += (tr - s.r) * 0.08;
      el.style.translate = s.x.toFixed(1) + "px " + s.y.toFixed(1) + "px";
      el.style.rotate = s.r.toFixed(2) + "deg";
    });
  }

  document.addEventListener("pointerdown", function (e) {
    if (!FX.zero || e.button > 0) return;
    var el = e.target.closest && e.target.closest(".zg-item");
    if (!el || e.target.closest("a,button,summary,input,textarea,select,.cite")) return;
    var s = st.get(el); if (!s) return;
    if (s.dirty) { bounds(el); s.dirty = false; }
    drag = { el: el, sx: e.clientX, sy: e.clientY, ox: s.x, oy: s.y, lx: e.clientX, ly: e.clientY, lt: performance.now() };
    s.drag = true; s.vx = s.vy = 0;
    el.classList.add("is-dragging");
    try { el.setPointerCapture(e.pointerId); } catch (_) {}
    e.preventDefault();
  });
  document.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var s = st.get(drag.el), now = performance.now(), dt = Math.max(1, now - drag.lt) / 1000;
    s.x = Math.max(s.minX, Math.min(s.maxX, drag.ox + e.clientX - drag.sx));
    s.y = Math.max(s.minY, Math.min(s.maxY, drag.oy + e.clientY - drag.sy));
    s.vx = 0.6 * s.vx + 0.4 * ((e.clientX - drag.lx) / dt); s.vy = 0.6 * s.vy + 0.4 * ((e.clientY - drag.ly) / dt);
    drag.lx = e.clientX; drag.ly = e.clientY; drag.lt = now;
    s.r = Math.max(-8, Math.min(8, s.vx * 0.012));
    drag.el.style.translate = s.x.toFixed(1) + "px " + s.y.toFixed(1) + "px";
    drag.el.style.rotate = s.r.toFixed(2) + "deg";
  });
  function release() {
    if (!drag) return;
    var s = st.get(drag.el);
    s.drag = false;
    s.vx = Math.max(-900, Math.min(900, s.vx)) * 0.35; s.vy = Math.max(-900, Math.min(900, s.vy)) * 0.35;   // throw!
    drag.el.classList.remove("is-dragging");
    drag = null;
  }
  document.addEventListener("pointerup", release);
  document.addEventListener("pointercancel", release);

  FX.setZeroG = function (on) {
    on = !!on && !reduce;
    FX.zero = on;
    document.body.classList.toggle("zerog", on);
    var btn = $("zg-btn"); if (btn) btn.setAttribute("aria-pressed", on ? "true" : "false");
    if (window.Scene3D) window.Scene3D.setZeroG(on);
    resetTilt(tiltEl); tiltEl = null;
    if (on) {
      scan();
      items.forEach(function (el) { el.style.transition = ""; var s = st.get(el); if (s) s.dirty = true; });
      lastT = performance.now();
      if (!loop) loop = requestAnimationFrame(step);
      FX.toast("Zero-G on. Drag any card and throw it. Click the orbit button again to restore gravity.");
    } else {
      items.forEach(function (el) {
        var s = st.get(el);
        el.style.transition = "translate .9s cubic-bezier(.2,.8,.2,1), rotate .9s cubic-bezier(.2,.8,.2,1)";
        el.style.translate = "0px 0px"; el.style.rotate = "0deg";
        if (s) { s.x = s.y = s.r = 0; }
        setTimeout(function () { el.style.transition = ""; el.style.translate = ""; el.style.rotate = ""; el.classList.remove("zg-item", "is-dragging"); }, 1000);
      });
      items.clear();
      FX.toast("Gravity restored.");
    }
  };
})();
