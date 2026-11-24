/* Bridge from CSS design tokens to concrete colours.
 *
 * Canvas 2D, Chart.js and SVG attributes cannot resolve `var(--token)` — an
 * invalid colour string is silently ignored, so the previous colour is kept and
 * the page looks fine while being wrong. Anything that needs a real colour
 * reads it from here instead of re-declaring a hex.
 *
 * Values are read lazily: the tokens live in base.css, and a getter means this
 * file is correct even if it is evaluated before the stylesheet is applied.
 */
window.BAM_TOK = (function () {
  function read(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  var named = {
    positive:  '--positive',
    negative:  '--negative',
    warning:   '--warning',
    accent:    '--accent',
    text:      '--text',
    textMuted: '--text-muted',
    textFaint: '--text-faint',
    surface:   '--surface',
    border:    '--border'
  };

  // Categorical slots used by the graph and charts. No token pair exists for
  // these — they distinguish node types, not semantics — so they are declared
  // once here rather than repeated per page.
  var out = { process: '#7cc4ff', metric: '#b6a6ff' };

  Object.keys(named).forEach(function (key) {
    Object.defineProperty(out, key, {
      enumerable: true,
      get: function () { return read(named[key]); }
    });
  });

  return out;
})();
