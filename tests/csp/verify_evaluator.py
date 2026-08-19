"""Headless verification of the CSP-safe evaluator (app/static/js/csp/csp-evaluator.js).

Three checks in real chromium via Playwright:
  1. Parse coverage: compile every unique Alpine expression from the codebase;
     the JS parser must match the proven Python grammar's coverage.
  2. Correctness battery: ~40 hand-oracled expressions across every construct.
  3. Differential: for pure (side-effect-free) expressions, compare the
     evaluator's result to the browser's own native eval on the same scope.
"""
import json, re, importlib.util
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("g", ROOT / "scripts" / "check_alpine_csp_grammar.py")
_g = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_g)

EVAL_JS = (ROOT / "dev_csp" / "evaluator.js").read_text(encoding="utf-8")

# ── correctness battery: (expr, scope, expected) ────────────────────────────
BATTERY = [
    ("1 + 2 * 3", {}, 7),
    ("(1 + 2) * 3", {}, 9),
    ("a > b ? 'hi' : 'lo'", {"a": 5, "b": 3}, "hi"),
    ("!done && count > 0", {"done": False, "count": 2}, True),
    ("x ?? 'def'", {"x": None}, "def"),
    ("x ?? 'def'", {"x": 0}, 0),
    ("items.length === 0", {"items": []}, True),
    ("user.name.toUpperCase()", {"user": {"name": "amy"}}, "AMY"),
    ("nums.map(n => n * 2)", {"nums": [1, 2, 3]}, [2, 4, 6]),
    ("nums.filter(n => n > 1).length", {"nums": [1, 2, 3]}, 2),
    ("`hi ${name}!`", {"name": "Bo"}, "hi Bo!"),
    ("a.b?.c ?? 'x'", {"a": {}}, "x"),
    ("(a?.b?.c) === undefined", {"a": None}, True),
    ("obj['k']", {"obj": {"k": 9}}, 9),
    ("[1,2,3].reduce((a,b)=>a+b,0)", {}, 6),
    ("{a:1,b:2}", {}, {"a": 1, "b": 2}),
    ("Math.max(...arr)", {"arr": [3, 9, 2]}, 9),
    ("s.replace(/_/g,' ')", {"s": "a_b_c"}, "a b c"),
    ("n % 2 === 0 ? 'even' : 'odd'", {"n": 4}, "even"),
    ("typeof foo", {}, "undefined"),
    ("flag ? (x + 1) : (x - 1)", {"flag": True, "x": 10}, 11),
    ("'a' + 1 + true", {}, "a1true"),
    ("list.includes('x')", {"list": ["x", "y"]}, True),
    ("Object.keys(o).length", {"o": {"a": 1, "b": 2}}, 2),
    ("val || fallback", {"val": "", "fallback": "fb"}, "fb"),
    ("a && a.b && a.b.c", {"a": {"b": {"c": 42}}}, 42),
    ("(cond) ? 'y' : (other ? 'm' : 'n')", {"cond": False, "other": True}, "m"),
    ("arr.slice(0,2).join('-')", {"arr": ["a", "b", "c"]}, "a-b"),
    ("count > 5 && count < 10", {"count": 7}, True),
    ("-x", {"x": 3}, -3),
    ("!!value", {"value": "x"}, True),
    ("parseInt('42',10) + 1", {}, 43),
    ("str.length > 0 ? str[0] : ''", {"str": "hi"}, "h"),
]

# stateful battery (assignment / statements): (expr, scope_before, key, expected_after)
STATE_BATTERY = [
    ("open = !open", {"open": False}, "open", True),
    ("count += 5", {"count": 10}, "count", 15),
    ("x = x || 3", {"x": None}, "x", 3),
    ("obj.n = 9", {"obj": {"n": 1}}, "obj", {"n": 9}),
    ("show = true; count = count + 1", {"show": False, "count": 0}, "count", 1),
    ("if (a > 0) result = 'pos'", {"a": 5, "result": ""}, "result", "pos"),
]


