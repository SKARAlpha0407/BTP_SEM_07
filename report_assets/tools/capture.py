"""Capture report screenshots of the running Kavosh app with headless Brave (CDP).

Usage: python capture.py OUT_DIR TOPIC
Needs ./dev.sh running (frontend :3000, backend :8000).
"""
import asyncio, base64, json, os, subprocess, sys, time
import requests, websockets

HIDE_DEV_JS = """(() => { let st = document.getElementById('hide-next-dev');
  if (!st) { st = document.createElement('style'); st.id = 'hide-next-dev';
    st.textContent = 'nextjs-portal, [data-nextjs-dev-tools-button], [data-next-badge-root], [data-nextjs-toast], #devtools-indicator { display: none !important; }';
    document.head.appendChild(st); }
  document.querySelectorAll('nextjs-portal').forEach(e => e.style.display = 'none'); return true; })()"""
BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
PORT = 9333
OUT, TOPIC = (sys.argv[1], sys.argv[2]) if __name__ == "__main__" else (None, None)


class CDP:
    def __init__(self, ws):
        self.ws, self.i = ws, 0

    async def call(self, method, **params):
        self.i += 1
        my = self.i
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    async def js(self, expr):
        r = await self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")

    async def shot(self, name):
        # Hide the Next.js development badge; it is not part of the app.
        await self.js(HIDE_DEV_JS)
        r = await self.call("Page.captureScreenshot", format="png")
        with open(os.path.join(OUT, name), "wb") as fh:
            fh.write(base64.b64decode(r["data"]))
        print("saved", name, flush=True)

    async def wait_for(self, expr, timeout=180):
        t = time.time()
        while time.time() - t < timeout:
            if await self.js(expr):
                return True
            await asyncio.sleep(0.5)
        raise TimeoutError(expr)


SEARCH_JS = """(() => { const i = document.querySelector('input[aria-label="Research topic"]');
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  set.call(i, %s); i.dispatchEvent(new Event('input', {bubbles: true}));
  i.closest('form').requestSubmit(); return true; })()"""

DONE_JS = "!document.querySelector('[aria-busy=true]') && !!document.querySelector('header p')"


async def main():
    os.makedirs(OUT, exist_ok=True)
    proc = subprocess.Popen([BRAVE, "--headless=new", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=/private/tmp/claude-501/brave-capture",
                             "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                             "--window-size=1440,900", "--hide-scrollbars", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                tabs = requests.get(f"http://127.0.0.1:{PORT}/json").json()
                break
            except Exception:
                time.sleep(0.25)
        page = next(t for t in tabs if t["type"] == "page")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
            c = CDP(ws)
            await c.call("Page.enable")
            await c.call("Runtime.enable")
            await c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=2, mobile=False)
            await c.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"},
                                                                  {"name": "prefers-reduced-motion", "value": "reduce"}])
            await c.call("Page.navigate", url="http://localhost:3000/")
            await c.wait_for("!!document.querySelector('input[aria-label=\"Research topic\"]')")
            await asyncio.sleep(4)
            await c.shot("01_start_page.png")

            await c.js(SEARCH_JS % json.dumps(TOPIC))
            await asyncio.sleep(1.5)
            await c.shot("02_searching.png")
            await c.wait_for(DONE_JS)
            await asyncio.sleep(6)  # map layout and reveal
            badge = await c.js("document.querySelector('header p')?.innerText")
            print("badge:", badge)
            await c.shot("03_results.png")

            # open the first ranked paper: reader shows summary + grounding; map highlights neighbours
            await c.js("(() => { const t = [...document.querySelectorAll('aside li button, aside button')]"
                       ".find(b => /^0?1/.test(b.innerText.trim())); (t || document.querySelector('aside li')).click(); return true; })()")
            await asyncio.sleep(4)
            await c.shot("04_paper_view.png")
            await c.js("(() => { const g = [...document.querySelectorAll('article p')].find(p => p.innerText.includes('Summary check'));"
                       " if (g) g.scrollIntoView({block: 'center'}); return !!g; })()")
            await asyncio.sleep(2)
            await c.shot("05_grounding_check.png")

            # repeat the same search: served as a saved answer
            await c.js(SEARCH_JS % json.dumps(TOPIC))
            await c.wait_for(DONE_JS)
            await asyncio.sleep(5)
            print("badge after repeat:", await c.js("document.querySelector('header p')?.innerText"))
            await c.shot("06_saved_answer.png")
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
