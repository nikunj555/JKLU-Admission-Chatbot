// Regenerates web/js/icons.js (inline SVG icons), copies fonts + three.js. Run: node build_assets.js
const fs = require("fs"), path = require("path");
const nm = path.join(__dirname, "node_modules"), web = path.join(__dirname, "..", "web");
const names = ["menu","x","rotate-ccw","chevron-down","send","book-open","info","phone","external-link","landmark","circle-alert","refresh-cw","orbit","shield-check","corner-down-left"];
const out = {};
for (const n of names) {
  const svg = fs.readFileSync(path.join(nm, "lucide-static/icons", n + ".svg"), "utf8");
  out[n] = svg.replace(/^[\s\S]*?<svg[^>]*>/, "").replace(/<\/svg>[\s\S]*$/, "").replace(/\s+/g, " ").trim();
}
fs.writeFileSync(path.join(web, "js/icons.js"),
`/* Inline Lucide icons (ISC licence) - no icon font or CDN needed. */
(function(){
  var P = ${JSON.stringify(out)};
  window.ic = function(name, size, cls){
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="'+(size||20)+'" height="'+(size||20)+'" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="shrink-0 '+(cls||'')+'">'+(P[name]||'')+'</svg>';
  };
  window.hydrateIcons = function(root){
    (root||document).querySelectorAll('[data-ic]').forEach(function(el){
      el.innerHTML = window.ic(el.getAttribute('data-ic'), +el.getAttribute('data-size')||20);
      el.removeAttribute('data-ic');
    });
  };
})();
`);
fs.copyFileSync(path.join(nm, "three/build/three.min.js"), path.join(web, "vendor/three.min.js"));
const f = [["@fontsource-variable/inter/files/inter-latin-wght-normal.woff2"],["@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2"],
  ["@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2"],["@fontsource/jetbrains-mono/files/jetbrains-mono-latin-600-normal.woff2"]];
for (const [p] of f) fs.copyFileSync(path.join(nm, p), path.join(web, "fonts", path.basename(p)));
console.log("assets ok:", Object.keys(out).length, "icons");
