#!/usr/bin/env python
"""ARCH-070 feasibility proof: a bounded grammar covers the Alpine expression
corpus, so a CSP-safe evaluator can replace new Function() with no template
rewrites. See docs/adr/0007-csp-unsafe-eval-removal.md.

Extracts every Alpine directive expression from app/templates + app/modules and
parses each with a reference Pratt parser mirroring the intended evaluator
grammar. Reports coverage; exits non-zero if it drops below the threshold.

    python scripts/check_alpine_csp_grammar.py           # report
    python scripts/check_alpine_csp_grammar.py --json     # machine-readable
    python scripts/check_alpine_csp_grammar.py --examples  # show residual
"""
import argparse, json, re, sys, collections, importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "csp_compat", REPO_ROOT / "scripts" / "check_alpine_csp_compat.py")
_m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)
ATTR_RE, JINJA_RE = _m.ATTR_RE, _m.JINJA_RE
TEMPLATE_DIRS = [REPO_ROOT / "app" / "templates", REPO_ROOT / "app" / "modules"]

COVERAGE_FLOOR = 0.995  # of parseable (non-css) expressions

import re

TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<num>0[xX][0-9a-fA-F]+|\d+\.\d+|\.\d+|\d+(?:e[+-]?\d+)?)
  | (?P<tstr>`(?:\\.|\$\{|[^`\\])*`)
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<name>[A-Za-z_$][\w$]*)
  | (?P<punc>\.\.\.|\?\.|\?\?=|\?\?|===|!==|==|!=|<=|>=|&&=|\|\|=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|%=|=>|[-+*/%<>=!?:;,.()\[\]{}&|^~])
""", re.VERBOSE)

REGEX_RE = re.compile(r"/(?:\\.|\[(?:\\.|[^\]\\])*\]|[^/\\\n])+/[gimsuy]*")

KEYWORDS = {"true", "false", "null", "undefined", "typeof", "new", "in",
            "instanceof", "void", "delete", "await", "function"}

# A '/' starts a regex (not division) when the previous significant token is
# one of these (or at expression start).
REGEX_PREV = {"(", ",", "[", "{", ":", ";", "?", "=>", "!", "&&", "||", "??",
              "=", "+=", "-=", "*=", "/=", "%=", "===", "!==", "==", "!=",
              "<", "<=", ">", ">=", "+", "-", "*", "%", "return", "typeof",
              "&", "|", "^"}

def tokenize(s):
    toks = []
    i = 0
    prev = None  # (type, val) of previous non-ws token
    while i < len(s):
        # regex literal? only where a value is expected
        if s[i] == "/" and (prev is None or prev[1] in REGEX_PREV):
            rm = REGEX_RE.match(s, i)
            if rm:
                tok = ("regex", rm.group()); toks.append(tok); prev = tok
                i = rm.end(); continue
        m = TOKEN_RE.match(s, i)
        if not m:
            raise SyntaxError(f"bad token at {i}: {s[i:i+20]!r}")
        i = m.end()
        if m.lastgroup == "ws":
            continue
        tok = (m.lastgroup, m.group())
        toks.append(tok); prev = tok
    toks.append(("eof", ""))
    return toks

# Binary operator precedence (higher binds tighter)
BINOP = {
    "??": 1, "||": 2, "&&": 3, "|": 4, "^": 5, "&": 6,
    "==": 7, "!=": 7, "===": 7, "!==": 7,
    "<": 8, "<=": 8, ">": 8, ">=": 8, "in": 8, "instanceof": 8,
    "+": 10, "-": 10, "*": 11, "/": 11, "%": 11,
}
ASSIGN = {"=", "+=", "-=", "*=", "/=", "%=", "??=", "&&=", "||="}
PREFIX = {"!", "-", "+", "~", "typeof", "void", "delete", "await", "++", "--"}

class P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
    def peek(self): return self.t[self.i]
    def next(self): tok = self.t[self.i]; self.i += 1; return tok
    def at(self, val): return self.t[self.i][1] == val
    def eat(self, val):
        if not self.at(val):
            raise SyntaxError(f"expected {val!r} got {self.t[self.i]!r}")
        return self.next()

    STMT_KW = {"if", "return", "let", "const", "var", "for", "while"}

    def parse_program(self):
        # Alpine evaluates directive values as expressions (so a leading `{` is
        # an OBJECT literal, e.g. x-data / :class), except @click-style handlers
        # which can be statement sequences. Parse expression-first; only a
        # leading statement keyword switches an item to statement mode.
        self.parse_top_item()
        while self.at(";"):
            self.next()
            if self.peek()[0] == "eof": break
            self.parse_top_item()
        if self.peek()[0] != "eof":
            raise SyntaxError(f"trailing {self.peek()!r}")

    def parse_top_item(self):
        if self.peek()[1] in self.STMT_KW:
            self.parse_statement()
        else:
            self.parse_seq()

    def parse_seq(self):
        self.parse_assign()
        while self.at(","):
            self.next()
            self.parse_assign()

    def parse_assign(self):
        # try arrow function: params => body
        start = self.i
        if self.try_arrow():
            return
        self.i = start
        self.parse_ternary()
        if self.peek()[1] in ASSIGN:
            self.next()
            self.parse_assign()

    def try_arrow(self):
        try:
            if self.peek()[0] == "name" and self.t[self.i+1][1] == "=>":
                self.next(); self.eat("=>"); self.parse_arrow_body(); return True
            if self.at("("):
                depth = 0; j = self.i
                while j < len(self.t):
                    v = self.t[j][1]
                    if v == "(": depth += 1
                    elif v == ")":
                        depth -= 1
                        if depth == 0: break
                    j += 1
                if j+1 < len(self.t) and self.t[j+1][1] == "=>":
                    self.eat("(")
                    if not self.at(")"):
                        self.parse_param()
                        while self.at(","):
                            self.next(); self.parse_param()
                    self.eat(")"); self.eat("=>"); self.parse_arrow_body(); return True
        except SyntaxError:
            return False
        return False

    def parse_param(self):
        if self.at("..."): self.next()
        if self.peek()[0] != "name":
            # destructuring {a,b} or [a,b]
            if self.at("{") or self.at("["): self.parse_primary();
            else: raise SyntaxError("bad param")
        else:
            self.next()
            if self.at("="):  # default
                self.next(); self.parse_assign()

    def parse_arrow_body(self):
        if self.at("{"):
            self.parse_block()
        else:
            self.parse_assign()

    def parse_block(self):
        self.eat("{")
        while not self.at("}"):
            self.parse_statement()
            if self.at(";"): self.next()
        self.eat("}")

    def parse_statement(self):
        v = self.peek()[1]
        if v == "return":
            self.next()
            if not self.at("}") and not self.at(";"):
                self.parse_seq()
        elif v == "if":
            self.next(); self.eat("("); self.parse_seq(); self.eat(")")
            self.parse_stmt_or_block()
            if self.at("else"):
                self.next(); self.parse_stmt_or_block()
        elif v in ("let", "const", "var"):
            self.next(); self.next()  # decl name
            if self.at("="):
                self.next(); self.parse_assign()
            while self.at(","):
                self.next(); self.next()
                if self.at("="): self.next(); self.parse_assign()
        elif v == "{":
            self.parse_block()
        else:
            self.parse_seq()

    def parse_stmt_or_block(self):
        if self.at("{"): self.parse_block()
        else:
            self.parse_statement()
            if self.at(";"): self.next()

    def parse_ternary(self):
        self.parse_binary(0)
        if self.at("?"):
            self.next(); self.parse_assign(); self.eat(":"); self.parse_assign()

    def parse_binary(self, minp):
        self.parse_unary()
        while True:
            op = self.peek()[1]
            p = BINOP.get(op)
            if p is None or p < minp: break
            self.next()
            self.parse_binary(p+1)

    def parse_unary(self):
        if self.peek()[1] in PREFIX:
            self.next(); self.parse_unary(); return
        self.parse_postfix()

    def parse_postfix(self):
        self.parse_call_member()
        if self.peek()[1] in ("++", "--"):
            self.next()

    def parse_call_member(self):
        self.parse_primary()
        while True:
            v = self.peek()[1]
            if v == "?.":
                self.next()
                if self.at("["):
                    self.next(); self.parse_seq(); self.eat("]")
                elif self.at("("):
                    self.parse_args()
                else:
                    if self.peek()[0] != "name" and self.peek()[1] not in KEYWORDS:
                        raise SyntaxError(f"expected prop got {self.peek()!r}")
                    self.next()
            elif v == ".":
                self.next()
                if self.peek()[0] != "name" and self.peek()[1] not in KEYWORDS:
                    raise SyntaxError(f"expected prop got {self.peek()!r}")
                self.next()
            elif v == "[":
                self.next(); self.parse_seq(); self.eat("]")
            elif v == "(":
                self.parse_args()
            else:
                break

    def parse_args(self):
        self.eat("(")
        if not self.at(")"):
            if self.at("..."): self.next()
            self.parse_assign()
            while self.at(","):
                self.next()
                if self.at(")"): break
                if self.at("..."): self.next()
                self.parse_assign()
        self.eat(")")

    def parse_primary(self):
        typ, val = self.peek()
        if typ in ("num", "str", "tstr", "regex"):
            self.next(); return
        if val == "new":
            self.next(); self.parse_call_member(); return
        if val == "function":
            self.next()
            if self.peek()[0] == "name": self.next()  # optional name
            self.eat("(")
            if not self.at(")"):
                self.parse_param()
                while self.at(","):
                    self.next(); self.parse_param()
            self.eat(")")
            self.parse_block()
            return
        if typ == "name":
            self.next(); return
        if val == "(":
            self.next(); self.parse_seq(); self.eat(")"); return
        if val == "[":
            self.next()
            if not self.at("]"):
                if self.at("..."): self.next()
                self.parse_assign()
                while self.at(","):
                    self.next()
                    if self.at("]"): break
                    if self.at("..."): self.next()
                    self.parse_assign()
            self.eat("]"); return
        if val == "{":
            self.parse_object(); return
        if val in PREFIX:
            self.next(); self.parse_unary(); return
        raise SyntaxError(f"unexpected {self.peek()!r}")

    def parse_object(self):
        self.eat("{")
        while not self.at("}"):
            if self.at("..."):
                self.next(); self.parse_assign()
            else:
                # key
                if self.at("["):
                    self.next(); self.parse_assign(); self.eat("]")
                elif self.peek()[0] in ("name", "str", "num"):
                    key = self.next()
                else:
                    raise SyntaxError(f"bad key {self.peek()!r}")
                if self.at("("):  # method shorthand
                    self.next()
                    if not self.at(")"):
                        self.parse_param()
                        while self.at(","):
                            self.next(); self.parse_param()
                    self.eat(")")
                    self.parse_arrow_body()  # method body = block
                elif self.at(":"):
                    self.next(); self.parse_assign()
                # else shorthand {a}
            if self.at(","):
                self.next()
            else:
                break
        self.eat("}")

def parse(expr):
    p = P(tokenize(expr))
    p.parse_program()

CSS_CLASS_RE = re.compile(r"^[a-z0-9:_\-\s!/.\[\]#%]+$")

def is_css_classlist(e):
    # x-transition:enter/@… class strings: space-separated tokens, no JS
    # operators/keywords, at least one space, looks like tailwind classes.
    if not CSS_CLASS_RE.match(e): return False
    if "(" in e or "=" in e: return False
    toks = e.split()
    if len(toks) < 2: return False
    return all(re.match(r"^[a-z0-9:_\-/.\[\]#%!]+$", t) and "-" in t or t in
               ("transition","transform","ease","ease-in","ease-out","opacity") for t in toks)



def extract_corpus():
    seen = {}
    for d in TEMPLATE_DIRS:
        for f in d.rglob("*.html"):
            try: txt = f.read_text(encoding="utf-8")
            except Exception: continue
            for mt in ATTR_RE.finditer(txt):
                e = mt.group("expr")
                if not e.strip() or JINJA_RE.search(e): continue
                seen.setdefault(e, mt.group("name"))
    return list(seen.keys())


def run():
    exprs = extract_corpus()
    ok = css = 0; fails = []
    for e in exprs:
        try:
            parse(e); ok += 1
        except Exception as ex:
            if is_css_classlist(e): css += 1
            else: fails.append((e, str(ex)))
    total = len(exprs)
    parseable = total - css
    cov = ok / parseable if parseable else 1.0
    return {"total": total, "parsed": ok, "css_classlists": css,
            "residual": len(fails), "coverage": cov, "fails": fails}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--examples", action="store_true")
    a = ap.parse_args()
    r = run()
    if a.json:
        print(json.dumps({k: v for k, v in r.items() if k != "fails"}))
        return 0 if r["coverage"] >= COVERAGE_FLOOR else 1
    print(f"Alpine expressions (unique):     {r['total']}")
    print(f"  parsed by bounded grammar:     {r['parsed']} ({r['coverage']*100:.2f}% of parseable)")
    print(f"  css class-strings (not JS):    {r['css_classlists']}")
    print(f"  true residual:                 {r['residual']}")
    if a.examples:
        for e, why in r["fails"][:40]:
            print(f"    RESIDUAL: {e[:88]!r} -- {why[:45]}")
    if r["coverage"] < COVERAGE_FLOOR:
        print(f"FAIL: coverage {r['coverage']*100:.2f}% < floor {COVERAGE_FLOOR*100:.1f}%")
        return 1
    print(f"OK: coverage >= {COVERAGE_FLOOR*100:.1f}% floor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
