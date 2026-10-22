/* Small progressive-enhancement helpers: table sorting, live filtering,
   and the cost calculator. The site works without JavaScript; the data is
   all present in the HTML. */

(function () {
  "use strict";

  function cellValue(row, index) {
    var cell = row.children[index];
    if (!cell) return 0;
    var raw = cell.getAttribute("data-v");
    if (raw !== null && raw !== "") {
      var n = parseFloat(raw);
      if (!isNaN(n)) return n;
    }
    return (cell.textContent || "").trim().toLowerCase();
  }

  function sortTable(table, th) {
    var index = Array.prototype.indexOf.call(th.parentNode.children, th);
    var body = table.tBodies[0];
    if (!body) return;
    var rows = Array.prototype.slice.call(body.rows);
    var desc = th.classList.contains("sorted-asc");
    rows.sort(function (a, b) {
      var x = cellValue(a, index), y = cellValue(b, index);
      if (typeof x === "number" && typeof y === "number") {
        return desc ? y - x : x - y;
      }
      return desc ? String(y).localeCompare(String(x)) : String(x).localeCompare(String(y));
    });
    Array.prototype.forEach.call(th.parentNode.children, function (other) {
      other.classList.remove("sorted-asc", "sorted-desc");
    });
    th.classList.add(desc ? "sorted-desc" : "sorted-asc");
    rows.forEach(function (row) { body.appendChild(row); });
  }

  document.addEventListener("click", function (event) {
    var th = event.target.closest("th[data-sort]");
    if (!th) return;
    sortTable(th.closest("table"), th);
  });

  document.querySelectorAll("[data-filter]").forEach(function (input) {
    var target = document.getElementById(input.getAttribute("data-filter"));
    if (!target) return;
    var counter = document.getElementById(input.getAttribute("data-count") || "");
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      Array.prototype.forEach.call(target.tBodies[0].rows, function (row) {
        var hay = (row.getAttribute("data-name") || row.textContent).toLowerCase();
        var hit = !q || hay.indexOf(q) !== -1;
        row.classList.toggle("hidden", !hit);
        if (hit) shown++;
      });
      if (counter) counter.textContent = String(shown);
    });
  });

  var calc = document.getElementById("compare");
  if (calc) {
    var modelSelect = document.getElementById("cmp-model");
    var inVol = document.getElementById("cmp-in");
    var outVol = document.getElementById("cmp-out");
    var out = document.getElementById("compare-out");

    function money(n) {
      if (n === null || n === undefined || isNaN(n) || !isFinite(n)) return "—";
      if (n === 0) return "$0.00";
      // Below a cent, fixed decimals would round the answer to zero.
      if (n < 0.01) return "$" + parseFloat(n.toPrecision(2)).toString();
      if (n < 1) return "$" + n.toFixed(3);
      return "$" + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function run() {
      var value = modelSelect.value;
      if (!value) { out.innerHTML = ""; return; }
      var parts = value.split("|");
      var inPrice = parseFloat(parts[0]), outPrice = parseFloat(parts[1]);
      var inTokens = parseFloat(inVol.value) || 0;
      var outTokens = parseFloat(outVol.value) || 0;
      var inCost = (inTokens / 1e6) * inPrice;
      var outCost = (outTokens / 1e6) * outPrice;
      out.innerHTML =
        '<div class="tablewrap"><table><tbody>' +
        '<tr><td>Input — ' + inTokens.toLocaleString() + ' tokens × ' + money(inPrice) + '/1M</td><td class="num">' + money(inCost) + "</td></tr>" +
        '<tr><td>Output — ' + outTokens.toLocaleString() + ' tokens × ' + money(outPrice) + '/1M</td><td class="num">' + money(outCost) + "</td></tr>" +
        '<tr><td><strong>Total per request</strong></td><td class="num"><strong>' + money(inCost + outCost) + "</strong></td></tr>" +
        '<tr><td class="muted">× 1M requests</td><td class="num muted">' + money((inCost + outCost) * 1e6) + "</td></tr>" +
        "</tbody></table></div>";
    }

    modelSelect.addEventListener("change", run);
    inVol.addEventListener("input", run);
    outVol.addEventListener("input", run);
    run();
  }
})();
