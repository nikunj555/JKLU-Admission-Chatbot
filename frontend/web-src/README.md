# Front-end build sources (only needed if you want to change the design)

The shipped UI in `../web/` is already compiled and works **offline** (no CDN): compiled Tailwind CSS,
bundled Three.js, bundled Inter / JetBrains Mono fonts, inline SVG icons.

To change styles or classes:

    cd frontend/web-src
    npm install tailwindcss@3 three@0.128.0 lucide-static @fontsource-variable/inter @fontsource/jetbrains-mono
    node build_assets.js        # regenerates js/icons.js, copies fonts + three.min.js
    npx tailwindcss -c tailwind.config.js -i input.css -o ../web/css/app.css --minify

Design tokens come from the Stitch "Academic Clarity" system (see tailwind.config.js).
