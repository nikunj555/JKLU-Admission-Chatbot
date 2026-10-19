/** Design tokens come from the Stitch "Academic Clarity" design system (DESIGN.md). */
module.exports = {
  content: ["../web/index.html", "../web/js/*.js"],
  theme: {
    extend: {
      colors: {
        surface: "#f8f9ff", "surface-dim": "#cbdbf5", "surface-container-lowest": "#ffffff",
        "surface-container-low": "#eff4ff", "surface-container": "#e5eeff", "surface-container-high": "#dce9ff",
        "surface-container-highest": "#d3e4fe", "on-surface": "#0b1c30", "on-surface-variant": "#434750",
        outline: "#747781", "outline-variant": "#c4c6d2", primary: "#002353", "on-primary": "#ffffff",
        "primary-container": "#0f3876", "on-primary-container": "#84a4e8", secondary: "#515f74",
        "surface-tint": "#3c5d9d", error: "#ba1a1a",
      },
      fontFamily: {
        sans: ["Inter Variable", "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        code: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"],
      },
      borderRadius: { xl: "0.75rem", "2xl": "1rem", "3xl": "1.5rem" },
      boxShadow: {
        float: "0 18px 40px -18px rgba(15,56,118,.35), 0 6px 14px -8px rgba(15,56,118,.18)",
        soft: "0 1px 2px rgba(11,28,48,.05), 0 8px 24px -12px rgba(15,56,118,.18)",
      },
    },
  },
};