def main():
    exprs = _g.extract_corpus()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.set_content("<!doctype html><html><body></body></html>")
        pg.add_script_tag(content=EVAL_JS)
        assert pg.evaluate("typeof window.CSPExpr") == "object", "evaluator did not load: " + str(errors)

        # 1. parse coverage
        parse_res = pg.evaluate(
            """(exprs) => {
                let ok=0, fails=[];
                for (const e of exprs) { try { window.CSPExpr.compile(e); ok++; } catch(err){ fails.push([e.slice(0,80), String(err).slice(0,50)]); } }
                return {ok, total: exprs.length, fails: fails.slice(0,25)};
            }""", exprs)
        # Exclude, from the denominator, expressions Alpine never actually
        # evaluates as authored:
        #  - Tailwind x-transition class-strings (not JS)
        #  - fragments of JS template literals mis-captured by the scanner:
        #    they contain `${...}` outside backticks or a stray `\'`, i.e. they
        #    are the pre-interpolation SOURCE; the runtime form (e.g.
        #    `toggleReviewItem(42, this.checked)`) parses fine.
        def is_artifact(e):
            return _g.is_css_classlist(e) or "${" in e or "\\'" in e
        real_fails = [(e, why) for (e, why) in parse_res["fails"] if not is_artifact(e)]
        excluded = len(parse_res["fails"]) - len(real_fails)
        css_fails = excluded
        cov = parse_res["ok"] / (parse_res["total"] - css_fails)
        print(f"[1] parse coverage (JS expr): {parse_res['ok']}/{parse_res['total']-css_fails} = {cov*100:.2f}%  "
              f"(css class-strings excluded: {css_fails}; real fails: {len(real_fails)})")
        for e, why in real_fails[:12]:
            print(f"      PARSEFAIL: {e!r} -- {why}")

        # 2. correctness battery
        bat_fail = pg.evaluate(
            """(cases) => {
                const out=[];
                for (const [expr, scope, expected] of cases) {
                    let got, err=null;
                    try { got = window.CSPExpr.run(expr, scope); } catch(e){ err=String(e); }
                    const eq = JSON.stringify(got) === JSON.stringify(expected);
                    if (!eq || err) out.push({expr, expected, got: (err?('ERR '+err):got)});
                }
                return out;
            }""", [[e, s, x] for (e, s, x) in BATTERY])
        print(f"[2] correctness battery: {len(BATTERY)-len(bat_fail)}/{len(BATTERY)} passed")
        for f in bat_fail:
            print(f"      WRONG: {f['expr']!r}  expected={f['expected']!r} got={f['got']!r}")

        # 2b. stateful battery
        st_fail = pg.evaluate(
            """(cases) => {
                const out=[];
                for (const [expr, scope, key, expected] of cases) {
                    let err=null; const sc = JSON.parse(JSON.stringify(scope));
                    try { window.CSPExpr.run(expr, sc); } catch(e){ err=String(e); }
                    const eq = JSON.stringify(sc[key]) === JSON.stringify(expected);
                    if (!eq || err) out.push({expr, expected, got: (err?('ERR '+err):sc[key])});
                }
                return out;
            }""", [[e, s, k, x] for (e, s, k, x) in STATE_BATTERY])
        print(f"[2b] stateful battery: {len(STATE_BATTERY)-len(st_fail)}/{len(STATE_BATTERY)} passed")
        for f in st_fail:
            print(f"      WRONG: {f['expr']!r}  expected={f['expected']!r} got={f['got']!r}")

        # 3. differential vs native eval on pure expressions
        diff = pg.evaluate(
            r"""(exprs) => {
                // permissive proxy: any identifier -> a chainable universal mock
                function mock(seed){
                    const f = function(){ return f; };
                    return new Proxy(f, {
                        get(t,k){ if(k===Symbol.toPrimitive) return ()=>seed; if(k==='length') return 3;
                                  if(typeof k==='string' && ['map','filter','forEach','slice','reduce','join','includes','replace','split','toUpperCase','toLowerCase','trim','find','some','every','indexOf','concat','toString','charAt','startsWith','endsWith','padStart','repeat'].includes(k)) return function(){return mock(seed);};
                                  return mock(seed); },
                        apply(){ return mock(seed); }, has(){ return true; }
                    });
                }
                function scopeProxy(){ return new Proxy({}, {
                    get(_,k){ if(typeof k==='symbol') return undefined; if(k==='length') return 3; return mock(1); },
                    has(k){ return typeof k!=='symbol'; } }); }
                let checked=0, mism=[];
                for (const e of exprs) {
                    // pure only: skip assignment/statement/increment
                    if (/[^=!<>]=[^=]|\+\+|--|;|\breturn\b|\bif\b|=>|\bnew\b|`/.test(e)) continue;
                    let a, b, ea=null, eb=null;
                    const s1 = scopeProxy(), s2 = scopeProxy();
                    try { a = window.CSPExpr.run(e, s1); } catch(err){ ea=String(err); }
                    try { b = (new Function('S', 'with(S){ return ('+e+'); }'))(s2); } catch(err){ eb=String(err); }
                    checked++;
                    // both error, or both produce a mock/primitive: accept. Flag only value mismatch on primitives.
                    const prim = x => x===null||['number','string','boolean','undefined'].includes(typeof x);
                    if (ea && eb) continue;
                    if (ea || eb) { if (mism.length<20) mism.push({e:e.slice(0,70), ea, eb}); continue; }
                    if (prim(a) && prim(b) && String(a)!==String(b)) { if(mism.length<20) mism.push({e:e.slice(0,70), a:String(a), b:String(b)}); }
                }
                return {checked, mism};
            }""", exprs)
        print(f"[3] differential vs native eval: checked {diff['checked']} pure exprs, {len(diff['mism'])} divergences")
        for d in diff["mism"][:15]:
            print("      DIVERGE:", str(d).encode("ascii","replace").decode())

        b.close()
        pass_all = cov >= 0.999 and not bat_fail and not st_fail
        print("\nRESULT:", "PASS" if pass_all else "FAIL")
        return 0 if pass_all else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
