"""Rigorous ARCH-070 integration test with CSP as a real HTTP header.

meta-tag CSP does not reliably enforce eval-blocking, and Playwright's
add_script_tag bypasses CSP entirely. So we serve the page + scripts from a
local HTTP server that sends a genuine `Content-Security-Policy` response header
WITHOUT 'unsafe-eval', and load everything via normal <script src>.

Runs three configurations:
  A. stock Alpine only            -> expected BROKEN (proves eval is truly blocked)
  B. Alpine + CSPExpr evaluator   -> expected WORKING (proves the fix)
  C. same as B but CSP INCLUDES unsafe-eval -> sanity: stock path works there
"""
import threading
import functools
import http.server
import socket
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    "/alpine.min.js": ROOT / "app/static/vendor/alpine.min.js",
    "/evaluator.js": ROOT / "app/static/js/csp/csp-evaluator.js",
    "/adapter.js": ROOT / "app/static/js/csp/alpine-csp-adapter.js",
}

BODY = """<div x-data="{ count:0, name:'Ada', items:['a','b','c'], open:false, log:[], watched:0, gotEvent:'' }" x-init="$watch('count', v => watched = v)" @ping.window="gotEvent = $event.detail">
  <span id="greet" x-text="'Hi '+name"></span>
  <span id="count" x-text="count"></span>
  <span id="parity" x-text="count%2===0?'even':'odd'"></span>
  <button id="inc" @click="count++">inc</button>
  <button id="add5" @click="count+=5; log.push(count)">add5</button>
  <button id="toggle" @click="open=!open">t</button>
  <div id="panel" x-show="open">panel</div>
  <template x-if="count>3"><span id="big">BIG</span></template>
  <ul id="list"><template x-for="(it,i) in items" :key="i"><li x-text="i+':'+it"></li></template></ul>
  <input id="model" x-model="name"><span id="modelout" x-text="name"></span>
  <span id="cls" :class="open?'is-open':'is-closed'">c</span>
  <button id="self" @click="$el.setAttribute('data-hit','1')">s</button>
  <span id="loglen" x-text="log.length"></span>
  <input x-ref="thebox" value="R1">
  <button id="useref" @click="name = $refs.thebox.value">useref</button>
  <button id="fire" @click="$dispatch('ping', 'PONG')">fire</button>
  <span id="watched" x-text="watched"></span>
  <span id="gotevent" x-text="gotEvent"></span>
  <span id="rootok" x-text="$root === $el.closest('[x-data]') ? 'yes' : 'no'"></span>
</div>"""


def make_handler(mode, csp_eval):
    scripts = {
        "stock":   '<script src="/alpine.min.js" defer></script>',
        "csp":     '<script src="/evaluator.js"></script><script src="/adapter.js"></script><script src="/alpine.min.js" defer></script>',
    }[mode]
    csp = "default-src 'self'; script-src 'self'" + (" 'unsafe-eval'" if csp_eval else "")
    html = f"<!doctype html><html><head></head><body>{BODY}{scripts}</body></html>"

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path in FILES:
                data = FILES[self.path].read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            data = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Security-Policy", csp)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return H


def serve(handler):
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


