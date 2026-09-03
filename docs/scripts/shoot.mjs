/**
 * Screenshot a page at a real device size, and report whether it overflows.
 *
 * `chrome --headless --window-size=390,844` does not give a 390px viewport:
 * the window has a platform minimum (about 485px here), and Windows display
 * scaling inflates it further. The screenshot then comes out 390px wide by
 * cropping a wider render, which looks exactly like a layout that overflows --
 * and is not one.
 *
 * So this drives Chrome over the DevTools protocol and sets the metrics
 * properly. No dependencies: Node 22 has WebSocket built in.
 *
 *   node scripts/shoot.mjs <url> [width] [height] [out.png]
 *
 * It prints the viewport it actually got, the document's scroll width, and the
 * widest element sticking out past the edge -- which is the thing to fix when
 * those two numbers differ.
 */
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const CHROME =
  process.env.CHROME_PATH ||
  'C:/Program Files/Google/Chrome/Application/chrome.exe';

const [url, width = '390', height = '844', out = 'shot.png'] = process.argv.slice(2);
if (!url) {
  console.error('usage: node scripts/shoot.mjs <url> [width] [height] [out.png]');
  process.exit(1);
}

const PORT = 9222 + Math.floor(Math.random() * 500);
const profile = `${process.env.TEMP || '/tmp'}/bq-shoot-${PORT}`;

const chrome = spawn(CHROME, [
  '--headless=new',
  '--disable-gpu',
  '--no-sandbox',
  '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`,
  'about:blank',
]);

/** Chrome needs a moment before its debugging port answers. */
async function endpoint() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      return (await res.json()).webSocketDebuggerUrl;
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  throw new Error('Chrome never opened its debugging port');
}

const socket = new WebSocket(await endpoint());
await new Promise((r) => socket.addEventListener('open', r, { once: true }));

let nextId = 0;
const pending = new Map();
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  const settle = pending.get(message.id);
  if (!settle) return;
  pending.delete(message.id);
  message.error ? settle.reject(new Error(message.error.message)) : settle.resolve(message.result);
});

const send = (method, params = {}, sessionId) =>
  new Promise((resolve, reject) => {
    const id = (nextId += 1);
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params, sessionId }));
  });

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
const call = (method, params) => send(method, params, sessionId);

await call('Page.enable');
await call('Runtime.enable');

// The part --window-size cannot do.
await call('Emulation.setDeviceMetricsOverride', {
  width: Number(width),
  height: Number(height),
  deviceScaleFactor: 1,
  mobile: Number(width) < 700,
});

// Starlight follows the system preference until someone picks a theme, so this
// is how the light rendering gets tested without a click.
if (process.env.SCHEME) {
  await call('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-color-scheme', value: process.env.SCHEME }],
  });
}

await call('Page.navigate', { url });
await new Promise((r) => setTimeout(r, 2500));

const { result } = await call('Runtime.evaluate', {
  returnByValue: true,
  expression: `(() => {
    const vw = document.documentElement.clientWidth;
    const sw = document.documentElement.scrollWidth;
    let widest = null, widestRight = vw;
    for (const el of document.querySelectorAll('body *')) {
      const box = el.getBoundingClientRect();
      // Something inside a scroll container sticks out without widening the
      // page, so only count what actually moves the document's scroll width.
      if (box.right > widestRight + 1 && el.scrollWidth <= el.clientWidth + 1) {
        widestRight = box.right;
        widest = el.tagName.toLowerCase() +
          (el.className ? '.' + String(el.className).trim().split(/\\s+/).slice(0, 2).join('.') : '');
      }
    }
    return { vw, sw, overflows: sw > vw + 1, widest };
  })()`,
});

const { data } = await call('Page.captureScreenshot', { format: 'png' });
await mkdir(dirname(resolve(out)), { recursive: true });
await writeFile(resolve(out), Buffer.from(data, 'base64'));

const { vw, sw, overflows, widest } = result.value;
console.log(`  viewport ${vw}px, document ${sw}px`);
console.log(overflows ? `  OVERFLOWS -- widest past the edge: ${widest}` : '  no horizontal overflow');
console.log(`  ${resolve(out)}`);

socket.close();
chrome.kill();
