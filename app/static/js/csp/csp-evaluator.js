/* CSP-safe JS-expression evaluator (ARCH-070).
 *
 * Tokenizer + Pratt parser + tree-walking interpreter for the JS-expression
 * subset Alpine templates use. No eval / new Function anywhere, so it works
 * under a CSP without 'unsafe-eval'. Grammar mirrors the proven reference in
 * scripts/check_alpine_csp_grammar.py (99.9% corpus coverage).
 *
 * Public API:
 *   CSPExpr.compile(src) -> ast           (throws on parse error)
 *   CSPExpr.run(ast|src, scope) -> value  (evaluates against a scope object)
 */
(function (global) {
  'use strict';

  // ── Tokenizer ──────────────────────────────────────────────────────────
  var PUNCT = [
    '...', '?.', '??=', '===', '!==', '==', '!=', '<=', '>=',
    '&&=', '||=', '&&', '||', '??', '++', '--', '+=', '-=', '*=', '/=', '%=',
    '=>', '(', ')', '[', ']', '{', '}', '.', ',', ';', ':', '?',
    '+', '-', '*', '/', '%', '<', '>', '=', '!', '&', '|', '^', '~'
  ];
  var KEYWORD = { 'true': 1, 'false': 1, 'null': 1, 'undefined': 1, 'new': 1,
    'typeof': 1, 'void': 1, 'delete': 1, 'in': 1, 'instanceof': 1, 'function': 1,
    'return': 1, 'if': 1, 'else': 1, 'let': 1, 'const': 1, 'var': 1, 'await': 1,
    'try': 1, 'catch': 1, 'finally': 1,
    'for': 1, 'while': 1, 'of': 1, 'break': 1, 'continue': 1 };
  var REGEX_PREV = { '(': 1, ',': 1, '[': 1, '{': 1, ':': 1, ';': 1, '?': 1,
    '=>': 1, '!': 1, '&&': 1, '||': 1, '??': 1, '=': 1, '===': 1, '!==': 1,
    '==': 1, '!=': 1, '<': 1, '<=': 1, '>': 1, '>=': 1, '+': 1, '-': 1, '*': 1,
    '/': 1, '%': 1, '&': 1, '|': 1, '^': 1, 'return': 1, 'typeof': 1 };

  function isIdStart(c) { return /[A-Za-z_$]/.test(c); }
  function isIdPart(c) { return /[\w$]/.test(c); }
  function isDigit(c) { return c >= '0' && c <= '9'; }

  function tokenize(s) {
    var toks = [], i = 0, n = s.length, prev = null;
    function push(type, val) { var t = { type: type, val: val }; toks.push(t); prev = t; }
    while (i < n) {
      var c = s[i];
      if (/\s/.test(c)) { i++; continue; }
      // comments (a method body inside x-data may carry them)
      if (c === '/' && s[i + 1] === '/') { i += 2; while (i < n && s[i] !== '\n') i++; continue; }
      if (c === '/' && s[i + 1] === '*') { i += 2; while (i < n && !(s[i] === '*' && s[i + 1] === '/')) i++; i += 2; continue; }
      // HTML comments embedded in an attribute value (e.g. a `:class` object with
      // an inline `<!-- token-migration-ok -->`). Browsers treat `<!--` and a
      // line-leading `-->` as single-line comments in JS (ECMAScript Annex B web
      // compat), so stock Alpine's new Function() ignored them; match that.
      if (c === '<' && s[i + 1] === '!' && s[i + 2] === '-' && s[i + 3] === '-') { i += 4; while (i < n && s[i] !== '\n') i++; continue; }
      // regex literal (only where a value is expected)
      if (c === '/' && (prev === null || REGEX_PREV[prev.val])) {
        var j = i + 1, inClass = false, ok = false;
        while (j < n) {
          var d = s[j];
          if (d === '\\') { j += 2; continue; }
          if (d === '[') inClass = true;
          else if (d === ']') inClass = false;
          else if (d === '/' && !inClass) { ok = true; break; }
          else if (d === '\n') break;
          j++;
        }
        if (ok) {
          var end = j + 1;
          while (end < n && /[gimsuy]/.test(s[end])) end++;
          push('regex', s.slice(i, end)); i = end; continue;
        }
      }
      // number
      if (isDigit(c) || (c === '.' && isDigit(s[i + 1]))) {
        var m = /^(?:0[xX][0-9a-fA-F]+|\d+\.\d+|\.\d+|\d+(?:[eE][+-]?\d+)?|\d+)/.exec(s.slice(i));
        push('num', m[0]); i += m[0].length; continue;
      }
      // string
      if (c === '"' || c === "'") {
        var q = c, k = i + 1, buf = '';
        while (k < n && s[k] !== q) {
          if (s[k] === '\\') { var esc = readEscape(s, k + 1); buf += esc.ch; k = esc.next; }
          else { buf += s[k]; k++; }
        }
        push('str', buf); i = k + 1; continue;
      }
      // template literal
      if (c === '`') { var res = readTemplate(s, i); toks.push(res.tok); prev = res.tok; i = res.end; continue; }
      // identifier / keyword
      if (isIdStart(c)) {
        var st = i; i++; while (i < n && isIdPart(s[i])) i++;
        var word = s.slice(st, i);
        push(KEYWORD[word] ? 'kw' : 'name', word); continue;
      }
      // punctuation (longest match)
      var matched = null;
      for (var p = 0; p < PUNCT.length; p++) {
        if (s.startsWith(PUNCT[p], i)) { matched = PUNCT[p]; break; }
      }
      if (!matched) throw new SyntaxError('bad char ' + JSON.stringify(c) + ' at ' + i);
      push('punc', matched); i += matched.length;
    }
    // Pad with several eof sentinels so lookahead (this.t[this.i+1/+2/+3]) never
    // returns undefined on truncated/malformed input — the parser then throws a
    // clean SyntaxError instead of crashing with a TypeError.
    toks.push({ type: 'eof', val: '' });
    toks.push({ type: 'eof', val: '' });
    toks.push({ type: 'eof', val: '' });
    toks.push({ type: 'eof', val: '' });
    return toks;
  }

  // reads the escape sequence starting AT position p (right after the backslash);
  // returns {ch, next} where next is the index just past the sequence.
  function readEscape(s, p) {
    var c = s[p];
    switch (c) {
      case 'n': return { ch: '\n', next: p + 1 };
      case 't': return { ch: '\t', next: p + 1 };
      case 'r': return { ch: '\r', next: p + 1 };
      case 'b': return { ch: '\b', next: p + 1 };
      case 'f': return { ch: '\f', next: p + 1 };
      case 'v': return { ch: '\v', next: p + 1 };
      case '0': return { ch: '\0', next: p + 1 };
      case 'x': return { ch: String.fromCharCode(parseInt(s.substr(p + 1, 2), 16)), next: p + 3 };
      case 'u':
        if (s[p + 1] === '{') { var e = s.indexOf('}', p + 2); return { ch: String.fromCodePoint(parseInt(s.slice(p + 2, e), 16)), next: e + 1 }; }
        return { ch: String.fromCharCode(parseInt(s.substr(p + 1, 4), 16)), next: p + 5 };
      default: return { ch: c, next: p + 1 };
    }
  }

  function readTemplate(s, i) {
    // returns {tok:{type:'tstr', quasis:[str], exprs:[src]}, end}
    var k = i + 1, quasis = [], exprs = [], cur = '';
    while (k < s.length && s[k] !== '`') {
      if (s[k] === '\\') { var esc = readEscape(s, k + 1); cur += esc.ch; k = esc.next; continue; }
      if (s[k] === '$' && s[k + 1] === '{') {
        quasis.push(cur); cur = '';
        var depth = 1, st = k + 2, j = k + 2;
        while (j < s.length && depth > 0) {
          if (s[j] === '{') depth++;
          else if (s[j] === '}') depth--;
          if (depth === 0) break;
          j++;
        }
        exprs.push(s.slice(st, j)); k = j + 1; continue;
      }
      cur += s[k]; k++;
    }
    quasis.push(cur);
    return { tok: { type: 'tstr', quasis: quasis, exprs: exprs }, end: k + 1 };
  }

  // ── Parser (Pratt) ─────────────────────────────────────────────────────
  var BINOP = { '??': 1, '||': 2, '&&': 3, '|': 4, '^': 5, '&': 6,
    '==': 7, '!=': 7, '===': 7, '!==': 7,
    '<': 8, '<=': 8, '>': 8, '>=': 8, 'in': 8, 'instanceof': 8,
    '+': 10, '-': 10, '*': 11, '/': 11, '%': 11 };
  var ASSIGN = { '=': 1, '+=': 1, '-=': 1, '*=': 1, '/=': 1, '%=': 1, '??=': 1, '&&=': 1, '||=': 1 };
  var PREFIX = { '!': 1, '-': 1, '+': 1, '~': 1, 'typeof': 1, 'void': 1, 'delete': 1, 'await': 1 };
  var STMT_KW = { 'if': 1, 'return': 1, 'let': 1, 'const': 1, 'var': 1, 'try': 1,
    'for': 1, 'while': 1, 'break': 1, 'continue': 1 };

  function Parser(toks) { this.t = toks; this.i = 0; }
  Parser.prototype = {
    peek: function () { return this.t[this.i]; },
    val: function () { return this.t[this.i].val; },
    next: function () { return this.t[this.i++]; },
    at: function (v) { return this.t[this.i].val === v && this.t[this.i].type !== 'str' && this.t[this.i].type !== 'name'; },
    isPunc: function (v) { var t = this.t[this.i]; return (t.type === 'punc' || t.type === 'kw') && t.val === v; },
    eat: function (v) { if (!this.isPunc(v)) throw new SyntaxError('expected ' + v + ' got ' + JSON.stringify(this.peek().val)); return this.next(); },

    program: function () {
      // Strict statement list: items are ';'-separated (empty statements ok). A
      // separator is REQUIRED between items, so two juxtaposed expressions with
      // no ';' (e.g. a Tailwind x-transition class-string "opacity-0 scale-95")
      // are correctly rejected as non-JS rather than mis-parsed. The earlier
      // `if(c) f(); g()` bug was stmtOrBlock eating the ';', not a missing-
      // separator rule — fixed there, so this stays strict.
      var body = [this.topItem()];
      while (this.isPunc(';')) {
        while (this.isPunc(';')) this.next();
        if (this.peek().type === 'eof') break;
        body.push(this.topItem());
      }
      if (this.peek().type !== 'eof') throw new SyntaxError('trailing ' + JSON.stringify(this.peek().val));
      return { t: 'program', body: body };
    },
    topItem: function () {
      if (this.peek().type === 'kw' && STMT_KW[this.val()]) return this.statement();
      return this.seq();
    },
    seq: function () {
      var first = this.assign();
      if (!this.isPunc(',')) return first;
      var items = [first];
      while (this.isPunc(',')) { this.next(); items.push(this.assign()); }
      return { t: 'seq', items: items };
    },
    assign: function () {
      var start = this.i;
      var arrow = this.tryArrow();
      if (arrow) return arrow;
      this.i = start;
      var left = this.ternary();
      if (this.peek().type === 'punc' && ASSIGN[this.val()]) {
        var op = this.next().val;
        var right = this.assign();
        return { t: 'assign', op: op, target: left, value: right };
      }
      return left;
    },
    tryArrow: function () {
      try {
        if (this.peek().type === 'name' && this.t[this.i + 1].val === '=>') {
          var p = { t: 'id', name: this.next().val }; this.eat('=>');
          return { t: 'arrow', params: [p], body: this.arrowBody() };
        }
        if (this.isPunc('(')) {
          var depth = 0, j = this.i;
          while (j < this.t.length) {
            var v = this.t[j].val;
            if (this.t[j].type === 'punc') { if (v === '(') depth++; else if (v === ')') { depth--; if (depth === 0) break; } }
            j++;
          }
          if (j + 1 < this.t.length && this.t[j + 1].val === '=>') {
            this.eat('('); var params = [];
            if (!this.isPunc(')')) { params.push(this.param()); while (this.isPunc(',')) { this.next(); params.push(this.param()); } }
            this.eat(')'); this.eat('=>');
            return { t: 'arrow', params: params, body: this.arrowBody() };
          }
        }
      } catch (e) { return null; }
      return null;
    },
    param: function () {
      var rest = false;
      if (this.isPunc('...')) { this.next(); rest = true; }
      if (this.peek().type !== 'name') {
        if (this.isPunc('{') || this.isPunc('[')) { var pat = this.primary(); return { t: 'param', pattern: pat, rest: rest }; }
        throw new SyntaxError('bad param');
      }
      var name = this.next().val, def = null;
      if (this.isPunc('=')) { this.next(); def = this.assign(); }
      return { t: 'param', name: name, def: def, rest: rest };
    },
    arrowBody: function () {
      if (this.isPunc('{')) return { t: 'block', body: this.block() };
      return this.assign();
    },
    block: function () {
      this.eat('{'); var body = [];
      while (!this.isPunc('}')) { body.push(this.statement()); while (this.isPunc(';')) this.next(); }
      this.eat('}'); return body;
    },
    statement: function () {
      var v = this.val(), t = this.peek().type;
      if (t === 'kw' && v === 'return') { this.next(); if (this.isPunc('}') || this.isPunc(';') || this.peek().type === 'eof') return { t: 'return', arg: null }; return { t: 'return', arg: this.seq() }; }
      if (t === 'kw' && v === 'if') {
        this.next(); this.eat('('); var test = this.seq(); this.eat(')');
        var cons = this.stmtOrBlock(), alt = null;
        // Allow `if (c) foo(); else bar()` — the ';' terminates the consequent
        // expression-statement and `else` follows it.
        while (this.isPunc(';') && this.t[this.i + 1] && this.t[this.i + 1].val === 'else') this.next();
        if (this.isPunc('else')) { this.next(); alt = this.stmtOrBlock(); }
        return { t: 'if', test: test, cons: cons, alt: alt };
      }
      if (t === 'kw' && v === 'break') { this.next(); return { t: 'break' }; }
      if (t === 'kw' && v === 'continue') { this.next(); return { t: 'continue' }; }
      if (t === 'kw' && v === 'while') {
        this.next(); this.eat('('); var wtest = this.seq(); this.eat(')');
        return { t: 'while', test: wtest, body: this.stmtOrBlock() };
      }
      if (t === 'kw' && v === 'for') {
        this.next(); this.eat('(');
        // init clause: `let/const/var x = ...` | expr | empty
        var decl = null;
        if (this.isPunc('let') || this.isPunc('const') || this.isPunc('var') ||
            (this.peek().type === 'kw' && (this.val() === 'let' || this.val() === 'const' || this.val() === 'var'))) {
          this.next();  // let/const/var
          decl = { name: this.next().val, init: null };
        }
        // for-of / for-in
        if (this.isPunc('of') || (this.peek().type === 'kw' && this.val() === 'of')) {
          this.next(); var oiter = this.assign(); this.eat(')');
          return { t: 'forof', name: decl ? decl.name : null, iter: oiter, body: this.stmtOrBlock() };
        }
        if (this.isPunc('in') || (this.peek().type === 'kw' && this.val() === 'in')) {
          this.next(); var iiter = this.assign(); this.eat(')');
          return { t: 'forin', name: decl ? decl.name : null, iter: iiter, body: this.stmtOrBlock() };
        }
        // C-style: init; test; update
        if (decl && this.isPunc('=')) { this.next(); decl.init = this.assign(); }
        var init = decl ? { t: 'var', decls: [decl] } : (this.isPunc(';') ? null : { t: 'exprstmt', expr: this.seq() });
        this.eat(';');
        var ftest = this.isPunc(';') ? null : this.seq();
        this.eat(';');
        var upd = this.isPunc(')') ? null : this.seq();
        this.eat(')');
        return { t: 'for', init: init, test: ftest, update: upd, body: this.stmtOrBlock() };
      }
      if (t === 'kw' && (v === 'let' || v === 'const' || v === 'var')) {
        this.next(); var decls = [];
        do { var nm = this.next().val, init = null; if (this.isPunc('=')) { this.next(); init = this.assign(); } decls.push({ name: nm, init: init }); } while (this.isPunc(',') && this.next());
        return { t: 'var', decls: decls };
      }
      if (t === 'kw' && v === 'try') {
        this.next(); var block = this.block(), handler = null, finalizer = null;
        if (this.isPunc('catch')) { this.next(); var param = null; if (this.isPunc('(')) { this.next(); param = this.next().val; this.eat(')'); } handler = { param: param, body: this.block() }; }
        if (this.isPunc('finally')) { this.next(); finalizer = this.block(); }
        return { t: 'try', block: block, handler: handler, finalizer: finalizer };
      }
      if (this.isPunc('{')) return { t: 'block', body: this.block() };
      return { t: 'exprstmt', expr: this.seq() };
    },
    stmtOrBlock: function () {
      // Do NOT consume a trailing ';' here — the enclosing statement list
      // (program / block) owns terminators, so an if-consequent leaves the ';'
      // for the outer loop and the following statement is not swallowed.
      if (this.isPunc('{')) return { t: 'block', body: this.block() };
      return this.statement();
    },
    ternary: function () {
      var test = this.binary(0);
      if (this.isPunc('?')) { this.next(); var cons = this.assign(); this.eat(':'); var alt = this.assign(); return { t: 'ternary', test: test, cons: cons, alt: alt }; }
      return test;
    },
    binary: function (minp) {
      var left = this.unary();
      while (true) {
        var op = this.val();
        var isOp = (this.peek().type === 'punc') || (this.peek().type === 'kw' && (op === 'in' || op === 'instanceof'));
        var p = isOp ? BINOP[op] : undefined;
        if (p === undefined || p < minp) break;
        this.next();
        var right = this.binary(p + 1);
        var kind = (op === '&&' || op === '||' || op === '??') ? 'logical' : 'binary';
        left = { t: kind, op: op, left: left, right: right };
      }
      return left;
    },
    unary: function () {
      var v = this.val();
      if (this.peek().type !== 'str' && this.peek().type !== 'name' && (PREFIX[v] || ((this.peek().type === 'kw') && PREFIX[v]))) {
        if (this.peek().type === 'punc' || this.peek().type === 'kw') { this.next(); return { t: 'unary', op: v, arg: this.unary() }; }
      }
      if (this.isPunc('++') || this.isPunc('--')) { var op = this.next().val; return { t: 'update', op: op, prefix: true, arg: this.unary() }; }
      return this.postfix();
    },
    postfix: function () {
      var e = this.callMember();
      if (this.isPunc('++') || this.isPunc('--')) { var op = this.next().val; return { t: 'update', op: op, prefix: false, arg: e }; }
      return e;
    },
    callMember: function () {
      var e = this.primary();
      while (true) {
        if (this.isPunc('?.')) {
          this.next();
          if (this.isPunc('[')) { this.next(); var pr = this.seq(); this.eat(']'); e = { t: 'member', obj: e, prop: pr, computed: true, optional: true }; }
          else if (this.isPunc('(')) { e = { t: 'call', callee: e, args: this.args(), optional: true }; }
          else { var nm = this.next().val; e = { t: 'member', obj: e, prop: { t: 'lit', v: nm }, computed: false, optional: true }; }
        } else if (this.isPunc('.')) {
          this.next(); var nm2 = this.next().val; e = { t: 'member', obj: e, prop: { t: 'lit', v: nm2 }, computed: false, optional: false };
        } else if (this.isPunc('[')) {
          this.next(); var pr2 = this.seq(); this.eat(']'); e = { t: 'member', obj: e, prop: pr2, computed: true, optional: false };
        } else if (this.isPunc('(')) {
          e = { t: 'call', callee: e, args: this.args(), optional: false };
        } else break;
      }
      return e;
    },
    args: function () {
      this.eat('('); var args = [];
      if (!this.isPunc(')')) {
        args.push(this.argItem());
        while (this.isPunc(',')) { this.next(); if (this.isPunc(')')) break; args.push(this.argItem()); }
      }
      this.eat(')'); return args;
    },
    argItem: function () { if (this.isPunc('...')) { this.next(); return { t: 'spread', arg: this.assign() }; } return this.assign(); },
    primary: function () {
      var tok = this.peek();
      if (tok.type === 'num') { this.next(); return { t: 'lit', v: parseNum(tok.val) }; }
      if (tok.type === 'str') { this.next(); return { t: 'lit', v: tok.val }; }
      if (tok.type === 'regex') { this.next(); return { t: 'regex', src: tok.val }; }
      if (tok.type === 'tstr') { this.next(); return { t: 'tstr', quasis: tok.quasis, exprs: tok.exprs.map(function (s) { return compile(s); }) }; }
      if (tok.type === 'kw') {
        var v = tok.val;
        if (v === 'true') { this.next(); return { t: 'lit', v: true }; }
        if (v === 'false') { this.next(); return { t: 'lit', v: false }; }
        if (v === 'null') { this.next(); return { t: 'lit', v: null }; }
        if (v === 'undefined') { this.next(); return { t: 'lit', v: undefined }; }
        if (v === 'new') { this.next(); var callee = this.callMemberNoCall(); var a = this.isPunc('(') ? this.args() : []; return { t: 'new', callee: callee, args: a }; }
        if (v === 'function') { this.next(); if (this.peek().type === 'name') this.next(); this.eat('('); var params = []; if (!this.isPunc(')')) { params.push(this.param()); while (this.isPunc(',')) { this.next(); params.push(this.param()); } } this.eat(')'); return { t: 'func', params: params, body: this.block() }; }
        if (PREFIX[v]) { this.next(); return { t: 'unary', op: v, arg: this.unary() }; }
      }
      if (tok.type === 'name') { this.next(); return { t: 'id', name: tok.val }; }
      if (this.isPunc('(')) { this.next(); var seq = this.seq(); this.eat(')'); return seq; }
      if (this.isPunc('[')) { return this.array(); }
      if (this.isPunc('{')) { return this.object(); }
      throw new SyntaxError('unexpected ' + JSON.stringify(tok.val));
    },
    callMemberNoCall: function () {
      var e = this.primary();
      while (true) {
        if (this.isPunc('.')) { this.next(); e = { t: 'member', obj: e, prop: { t: 'lit', v: this.next().val }, computed: false }; }
        else if (this.isPunc('[')) { this.next(); var pr = this.seq(); this.eat(']'); e = { t: 'member', obj: e, prop: pr, computed: true }; }
        else break;
      }
      return e;
    },
    array: function () {
      this.eat('['); var els = [];
      while (!this.isPunc(']')) {
        if (this.isPunc(',')) { this.next(); els.push({ t: 'hole' }); continue; }
        if (this.isPunc('...')) { this.next(); els.push({ t: 'spread', arg: this.assign() }); }
        else els.push(this.assign());
        if (this.isPunc(',')) this.next(); else break;
      }
      this.eat(']'); return { t: 'array', elements: els };
    },
    object: function () {
      this.eat('{'); var props = [];
      while (!this.isPunc('}')) {
        if (this.isPunc('...')) { this.next(); props.push({ kind: 'spread', value: this.assign() }); }
        else {
          var computed = false, key;
          // `async name() { ... }` method shorthand (Alpine x-data commonly has
          // `async init()`, `async load()`). Skip the `async` modifier — the
          // evaluator runs bodies synchronously (await is a pass-through), which
          // is fine for driving reactive state. Without this the whole x-data
          // object failed to parse and the component died.
          if (this.val() === 'async' && this.peek().type === 'name' &&
              (this.t[this.i + 1].type === 'name' || this.t[this.i + 1].type === 'str' ||
               (this.t[this.i + 1].type === 'punc' && (this.t[this.i + 1].val === '[' || this.t[this.i + 1].val === '*')))) {
            this.next();  // consume 'async'
            if (this.isPunc('*')) this.next();  // async generator — ignore the star
          }
          // get/set accessor: `get name() { ... }` / `set name(v) { ... }`.
          // Only treat as an accessor when followed by a property name (not
          // `get:` shorthand or `get()` method literally named "get").
          if ((this.val() === 'get' || this.val() === 'set') &&
              (this.t[this.i + 1].type === 'name' || this.t[this.i + 1].type === 'str' ||
               (this.t[this.i + 1].type === 'punc' && this.t[this.i + 1].val === '['))) {
            var acc = this.next().val;  // 'get' | 'set'
            var akComputed = false, akey;
            if (this.isPunc('[')) { this.next(); akey = this.assign(); this.eat(']'); akComputed = true; }
            else { var akt = this.next(); akey = { t: 'lit', v: akt.val }; }
            var aparams = []; this.eat('(');
            if (!this.isPunc(')')) { aparams.push(this.param()); while (this.isPunc(',')) { this.next(); aparams.push(this.param()); } }
            this.eat(')'); var abody = this.block();
            props.push({ kind: acc, key: akey, computed: akComputed, value: { t: 'func', params: aparams, body: abody } });
            if (this.isPunc(',')) this.next();
            continue;
          }
          if (this.isPunc('[')) { this.next(); key = this.assign(); this.eat(']'); computed = true; }
          else { var kt = this.peek(); this.next(); key = { t: 'lit', v: kt.type === 'num' ? kt.val : kt.val }; }
          if (this.isPunc('(')) { // method shorthand
            var params = []; this.eat('(');
            if (!this.isPunc(')')) { params.push(this.param()); while (this.isPunc(',')) { this.next(); params.push(this.param()); } }
            this.eat(')'); var body = this.block();
            props.push({ kind: 'init', key: key, computed: computed, value: { t: 'func', params: params, body: body } });
          } else if (this.isPunc(':')) { this.next(); props.push({ kind: 'init', key: key, computed: computed, value: this.assign() }); }
          else { props.push({ kind: 'shorthand', key: key, value: { t: 'id', name: key.v } }); }
        }
        if (this.isPunc(',')) this.next(); else break;
      }
      this.eat('}'); return { t: 'object', props: props };
    }
  };

  function parseNum(s) { return s.indexOf('.') >= 0 || /[eE]/.test(s) ? parseFloat(s) : (s.slice(0, 2).toLowerCase() === '0x' ? parseInt(s, 16) : parseInt(s, 10)); }

  function compile(src) { var p = new Parser(tokenize(src)); return p.program(); }

  // ── Evaluator ──────────────────────────────────────────────────────────
  // scope: object (Alpine merged proxy). We read/write through it.
  function ev(node, scope, ctx) {
    switch (node.t) {
      case 'program': { var r; for (var i = 0; i < node.body.length; i++) r = ev(node.body[i], scope, ctx); return r; }
      case 'exprstmt': return ev(node.expr, scope, ctx);
      case 'seq': { var v; for (var s = 0; s < node.items.length; s++) v = ev(node.items[s], scope, ctx); return v; }
      case 'lit': return node.v;
      case 'regex': { var m = /^\/(.*)\/([gimsuy]*)$/.exec(node.src); return new RegExp(m[1], m[2]); }
      case 'tstr': { var out = node.quasis[0]; for (var q = 0; q < node.exprs.length; q++) out += String(ev(node.exprs[q], scope, ctx)) + node.quasis[q + 1]; return out; }
      case 'id': return readId(node.name, scope, ctx);
      case 'array': { var arr = []; node.elements.forEach(function (el) { if (el.t === 'hole') arr.push(undefined); else if (el.t === 'spread') { var sp = ev(el.arg, scope, ctx); for (var x of sp) arr.push(x); } else arr.push(ev(el, scope, ctx)); }); return arr; }
      case 'object': { var o = {}; node.props.forEach(function (pr) {
        if (pr.kind === 'spread') { Object.assign(o, ev(pr.value, scope, ctx)); return; }
        var k = pr.computed ? ev(pr.key, scope, ctx) : pr.key.v;
        if (pr.kind === 'get') { Object.defineProperty(o, k, { get: makeFn(pr.value, scope, ctx), enumerable: true, configurable: true }); return; }
        if (pr.kind === 'set') { Object.defineProperty(o, k, { set: makeFn(pr.value, scope, ctx), enumerable: true, configurable: true }); return; }
        o[k] = ev(pr.value, scope, ctx);
      }); return o; }
      case 'member': { var obj = ev(node.obj, scope, ctx); if ((node.optional) && (obj === null || obj === undefined)) return undefined; var key = node.computed ? ev(node.prop, scope, ctx) : node.prop.v; return obj == null ? undefined : obj[key]; }
      case 'unary': {
        if (node.op === 'typeof') { if (node.arg.t === 'id') { try { return typeof readId(node.arg.name, scope, ctx); } catch (e) { return 'undefined'; } } return typeof ev(node.arg, scope, ctx); }
        if (node.op === 'delete') { if (node.arg.t === 'member') { var mo = ev(node.arg.obj, scope, ctx); var mk = node.arg.computed ? ev(node.arg.prop, scope, ctx) : node.arg.prop.v; return delete mo[mk]; } return true; }
        var a = ev(node.arg, scope, ctx);
        switch (node.op) { case '!': return !a; case '-': return -a; case '+': return +a; case '~': return ~a; case 'void': return undefined; case 'await': return a; }
        break;
      }
      case 'update': { var ref = lref(node.arg, scope, ctx); var old = Number(ref.get()); var nv = node.op === '++' ? old + 1 : old - 1; ref.set(nv); return node.prefix ? nv : old; }
      case 'binary': { var l = ev(node.left, scope, ctx), r = ev(node.right, scope, ctx); return binop(node.op, l, r); }
      case 'logical': { var lv = ev(node.left, scope, ctx); if (node.op === '&&') return lv ? ev(node.right, scope, ctx) : lv; if (node.op === '||') return lv ? lv : ev(node.right, scope, ctx); return (lv === null || lv === undefined) ? ev(node.right, scope, ctx) : lv; }
      case 'ternary': return ev(node.test, scope, ctx) ? ev(node.cons, scope, ctx) : ev(node.alt, scope, ctx);
      case 'assign': { var ref2 = lref(node.target, scope, ctx); var val; if (node.op === '=') val = ev(node.value, scope, ctx); else { var cur = ref2.get(); if (node.op === '&&=') { if (!cur) return cur; val = ev(node.value, scope, ctx); } else if (node.op === '||=') { if (cur) return cur; val = ev(node.value, scope, ctx); } else if (node.op === '??=') { if (cur !== null && cur !== undefined) return cur; val = ev(node.value, scope, ctx); } else { val = binop(node.op.slice(0, -1), cur, ev(node.value, scope, ctx)); } } ref2.set(val); return val; }
      case 'call': return doCall(node, scope, ctx);
      case 'new': { var C = ev(node.callee, scope, ctx); var args = evalArgs(node.args, scope, ctx); return new (Function.prototype.bind.apply(C, [null].concat(args)))(); }
      case 'arrow': case 'func': return makeFn(node, scope, ctx);
      case 'block': { var res; for (var b = 0; b < node.body.length; b++) { res = ev(node.body[b], scope, ctx); if (ctx._ret || ctx._brk || ctx._cont) return res; } return res; }
      case 'if': { if (ev(node.test, scope, ctx)) { ev(node.cons, scope, ctx); } else if (node.alt) { ev(node.alt, scope, ctx); } return undefined; }
      case 'break': { ctx._brk = true; return undefined; }
      case 'continue': { ctx._cont = true; return undefined; }
      case 'while': {
        var guardW = 0;
        while (ev(node.test, scope, ctx) && guardW++ < 1000000) {
          ev(node.body, scope, ctx);
          if (ctx._ret) return ctx._retVal;
          if (ctx._brk) { ctx._brk = false; break; }
          if (ctx._cont) { ctx._cont = false; }
        }
        return undefined;
      }
      case 'for': {
        if (node.init) ev(node.init, scope, ctx);
        var guardF = 0;
        while ((node.test ? ev(node.test, scope, ctx) : true) && guardF++ < 1000000) {
          ev(node.body, scope, ctx);
          if (ctx._ret) return ctx._retVal;
          if (ctx._brk) { ctx._brk = false; break; }
          if (ctx._cont) { ctx._cont = false; }
          if (node.update) ev(node.update, scope, ctx);
        }
        return undefined;
      }
      case 'forof': {
        var iterable = ev(node.iter, scope, ctx);
        if (iterable) {
          var arrOf = Array.from(iterable);
          for (var oi = 0; oi < arrOf.length; oi++) {
            if (node.name) (ctx.locals || (ctx.locals = {}))[node.name] = arrOf[oi];
            ev(node.body, scope, ctx);
            if (ctx._ret) return ctx._retVal;
            if (ctx._brk) { ctx._brk = false; break; }
            if (ctx._cont) { ctx._cont = false; }
          }
        }
        return undefined;
      }
      case 'forin': {
        var obj2 = ev(node.iter, scope, ctx);
        if (obj2) {
          for (var kIn in obj2) {
            if (node.name) (ctx.locals || (ctx.locals = {}))[node.name] = kIn;
            ev(node.body, scope, ctx);
            if (ctx._ret) return ctx._retVal;
            if (ctx._brk) { ctx._brk = false; break; }
            if (ctx._cont) { ctx._cont = false; }
          }
        }
        return undefined;
      }
      case 'return': { ctx._ret = true; ctx._retVal = node.arg ? ev(node.arg, scope, ctx) : undefined; return ctx._retVal; }
      case 'var': { node.decls.forEach(function (d) { var val = d.init ? ev(d.init, scope, ctx) : undefined; (ctx.locals || (ctx.locals = {}))[d.name] = val; }); return undefined; }
      case 'try': {
        try { for (var ti = 0; ti < node.block.length; ti++) { ev(node.block[ti], scope, ctx); if (ctx._ret) break; } }
        catch (err) { if (node.handler) { if (node.handler.param) (ctx.locals || (ctx.locals = {}))[node.handler.param] = err; for (var hi = 0; hi < node.handler.body.length; hi++) { ev(node.handler.body[hi], scope, ctx); if (ctx._ret) break; } } }
        finally { if (node.finalizer) { for (var fi = 0; fi < node.finalizer.length; fi++) ev(node.finalizer[fi], scope, ctx); } }
        return undefined;
      }
      case 'spread': return ev(node.arg, scope, ctx);
    }
    throw new Error('cannot evaluate node ' + node.t);
  }

  function readId(name, scope, ctx) {
    if (ctx && ctx.locals && name in ctx.locals) return ctx.locals[name];
    // Top-level `this` in an Alpine expression is the component (the scope).
    // Inside a method, ctx.locals['this'] is set and handled above.
    if (name === 'this') return scope;
    if (name === 'undefined') return undefined;
    if (name === 'NaN') return NaN; if (name === 'Infinity') return Infinity;
    if (scope && (name in scope)) return scope[name];
    // globals allowed (read-only)
    if (typeof GLOBALS[name] !== 'undefined') return GLOBALS[name];
    if (typeof global[name] !== 'undefined') return global[name];
    return undefined;
  }
  var GLOBALS = { Math: Math, JSON: JSON, Object: Object, Array: Array, String: String,
    Number: Number, Boolean: Boolean, Date: Date, RegExp: RegExp, parseInt: parseInt,
    parseFloat: parseFloat, isNaN: isNaN, isFinite: isFinite, console: (typeof console !== 'undefined' ? console : undefined) };

  function lref(node, scope, ctx) {
    if (node.t === 'id') {
      var name = node.name;
      if (ctx && ctx.locals && name in ctx.locals) return { get: function () { return ctx.locals[name]; }, set: function (v) { ctx.locals[name] = v; } };
      return { get: function () { return scope[name]; }, set: function (v) { scope[name] = v; } };
    }
    if (node.t === 'member') {
      var obj = ev(node.obj, scope, ctx);
      var key = node.computed ? ev(node.prop, scope, ctx) : node.prop.v;
      return { get: function () { return obj == null ? undefined : obj[key]; }, set: function (v) { obj[key] = v; } };
    }
    throw new Error('invalid assignment target');
  }

  function evalArgs(list, scope, ctx) {
    var out = [];
    list.forEach(function (a) { if (a.t === 'spread') { var sp = ev(a.arg, scope, ctx); for (var x of sp) out.push(x); } else out.push(ev(a, scope, ctx)); });
    return out;
  }

  function doCall(node, scope, ctx) {
    var callee = node.callee, thisArg, fn;
    if (callee.t === 'member') {
      thisArg = ev(callee.obj, scope, ctx);
      if ((callee.optional || node.optional) && (thisArg === null || thisArg === undefined)) return undefined;
      var key = callee.computed ? ev(callee.prop, scope, ctx) : callee.prop.v;
      fn = thisArg == null ? undefined : thisArg[key];
    } else {
      // Bare call `foo()` (not `obj.foo()`). Alpine runs expressions with `this`
      // = the component, so a component method must be called with this=scope
      // (e.g. x-init="init()" whose init() calls this.load()). BUT a native
      // global (setInterval/setTimeout/fetch/…) must be called with this=window
      // or it throws "Illegal invocation". Distinguish: if the resolved function
      // is the same reference as the global of that name, it's a global -> no
      // scope this; otherwise it's a component method -> this=scope.
      fn = ev(callee, scope, ctx);
      if (callee.t === 'id' && global && global[callee.name] === fn) {
        thisArg = global;   // native/global function: bind to window
      } else {
        thisArg = scope;    // component method: Alpine's `this` = component
      }
    }
    if (node.optional && (fn === null || fn === undefined)) return undefined;
    var args = evalArgs(node.args, scope, ctx);
    if (typeof fn !== 'function') throw new TypeError((callee.t === 'member' ? callee.prop.v : callee.name) + ' is not a function');
    return fn.apply(thisArg, args);
  }

  function makeFn(node, scope, ctx) {
    var params = node.params;
    return function () {
      var callArgs = arguments;
      var fctx = { locals: Object.create((ctx && ctx.locals) || null), _ret: false, _retVal: undefined };
      // `this`: arrows inherit lexically (Alpine binds x-data methods' `this` to
      // the reactive component at call time); function/method exprs get the JS
      // runtime `this`. Exposing it as a local lets `this.foo` resolve via readId.
      if (node.t !== 'arrow') fctx.locals['this'] = this;
      params.forEach(function (p, idx) {
        if (p.rest) { fctx.locals[p.name] = Array.prototype.slice.call(callArgs, idx); }
        else { var v = callArgs[idx]; if (v === undefined && p.def) v = ev(p.def, scope, fctx); fctx.locals[p.name] = v; }
      });
      var body = node.body;
      if (node.t === 'arrow') {
        if (body.t === 'block') { ev(body, scope, fctx); return fctx._retVal; }
        return ev(body, scope, fctx);
      }
      ev({ t: 'block', body: body }, scope, fctx);
      return fctx._retVal;
    };
  }

  function binop(op, l, r) {
    switch (op) {
      case '+': return l + r; case '-': return l - r; case '*': return l * r; case '/': return l / r; case '%': return l % r;
      case '==': return l == r; case '!=': return l != r; case '===': return l === r; case '!==': return l !== r;
      case '<': return l < r; case '<=': return l <= r; case '>': return l > r; case '>=': return l >= r;
      case '&': return l & r; case '|': return l | r; case '^': return l ^ r;
      case 'in': return l in r; case 'instanceof': return l instanceof r;
    }
    throw new Error('bad binop ' + op);
  }

  function run(astOrSrc, scope) {
    var ast = typeof astOrSrc === 'string' ? compile(astOrSrc) : astOrSrc;
    var ctx = { locals: null, _ret: false, _retVal: undefined };
    return ev(ast, scope || {}, ctx);
  }

  global.CSPExpr = { compile: compile, run: run, tokenize: tokenize };
})(typeof window !== 'undefined' ? window : globalThis);
