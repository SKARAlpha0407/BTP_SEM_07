#!/usr/bin/env python3
import time, concurrent.futures as cf
import requests

BASE = "http://localhost:8000"
RESULTS = []

def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

def post(payload, t=10, origin=None):
    h = {"Origin": origin} if origin else {}
    return requests.post(f"{BASE}/search", json=payload, timeout=t, headers=h)

# --- A. Validation must fast-fail BEFORE the pipeline (all <5s) ---
for name, payload in [
    ("missing topic", {}), ("empty topic", {"topic": ""}),
    ("whitespace topic", {"topic": "   "}), ("non-string topic", {"topic": 123}),
    ("oversized topic", {"topic": "x" * 5000}),
    ("max_results=0", {"topic": "attention", "max_results": 0}),
    ("max_results=-3", {"topic": "attention", "max_results": -3}),
    ("max_results=10000", {"topic": "attention", "max_results": 10000}),
]:
    t0 = time.time()
    try:
        r = post(payload)
        check(f"422 fast: {name}", r.status_code == 422 and time.time() - t0 < 5,
              f"got {r.status_code} in {time.time()-t0:.1f}s")
    except requests.exceptions.Timeout:
        check(f"422 fast: {name}", False, f"TIMEOUT (hang) after {time.time()-t0:.1f}s")
    except Exception as e:
        check(f"422 fast: {name}", False, repr(e))

t0 = time.time()
try:
    r = requests.post(f"{BASE}/search", data="{not json",
                      headers={"Content-Type": "application/json"}, timeout=10)
    check("422 fast: malformed JSON", r.status_code == 422 and time.time()-t0 < 5, f"{r.status_code}")
except Exception as e:
    check("422 fast: malformed JSON", False, repr(e))

check("GET /search -> 405", requests.get(f"{BASE}/search", timeout=5).status_code == 405)

t0 = time.time()
with cf.ThreadPoolExecutor(max_workers=10) as ex:
    codes = list(ex.map(lambda _: post({"topic": ""}, t=10).status_code, range(10)))
check("burst 10x empty -> all 422, none hang", codes == [422]*10,
      f"{codes} in {time.time()-t0:.1f}s")

# --- B. CORS (uses 422 responses — fast, no pipeline burn) ---
r = post({"topic": ""}, origin="http://localhost:3000")
acao = r.headers.get("access-control-allow-origin")
check("ACAO present on allowed origin (422 responses included)", acao in ("http://localhost:3000", "*"), f"{acao!r}")
pf = requests.options(f"{BASE}/search", headers={
    "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}, timeout=5)
check("preflight OPTIONS 2xx + ACAO", pf.status_code in (200, 204) and pf.headers.get("access-control-allow-origin"), f"{pf.status_code}")
r = post({"topic": ""}, origin="http://evil.example")
acao = r.headers.get("access-control-allow-origin")
check("no origin echo for disallowed origin", acao in (None, "", "*"), f"{acao!r}")

# --- C. Functional + cluster invariant ---
def invariant_ok(resp):
    try:
        g = resp.json().get("graph", {})
        nodes = g.get("nodes")
        # Note: the prompt mentions edges but the current backend returns 'links'
        links = g.get("links") 
        if not isinstance(nodes, list) or not nodes or not isinstance(links, list):
            return False, "bad graph shape"
        bad = [n.get("id") for n in nodes
               if not (isinstance(n.get("cluster"), str) and n["cluster"].strip())]
        return (not bad), (f"{len(bad)}/{len(nodes)} nodes missing cluster" if bad
                           else f"{len(nodes)} nodes / {len(links)} edges, clusters OK")
    except Exception as e:
        return False, repr(e)

def run_search(topic, n=3, t=120):
    t0 = time.time()
    return post({"topic": topic, "max_results": n}, t=t), time.time() - t0

for name, topic in [("single char 'a'", "a"), ("unicode + emoji", "量子コンピュータ 🚀")]:
    try:
        r, dt = run_search(topic)
        ok, det = invariant_ok(r) if r.status_code == 200 else (400 <= r.status_code < 500, f"clean {r.status_code}")
        check(f"no-hang + graceful: {name}", ok and dt < 90, f"{det} in {dt:.1f}s")
    except Exception as e:
        check(f"no-hang + graceful: {name}", False, repr(e))

try:
    r, dt = run_search("retrieval augmented generation")
    ok, det = invariant_ok(r) if r.status_code == 200 else (False, f"{r.status_code}")
    check("canonical search: 200 + valid clustered graph", ok and dt < 90, f"{det} in {dt:.1f}s")
except Exception as e:
    check("canonical search: 200 + valid clustered graph", False, repr(e))

# --- D. Mixed concurrency: bad request returns fast WHILE goods run ---
try:
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(run_search, ""); f2 = ex.submit(run_search, "graph neural networks")
        f3 = ex.submit(run_search, "transformer architecture")
        r_bad, dt_bad = f1.result(); r1, _ = f2.result(); r2, _ = f3.result()
    ok = (r_bad.status_code == 422 and dt_bad < 5 and r1.status_code == 200 and r2.status_code == 200
          and invariant_ok(r1)[0] and invariant_ok(r2)[0])
    check("mixed load: bad fast-422, goods 200+valid", ok,
          f"bad={r_bad.status_code}/{dt_bad:.1f}s goods={r1.status_code},{r2.status_code}")
except Exception as e:
    check("mixed load: bad fast-422, goods 200+valid", False, repr(e))

passed = sum(1 for _, ok, _ in RESULTS if ok)
print("\n" + "=" * 60 + f"\nREGRESSION v2: {passed}/{len(RESULTS)} PASS")
print("VERDICT: SHIP" if passed == len(RESULTS) else "VERDICT: FIX AGAIN")
with open(".deployment_status/8_regression_v2_report.txt", "w") as f:
    for name, ok, det in RESULTS:
        f.write(f"{'PASS' if ok else 'FAIL'}  {name}  {det}\n")
    f.write(f"\nVERDICT: {passed}/{len(RESULTS)}\n")
