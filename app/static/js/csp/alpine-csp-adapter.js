/* Alpine ↔ CSPExpr adapter (ARCH-070).
 *
 * Registers CSPExpr as Alpine's evaluator via Alpine.setEvaluator, so Alpine
 * stops using new Function() and the CSP can drop 'unsafe-eval'. Must run on
 * `alpine:init` (before Alpine.start compiles any expression).
 *
 * Alpine's evaluator contract (v3): setEvaluator(factory), where
 *   factory(el, expression) -> runner(receiver, { scope = {}, params = [] })
 * The runner evaluates `expression` against the element's data stack (plus any
 * extra `scope`, e.g. x-for vars, and Alpine magics), then calls receiver(result).
 */
(function (global) {
  'use strict';

  function install(Alpine) {
    var cache = Object.create(null);

    function compileCached(expression) {
      var ast = cache[expression];
      if (ast === undefined) {
        try { ast = global.CSPExpr.compile(expression); }
        catch (e) { ast = { __err: e }; }
        cache[expression] = ast;
      }
      return ast;
    }

    Alpine.setEvaluator(function (el, expression) {
      // Alpine passes either a string expression or (rarely) a function.
      if (typeof expression === 'function') {
        return function (receiver, extras) {
          extras = extras || {};
          var result = expression.apply(scopeFor(el, extras.scope), extras.params || []);
          runReceiver(receiver, result);
        };
      }
      var expr = String(expression).trim();
      var ast = compileCached(expr);

      return function (receiver, extras) {
        extras = extras || {};
        receiver = receiver || function () {};
        if (ast && ast.__err) throw ast.__err;
        var scope = scopeFor(el, extras.scope);
        var result = global.CSPExpr.run(ast, scope);
        runReceiver(receiver, result);
      };
    });

    // Build the evaluation scope: element data stack + Alpine magics + any extra
    // scope Alpine hands us (x-for iteration vars, $event on handlers, etc.).
    // Assignments write back to Alpine's reactive data so reactivity is preserved.
    function scopeFor(el, extraScope) {
      var base = el ? Alpine.$data(el) : {};
      var magics = buildMagics(el);
      return new Proxy({}, {
        has: function () { return true; },
        get: function (_t, k) {
          if (typeof k === 'symbol') return undefined;
          if (extraScope && k in extraScope) return extraScope[k];
          if (magics.hasOwnProperty(k)) return magics[k]();  // lazy magic
          // Component data next.
          if (base && (k in base)) return base[k];
          // CRITICAL: fall back to the REAL global for names not on the
          // component (window, document, localStorage, console, JSON, Date, …).
          // Without this, an Alpine expression like `window.addEventListener(...)`
          // or `localStorage.getItem(...)` resolves the identifier through this
          // proxy to undefined and throws — which broke every page whose Alpine
          // uses a browser global (e.g. the composer's resize handler). The
          // `has` trap must stay `true` (Alpine's with()-scope contract), so the
          // real fallback has to happen here in get().
          if (k in global) return global[k];
          return base ? base[k] : undefined;
        },
        set: function (_t, k, v) {
          if (extraScope && k in extraScope) { extraScope[k] = v; return true; }
          // Assign onto the component data when it owns the key, otherwise let a
          // genuine global assignment (rare in Alpine) hit the global.
          if (base && (k in base)) { base[k] = v; return true; }
          if (k in global) { try { global[k] = v; } catch (e) { /* read-only global */ } return true; }
          if (base) { base[k] = v; return true; }
          return true;
        }
      });
    }

    // Built-in Alpine 3 magics, reimplemented with Alpine's public API. Each is a
    // thunk so it's only constructed when the expression actually reads it.
    function buildMagics(el) {
      return {
        '$el': function () { return el; },
        '$refs': function () { return collectRefs(el); },
        '$store': function () { return Alpine.store(); },
        '$data': function () { return Alpine.$data(el); },
        '$root': function () { return Alpine.closestRoot ? Alpine.closestRoot(el) : rootOf(el); },
        '$nextTick': function () { return Alpine.nextTick; },
        '$dispatch': function () {
          return function (name, detail) {
            el.dispatchEvent(new CustomEvent(name, { detail: detail, bubbles: true, composed: true, cancelable: true }));
          };
        },
        '$id': function () { return Alpine.$id ? Alpine.$id : function (n, k) { return n + (k !== undefined ? '-' + k : ''); }; },
        '$watch': function () {
          return function (path, cb) {
            // Evaluate `path` as a getter against the live scope and watch it.
            var getter = function () { return global.CSPExpr.run(path, scopeFor(el)); };
            return Alpine.effect(function () { var v = getter(); Alpine.nextTick(function () {}); return cb ? undefined : v; }), watchGetter(getter, cb);
          };
        }
      };
    }

    function watchGetter(getter, cb) {
      var old; var first = true;
      return Alpine.effect(function () {
        var v = getter();
        if (first) { old = v; first = false; return; }
        if (v !== old) { var prev = old; old = v; cb(v, prev); }
      });
    }

    function rootOf(el) { var n = el; while (n && !(n._x_dataStack)) n = n.parentElement; return n || el; }

    function collectRefs(el) {
      // Alpine stores refs at the nearest ancestor carrying x-ref children via
      // _x_refs. Merge refs found along the ancestor chain (nearest wins).
      var refs = {}, n = el;
      while (n) {
        if (n._x_refs) { for (var k in n._x_refs) { if (!(k in refs)) refs[k] = n._x_refs[k]; } }
        n = n.parentElement;
      }
      return refs;
    }

    function runReceiver(receiver, result) {
      // Alpine unwraps a returned function by calling it (dontAutoEvaluate aside).
      receiver(result);
    }
  }

  // Auto-install on alpine:init if Alpine is present.
  global.document && global.document.addEventListener('alpine:init', function () {
    if (global.Alpine && global.CSPExpr) install(global.Alpine);
  });

  global.CSPAlpineAdapter = { install: install };
})(typeof window !== 'undefined' ? window : globalThis);
