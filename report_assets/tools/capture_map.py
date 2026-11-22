"""Capture the reading-map pane (dark theme) for one topic, with the first paper selected."""
import asyncio, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import requests, websockets
from capture import CDP, SEARCH_JS, DONE_JS, BRAVE, HIDE_DEV_JS

OUT, TOPIC = sys.argv[1], sys.argv[2]
PORT = 9334


async def main():
    proc = subprocess.Popen([BRAVE, "--headless=new", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=/private/tmp/claude-501/brave-capture-map",
                             "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                             "--window-size=1440,900", "--hide-scrollbars", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                tabs = requests.get(f"http://127.0.0.1:{PORT}/json").json(); break
            except Exception:
                time.sleep(0.25)
        page = next(t for t in tabs if t["type"] == "page")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=80_000_000) as ws:
            c = CDP(ws)
            await c.call("Page.enable"); await c.call("Runtime.enable")
            await c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=2, mobile=False)
            await c.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark"},
                                                                  {"name": "prefers-reduced-motion", "value": "reduce"}])
            await c.call("Page.navigate", url="http://localhost:3000/")
            await c.wait_for("!!document.querySelector('input[aria-label=\"Research topic\"]')")
            await asyncio.sleep(2)
            await c.js(SEARCH_JS % json.dumps(TOPIC))
            await c.wait_for(DONE_JS)
            await asyncio.sleep(6)
            await c.js("(() => { const t = [...document.querySelectorAll('aside li button, aside button')]"
                       ".find(b => /^0?1/.test(b.innerText.trim())); (t || document.querySelector('aside li')).click(); return true; })()")
            await asyncio.sleep(4)
            await c.js(HIDE_DEV_JS)
            rect = await c.js("(() => { const h = [...document.querySelectorAll('section')].find(s => s.innerText.toUpperCase().includes('READING MAP'));"
                              " const r = h.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })()")
            print("map pane", rect)
            import base64
            r = await c.call("Page.captureScreenshot", format="png",
                             clip={"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"], "scale": 1})
            with open(os.path.join(OUT, "07_reading_map_dark.png"), "wb") as fh:
                fh.write(base64.b64decode(r["data"]))
            print("saved 07_reading_map_dark.png")
    finally:
        proc.terminate()

asyncio.run(main())
