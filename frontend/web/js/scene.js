/* Background 3D scene: a weightless "knowledge network".
 *
 *  - Nodes drift UPWARD (anti-gravity) and flee the cursor; nearby nodes link with fading lines.
 *  - A wireframe core floats and slowly rotates, with a counter-rotating inner shell.
 *  - Functional meaning: while the assistant searches, nodes spiral into the core (retrieval);
 *    when the answer arrives, exactly `k` nodes (= passages retrieved) light up in the status
 *    colour (green answer / amber clarify / red escalate), then burst outward again.
 *  - Zero-G mode multiplies drift, cursor repulsion and node size.
 *  Gracefully does nothing without WebGL, without Three.js, or with prefers-reduced-motion.
 */
(function () {
  var api = { ok: false, search: function () {}, result: function () {}, idle: function () {}, setZeroG: function () {} };
  window.Scene3D = api;

  var canvas = document.getElementById("bg3d");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!canvas || !window.THREE || reduce) return;

  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true, powerPreference: "low-power" });
  } catch (e) { return; }
  renderer.setClearColor(0x000000, 0);

  var small = window.innerWidth < 768 || (navigator.hardwareConcurrency || 8) <= 4;
  var N = small ? 46 : 88;
  var FOV = 55, CAM_Z = 14;
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100);
  camera.position.z = CAM_Z;

  var COLORS = { search: 0x3c5d9d, answer: 0x059669, clarify: 0xd97706, escalate: 0xdc2626 };
  var BASE = [new THREE.Color(0x0f3876), new THREE.Color(0x3c5d9d), new THREE.Color(0x5d86c8)];

  /* ---------------------------------------------------------------- nodes */
  var pos = new Float32Array(N * 3), vel = new Float32Array(N * 3);
  var size = new Float32Array(N), glow = new Float32Array(N), col = new Float32Array(N * 3);
  var drift = new Float32Array(N), phase = new Float32Array(N), litUntil = new Float32Array(N);
  var halfW = 16, halfH = 9;

  function bounds() {
    var h = Math.tan((FOV * Math.PI) / 360) * CAM_Z;     // visible half-height at z = 0
    halfH = h * 1.12;
    halfW = h * camera.aspect * 1.12;
  }
  function place(i, anywhere) {
    pos[i * 3] = (Math.random() * 2 - 1) * halfW;
    pos[i * 3 + 1] = anywhere ? (Math.random() * 2 - 1) * halfH : -halfH - Math.random() * 2;
    pos[i * 3 + 2] = -11 + Math.random() * 14;
  }
  for (var i = 0; i < N; i++) {
    place(i, true);
    size[i] = 0.8 + Math.random() * 1.4;
    drift[i] = 0.18 + Math.random() * 0.42;
    phase[i] = Math.random() * 6.28;
    var c = BASE[(Math.random() * BASE.length) | 0];
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }

  var pg = new THREE.BufferGeometry();
  pg.setAttribute("position", new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
  pg.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
  pg.setAttribute("aGlow", new THREE.BufferAttribute(glow, 1).setUsage(THREE.DynamicDrawUsage));
  pg.setAttribute("aColor", new THREE.BufferAttribute(col, 3));
  var glowColor = new THREE.Color(COLORS.search);
  var pointMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { uPR: { value: 1 }, uGlowColor: { value: glowColor }, uScale: { value: 1 } },
    vertexShader: [
      "attribute float aSize; attribute float aGlow; attribute vec3 aColor;",
      "varying float vGlow; varying vec3 vColor; varying float vFade; uniform float uPR; uniform float uScale;",
      "void main(){ vec4 mv = modelViewMatrix * vec4(position,1.0); gl_Position = projectionMatrix * mv;",
      " gl_PointSize = aSize * uScale * uPR * (230.0 / -mv.z) * (1.0 + aGlow * 1.3);",
      " vGlow = aGlow; vColor = aColor; vFade = clamp(1.0 - (-mv.z - 6.0) / 34.0, 0.22, 1.0); }"
    ].join("\n"),
    fragmentShader: [
      "precision mediump float; varying float vGlow; varying vec3 vColor; varying float vFade; uniform vec3 uGlowColor;",
      "void main(){ vec2 c = gl_PointCoord - 0.5; float d = length(c); if (d > 0.5) discard;",
      " float core = smoothstep(0.5, 0.12, d); float halo = smoothstep(0.5, 0.0, d) * 0.4;",
      " vec3 col = mix(vColor, uGlowColor, vGlow); float a = (core * 0.9 + halo) * vFade * (0.5 + 0.5 * vGlow);",
      " gl_FragColor = vec4(col, a); }"
    ].join("\n")
  });
  scene.add(new THREE.Points(pg, pointMat));

  /* ---------------------------------------------------------------- links */
  var MAXL = N * 5, LINK = small ? 3.4 : 4.1;
  var lpos = new Float32Array(MAXL * 6), lalpha = new Float32Array(MAXL * 2), lglow = new Float32Array(MAXL * 2);
  var lg = new THREE.BufferGeometry();
  lg.setAttribute("position", new THREE.BufferAttribute(lpos, 3).setUsage(THREE.DynamicDrawUsage));
  lg.setAttribute("aAlpha", new THREE.BufferAttribute(lalpha, 1).setUsage(THREE.DynamicDrawUsage));
  lg.setAttribute("aGlow", new THREE.BufferAttribute(lglow, 1).setUsage(THREE.DynamicDrawUsage));
  var lineMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { uGlowColor: { value: glowColor } },
    vertexShader: "attribute float aAlpha; attribute float aGlow; varying float vA; varying float vG; void main(){ vA=aAlpha; vG=aGlow; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
    fragmentShader: "precision mediump float; varying float vA; varying float vG; uniform vec3 uGlowColor; void main(){ vec3 base = vec3(0.06,0.22,0.46); gl_FragColor = vec4(mix(base,uGlowColor,vG), vA * (0.8 + vG * 0.9)); }"
  });
  var lines = new THREE.LineSegments(lg, lineMat);
  lines.frustumCulled = false;
  scene.add(lines);

  /* ----------------------------------------------------------------- core */
  var core = new THREE.Group();
  var shellMat = new THREE.LineBasicMaterial({ color: 0x0f3876, transparent: true, opacity: 0.2 });
  var shell = new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(2.9, 1)), shellMat);
  var innerMat = new THREE.LineBasicMaterial({ color: 0x3c5d9d, transparent: true, opacity: 0.32 });
  var inner = new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.OctahedronGeometry(1.5, 0)), innerMat);
  core.add(shell); core.add(inner);
  scene.add(core);
  var coreHome = new THREE.Vector3(0, 0, -2);

  /* ----------------------------------------------------------- interaction */
  var mouse = { x: 0, y: 0, tx: 0, ty: 0, active: false };
  window.addEventListener("pointermove", function (e) {
    mouse.tx = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.ty = -((e.clientY / window.innerHeight) * 2 - 1);
    mouse.active = true;
  }, { passive: true });
  window.addEventListener("pointerleave", function () { mouse.active = false; });

  var baseScale = 1, mode = "idle", zero = false, spin = 1, pulse = 0, burstAt = 0, resultTimer = 0;

  function resize() {
    var w = window.innerWidth, h = window.innerHeight;
    var pr = Math.min(window.devicePixelRatio || 1, 1.75);
    renderer.setPixelRatio(pr);
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    pointMat.uniforms.uPR.value = pr;
    bounds();
    var wide = w > 900;
    baseScale = w < 640 ? 0.55 : w < 900 ? 0.8 : 1;
    coreHome.set(wide ? halfW * 0.34 : 0, wide ? -halfH * 0.04 : -halfH * 0.3, -2);
  }
  window.addEventListener("resize", resize);
  resize();

  function lightNearest(k, color) {
    glowColor.setHex(color);
    var cx = core.position.x, cy = core.position.y, idx = [];
    for (var i = 0; i < N; i++) {
      var dx = pos[i * 3] - cx, dy = pos[i * 3 + 1] - cy, dz = pos[i * 3 + 2] + 2;
      idx.push([dx * dx + dy * dy + dz * dz * 0.3, i]);
    }
    idx.sort(function (a, b) { return a[0] - b[0]; });
    var t = performance.now() / 1000;
    for (var j = 0; j < Math.min(k, N); j++) { glow[idx[j][1]] = 1; litUntil[idx[j][1]] = t + 3.2; }
  }

  api.ok = true;
  api.search = function () { clearTimeout(resultTimer); mode = "search"; glowColor.setHex(COLORS.search); };
  api.idle = function () { mode = "idle"; };
  api.result = function (status, k) {
    mode = "result";
    pulse = 1;
    lightNearest(Math.max(3, k || 5), COLORS[status] || COLORS.answer);
    shellMat.color.setHex(COLORS[status] || 0x0f3876);
    clearTimeout(resultTimer);
    resultTimer = setTimeout(function () {
      mode = "idle"; burstAt = performance.now() / 1000;
      shellMat.color.setHex(0x0f3876);
    }, 2400);
  };
  api.setZeroG = function (on) { zero = !!on; pointMat.uniforms.uScale.value = zero ? 1.35 : 1; };

  /* ------------------------------------------------------------------ loop */
  var last = performance.now() / 1000, running = true, tmpV = new THREE.Vector3();
  document.addEventListener("visibilitychange", function () {
    running = !document.hidden;
    if (running) { last = performance.now() / 1000; loop(); }
  });

  function loop() {
    if (!running) return;
    requestAnimationFrame(loop);
    var now = performance.now() / 1000;
    var dt = Math.min(now - last, 0.05); last = now;
    mouse.x += (mouse.tx - mouse.x) * 0.06; mouse.y += (mouse.ty - mouse.y) * 0.06;

    // camera parallax
    camera.position.x += (mouse.x * 1.3 - camera.position.x) * 0.035;
    camera.position.y += (mouse.y * 0.8 - camera.position.y) * 0.035;
    camera.lookAt(0, 0, 0);

    // core
    var targetSpin = mode === "search" ? 5 : mode === "result" ? 2.2 : 1;
    spin += (targetSpin - spin) * 0.05;
    pulse *= 0.96;
    core.position.x += (coreHome.x - core.position.x) * 0.04;
    core.position.y = coreHome.y + Math.sin(now * 0.7) * 0.45 + (zero ? Math.sin(now * 1.3) * 0.5 : 0);
    core.position.z = coreHome.z;
    shell.rotation.y += dt * 0.18 * spin; shell.rotation.x += dt * 0.07 * spin;
    inner.rotation.y -= dt * 0.35 * spin; inner.rotation.z += dt * 0.12 * spin;
    var s = 1 + pulse * 0.28 + (mode === "search" ? Math.sin(now * 6) * 0.04 : 0);
    core.scale.setScalar(s * baseScale);
    shellMat.opacity = 0.2 + pulse * 0.35 + (mode === "search" ? 0.12 : 0);
    innerMat.opacity = 0.32 + pulse * 0.4;

    // nodes
    var driftMul = zero ? 3.2 : 1, repelR = zero ? 5.2 : 3.4, repelK = zero ? 26 : 13;
    var mwx = mouse.x * halfW / 1.12, mwy = mouse.y * halfH / 1.12;
    var burst = now - burstAt < 0.9 && burstAt > 0;
    for (var i = 0; i < N; i++) {
      var ix = i * 3, iy = ix + 1, iz = ix + 2;
      var x = pos[ix], y = pos[iy], z = pos[iz];
      var ax = 0, ay = 0, az = 0;

      // cursor repulsion (projected into screen-plane space)
      if (mouse.active) {
        var f = CAM_Z / (CAM_Z - z), sx = x * f - mwx, sy = y * f - mwy, d2 = sx * sx + sy * sy;
        if (d2 < repelR * repelR) {
          var d = Math.sqrt(d2) + 0.001, w = (1 - d / repelR);
          ax += (sx / d) * w * repelK; ay += (sy / d) * w * repelK;
        }
      }
      // gentle orbital sway
      ax += Math.sin(now * 0.4 + phase[i]) * 0.35;
      az += Math.cos(now * 0.33 + phase[i]) * 0.25;

      if (mode === "search") {                      // retrieval vortex
        var dx = core.position.x - x, dy = core.position.y - y, dz = core.position.z - z;
        var dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01;
        ax += (dx / dist) * 5.5 + (-dy / dist) * 3.4;
        ay += (dy / dist) * 5.5 + (dx / dist) * 3.4;
        az += (dz / dist) * 3.0;
      } else if (burst) {                           // outward release after the answer
        var ox = x - core.position.x, oy = y - core.position.y, od = Math.sqrt(ox * ox + oy * oy) + 0.01;
        ax += (ox / od) * 22; ay += (oy / od) * 22;
      }
      if (zero) { ax += Math.sin(now * 0.8 + phase[i] * 2) * 1.4; ay += Math.cos(now * 0.6 + phase[i]) * 1.2; }

      vel[ix] += ax * dt; vel[iy] += ay * dt; vel[iz] += az * dt;
      var damp = 1 - (mode === "search" ? 1.6 : 0.9) * dt;
      vel[ix] *= damp; vel[iz] *= damp;
      // vertical velocity relaxes to this node's anti-gravity drift
      vel[iy] += (drift[i] * driftMul - vel[iy]) * 0.9 * dt * (mode === "search" ? 0.2 : 1);
      pos[ix] = x + vel[ix] * dt; pos[iy] = y + vel[iy] * dt; pos[iz] = z + vel[iz] * dt;

      if (pos[iy] > halfH + 1.5) { place(i, false); vel[ix] = vel[iy] = vel[iz] = 0; glow[i] = 0; }
      if (pos[ix] > halfW + 2) pos[ix] = -halfW - 1; else if (pos[ix] < -halfW - 2) pos[ix] = halfW + 1;
      if (pos[iz] > 5) vel[iz] -= 2 * dt; else if (pos[iz] < -13) vel[iz] += 2 * dt;

      if (glow[i] > 0 && now > litUntil[i]) glow[i] = Math.max(0, glow[i] - dt * 0.9);
    }

    // links
    var n = 0, link2 = LINK * LINK;
    for (var a = 0; a < N && n < MAXL; a++) {
      for (var b = a + 1; b < N && n < MAXL; b++) {
        var ddx = pos[a * 3] - pos[b * 3], ddy = pos[a * 3 + 1] - pos[b * 3 + 1], ddz = pos[a * 3 + 2] - pos[b * 3 + 2];
        var dd = ddx * ddx + ddy * ddy + ddz * ddz;
        if (dd < link2) {
          var al = (1 - Math.sqrt(dd) / LINK) * 0.55;
          var o = n * 6;
          lpos[o] = pos[a * 3]; lpos[o + 1] = pos[a * 3 + 1]; lpos[o + 2] = pos[a * 3 + 2];
          lpos[o + 3] = pos[b * 3]; lpos[o + 4] = pos[b * 3 + 1]; lpos[o + 5] = pos[b * 3 + 2];
          lalpha[n * 2] = lalpha[n * 2 + 1] = al;
          lglow[n * 2] = glow[a]; lglow[n * 2 + 1] = glow[b];
          n++;
        }
      }
    }
    lg.setDrawRange(0, n * 2);
    lg.attributes.position.needsUpdate = true;
    lg.attributes.aAlpha.needsUpdate = true;
    lg.attributes.aGlow.needsUpdate = true;
    pg.attributes.position.needsUpdate = true;
    pg.attributes.aGlow.needsUpdate = true;

    renderer.render(scene, camera);
  }
  loop();
})();
