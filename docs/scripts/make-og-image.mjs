/**
 * Generate the 1200x630 social card at public/og.png.
 *
 * The site sets `twitter:card = summary_large_image`, which promises an image —
 * without one, shares on X, Slack, Discord and LinkedIn render as a bare text
 * card. og:image also requires a raster format, so the SVG logo can't be used.
 *
 *   node scripts/make-og-image.mjs
 */
import sharp from 'sharp';
import { fileURLToPath } from 'node:url';

const W = 1200;
const H = 630;

// System font stack — the SVG renderer has no access to the site's webfont.
const FONT = "DejaVu Sans, Segoe UI, Helvetica, Arial, sans-serif";

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <radialGradient id="glow1" cx="50%" cy="0%" r="70%">
      <stop offset="0%" stop-color="#6366f1" stop-opacity="0.42"/>
      <stop offset="100%" stop-color="#6366f1" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glow2" cx="88%" cy="18%" r="55%">
      <stop offset="0%" stop-color="#8b5cf6" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="#8b5cf6" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#a5b4fc"/>
      <stop offset="55%" stop-color="#c4b5fd"/>
      <stop offset="100%" stop-color="#93c5fd"/>
    </linearGradient>
  </defs>

  <rect width="${W}" height="${H}" fill="#08080a"/>
  <rect width="${W}" height="${H}" fill="url(#glow1)"/>
  <rect width="${W}" height="${H}" fill="url(#glow2)"/>

  <!-- logo mark -->
  <rect x="88" y="104" width="70" height="70" rx="16" fill="#4f46e5"/>
  <text x="123" y="152" font-family="${FONT}" font-size="42" font-weight="bold"
        fill="#ffffff" text-anchor="middle">B</text>

  <text x="176" y="153" font-family="${FONT}" font-size="40" font-weight="bold"
        fill="#ffffff">Buraq</text>

  <!-- headline -->
  <text x="88" y="290" font-family="${FONT}" font-size="66" font-weight="bold" fill="#ffffff">
    The async Python framework
  </text>
  <text x="88" y="372" font-family="${FONT}" font-size="66" font-weight="bold" fill="url(#accent)">
    you already know how to use
  </text>

  <!-- supporting line -->
  <text x="88" y="446" font-family="${FONT}" font-size="27" fill="#a1a1aa">
    Django's ORM, admin, forms and CBVs — fully async, on FastAPI + SQLAlchemy 2.0
  </text>

  <!-- footer rule + url -->
  <rect x="88" y="516" width="1024" height="1" fill="#ffffff" fill-opacity="0.12"/>
  <text x="88" y="562" font-family="${FONT}" font-size="24" fill="#71717a">buraqproject.com</text>
</svg>`;

const out = fileURLToPath(new URL('../public/og.png', import.meta.url));

await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(out);

const { size } = await import('node:fs').then((fs) => fs.promises.stat(out));
console.log(`Wrote public/og.png — ${W}x${H}, ${(size / 1024).toFixed(0)} KB`);
