/* Injected into each tool page (served only to authenticated users, inside a sandboxed iframe).
   1) It forwards generated files to the parent window, which uploads them to the backend with the user's session
      (this page never sees credentials; the tool's own processing code is unchanged).
   2) It applies the same UI-level deterrents as the main app (F12, Ctrl+Shift+I/J/C, Ctrl+U, right-click).
      These are deterrents only, NOT a security control - real protection is server-side. */
(function () {
  var TOOL = "__TOOL_SLUG__";

  /* ---- deterrents ---- */
  var isMac = /Mac|iPod|iPhone|iPad/.test(navigator.platform || "");
  document.addEventListener("keydown", function (e) {
    var k = String(e.key || "").toUpperCase();
    var ctrlCmd = e.ctrlKey || (isMac && e.metaKey);
    var shiftAlt = e.shiftKey || (isMac && e.altKey);
    var block = e.key === "F12" || e.code === "F12" ||
      (ctrlCmd && shiftAlt && (k === "I" || k === "J" || k === "C")) ||
      (e.ctrlKey && k === "U") || (isMac && e.metaKey && e.altKey && k === "U") ||
      (e.ctrlKey && e.shiftKey && k === "K");
    if (block) { e.preventDefault(); e.stopPropagation(); }
  }, true);
  document.addEventListener("contextmenu", function (e) { e.preventDefault(); }, true);

  /* ---- forward generated files to the parent ---- */
  var inputs = [];
  var seen = {};
  function remember(files) {
    for (var i = 0; i < (files ? files.length : 0); i++) inputs.push(files[i]);
    if (inputs.length > 25) inputs = inputs.slice(-25);
  }
  document.addEventListener("change", function (e) {
    var t = e.target; if (t && t.type === "file") remember(t.files);
  }, true);
  document.addEventListener("drop", function (e) {
    if (e.dataTransfer) remember(e.dataTransfer.files);
  }, true);
  function stem(n) { return String(n || "").replace(/\.[^.]*$/, "").toLowerCase(); }
  function pick(outName) {
    var s = stem(outName);
    for (var i = inputs.length - 1; i >= 0; i--) if (s && stem(inputs[i].name) && s.indexOf(stem(inputs[i].name)) !== -1) return inputs[i];
    return inputs.length ? inputs[inputs.length - 1] : null;
  }
  var origClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    try {
      var a = this;
      if (a.hasAttribute("download") && /^blob:/.test(a.href)) {
        var name = a.getAttribute("download") || "output";
        var key = name + "|" + Date.now().toString().slice(0, -3);
        if (!seen[key]) {
          seen[key] = 1;
          fetch(a.href).then(function (r) { return r.blob(); }).then(function (blob) {
            window.parent.postMessage({ source: "ff-tool", tool: TOOL, name: name, blob: blob, original: pick(name) }, "*");
          }).catch(function () {});
        }
      }
    } catch (err) {}
    return origClick.apply(this, arguments);
  };
})();