def run_case(pw, mode, csp_eval, label):
    srv, port = serve(make_handler(mode, csp_eval))
    try:
        b = pw.chromium.launch(headless=True)
        pg = b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script("document.addEventListener('securitypolicyviolation',e=>{window.__c=window.__c||[];window.__c.push(e.violatedDirective+'/'+(e.blockedURI||'inline'))})")
        pg.goto(f"http://127.0.0.1:{port}/", wait_until="load")
        pg.wait_for_timeout(500)
        # drive interactions
        try:
            pg.click("#inc")
            pg.wait_for_timeout(30)
            pg.click("#add5")
            pg.wait_for_timeout(30)
            pg.click("#toggle")
            pg.wait_for_timeout(30)
            pg.fill("#model", "Bob")
            pg.wait_for_timeout(30)
            pg.click("#self")
            pg.wait_for_timeout(30)
            pg.click("#useref")
            pg.wait_for_timeout(30)
            pg.click("#fire")
            pg.wait_for_timeout(30)
        except Exception:
            pass
        state = pg.evaluate("""() => ({
            greet: (document.getElementById('greet')||{}).textContent,
            count: (document.getElementById('count')||{}).textContent,
            parity: (document.getElementById('parity')||{}).textContent,
            list: (document.getElementById('list')||{}).textContent.replace(/\\s+/g,' ').trim(),
            modelout: (document.getElementById('modelout')||{}).textContent,
            big: !!document.getElementById('big'),
            cls: (document.getElementById('cls')||{}).getAttribute('class'),
            hit: (document.getElementById('self')||{}).getAttribute('data-hit'),
            loglen: (document.getElementById('loglen')||{}).textContent,
            watched: (document.getElementById('watched')||{}).textContent,
            gotevent: (document.getElementById('gotevent')||{}).textContent,
            rootok: (document.getElementById('rootok')||{}).textContent,
            refname: (document.getElementById('modelout')||{}).textContent,
        })""")
        cspv = pg.evaluate("window.__c||[]")
        b.close()
        evalv = [v for v in cspv if 'eval' in v.lower() or 'script-src' in v.lower()]
        print(f"\n[{label}]")
        print(f"  greet={state['greet']!r} count={state['count']!r} parity={state['parity']!r} "
              f"list={state['list']!r} model={state['modelout']!r} big={state['big']} "
              f"cls={state['cls']!r} hit={state['hit']!r} loglen={state['loglen']!r}")
        print(f"  CSP script/eval violations: {len(evalv)}  pageerrors: {len(errs)}")
        return state, evalv, errs
    finally:
        srv.shutdown()


def main():
    with sync_playwright() as pw:
        # A: stock Alpine, CSP blocks eval -> must be BROKEN
        sA, vA, eA = run_case(pw, "stock", False, "A stock Alpine, CSP WITHOUT unsafe-eval")
        # B: our evaluator, CSP blocks eval -> must WORK
        sB, vB, eB = run_case(pw, "csp", False, "B Alpine+CSPExpr, CSP WITHOUT unsafe-eval")
        # C: stock Alpine, CSP allows eval -> sanity, must work
        sC, vC, eC = run_case(pw, "stock", True, "C stock Alpine, CSP WITH unsafe-eval (control)")

        def works(s): return s["greet"] == "Hi R1" and s["count"] == "6" and s["list"] == "0:a1:b2:c"
        A_broken = not works(sA)
        magics_ok = (sB.get("watched") == "6" and sB.get("gotevent") == "PONG"
                     and sB.get("rootok") == "yes" and sB.get("refname") == "R1")
        B_works = (works(sB) and sB["big"] and sB["cls"] == "is-open" and sB["hit"] == "1"
                   and magics_ok and not vB and not eB)
        print(f"  B magics: watched={sB.get('watched')!r} gotevent={sB.get('gotevent')!r} "
              f"rootok={sB.get('rootok')!r} refname={sB.get('refname')!r}")
        C_works = works(sC)

        print("\n=== VERDICT ===")
        print(f"  A stock+no-eval  BROKEN (control): {A_broken}  {'OK' if A_broken else 'FAIL - eval not actually blocked'}")
        print(f"  B ours+no-eval   WORKS           : {B_works}  {'OK' if B_works else 'FAIL'}")
        print(f"  C stock+eval     WORKS (control) : {C_works}  {'OK' if C_works else 'FAIL'}")
        allpass = A_broken and B_works and C_works
        print("\nRESULT:", "PASS - unsafe-eval can be dropped with the CSP evaluator" if allpass else "FAIL")
        return 0 if allpass else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
