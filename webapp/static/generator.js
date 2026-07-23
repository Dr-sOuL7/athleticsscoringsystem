// Client-side sample-file generator.
//
// Produces a realistic, VALID random meet entirely in the browser (no server
// call, so it never touches the serverless function): a Main Results file
// keyed by bib number, and an optional matching Roster file. Output is CSV,
// which the scoring engine accepts directly.
(function () {
  "use strict";

  var gen = document.getElementById("generator");
  if (!gen) return;

  // --- Sample data pools --------------------------------------------------
  // Events are gender-neutral names the scoring engine recognises for both
  // men and women, each with a plausible result range.
  var EVENTS = [
    { name: "100m", type: "TIME", min: 10.5, max: 13.8 },
    { name: "200m", type: "TIME", min: 21.0, max: 28.5 },
    { name: "400m", type: "TIME", min: 46.0, max: 62.0 },
    { name: "800m", type: "TIME", min: 110, max: 152 },   // seconds -> m:ss
    { name: "1500m", type: "TIME", min: 225, max: 315 },
    { name: "Long Jump", type: "DISTANCE", min: 4.4, max: 8.1 },
    { name: "High Jump", type: "DISTANCE", min: 1.45, max: 2.28 },
    { name: "Shot Put", type: "DISTANCE", min: 8.0, max: 20.5 },
    { name: "Discus Throw", type: "DISTANCE", min: 24, max: 66 },
    { name: "Javelin Throw", type: "DISTANCE", min: 30, max: 82 }
  ];

  var FIRST = ["Aarav", "Priya", "Rahul", "Sneha", "Karan", "Ananya", "Vikram",
    "Divya", "Arjun", "Meera", "Rohan", "Kavya", "Aditya", "Ritika", "Sameer",
    "Pooja", "Nikhil", "Isha", "Yash", "Tanvi", "Dev", "Naina", "Kabir", "Riya"];
  var LAST = ["Sharma", "Verma", "Patel", "Singh", "Nair", "Das", "Rao", "Khan",
    "Reddy", "Gupta", "Menon", "Iyer", "Bose", "Pillai", "Joshi", "Shah",
    "Desai", "Kapoor"];
  var COLLEGES = ["Fergusson College", "St. Xavier's", "Loyola College",
    "Christ University", "Presidency College", "Hindu College"];
  var GENDERS = ["Male", "Female"];

  function randInt(n) { return Math.floor(Math.random() * n); }
  function pick(arr) { return arr[randInt(arr.length)]; }
  function randIn(min, max) { return min + Math.random() * (max - min); }

  function formatTime(sec) {
    if (sec < 60) return sec.toFixed(2);
    var m = Math.floor(sec / 60);
    var s = sec - m * 60;
    return m + ":" + (s < 10 ? "0" : "") + s.toFixed(2);
  }

  function randomResult(ev) {
    var v = randIn(ev.min, ev.max);
    return ev.type === "TIME" ? formatTime(v) : v.toFixed(2);
  }

  // Minimal RFC-4180 CSV field escaping.
  function csvField(value) {
    var s = String(value);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function csvRows(rows) {
    return rows.map(function (r) { return r.map(csvField).join(","); }).join("\r\n") + "\r\n";
  }

  // --- Generation ---------------------------------------------------------
  function generate(rowCount, withRoster) {
    // Use fewer distinct bibs than rows so some athletes have multiple events
    // (exercises the per-bib score summing).
    var nBibs = Math.max(1, Math.round(rowCount * 0.75));
    var athletes = {};            // bib -> {gender, name, id, college}
    var bibs = [];
    for (var i = 0; i < nBibs; i++) {
      var bib = String(101 + i);
      bibs.push(bib);
      athletes[bib] = {
        gender: pick(GENDERS),
        name: pick(FIRST) + " " + pick(LAST),
        id: "A" + (1000 + i),
        college: pick(COLLEGES)
      };
    }

    var mainRows = [["BIB NUMBER", "GENDER", "EVENT NAME", "PERFORMANCE TYPE", "RESULT"]];
    var used = {};
    for (var j = 0; j < rowCount; j++) {
      var b = pick(bibs);
      used[b] = true;
      var ev = pick(EVENTS);
      mainRows.push([b, athletes[b].gender, ev.name, ev.type, randomResult(ev)]);
    }

    var result = { main: csvRows(mainRows), preview: mainRows.slice(0, 9), roster: null };

    if (withRoster) {
      var rosterRows = [["BIB NUMBER", "NAME", "ID", "COLLEGE"]];
      // Only include bibs that actually appear in the main file.
      bibs.forEach(function (b) {
        if (used[b]) {
          var a = athletes[b];
          rosterRows.push([b, a.name, a.id, a.college]);
        }
      });
      result.roster = csvRows(rosterRows);
      result.athleteCount = rosterRows.length - 1;
    } else {
      result.athleteCount = Object.keys(used).length;
    }
    return result;
  }

  // --- Wiring -------------------------------------------------------------
  var rowsInput = document.getElementById("gen-rows");
  var rosterCheck = document.getElementById("gen-roster");
  var btn = document.getElementById("gen-btn");
  var output = document.getElementById("gen-output");
  var dlMain = document.getElementById("gen-dl-main");
  var dlRoster = document.getElementById("gen-dl-roster");
  var note = document.getElementById("gen-note");
  var preview = document.getElementById("gen-preview");

  var objectUrls = [];
  function freshUrl(text) {
    var url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
    objectUrls.push(url);
    return url;
  }
  function revokeUrls() {
    objectUrls.forEach(function (u) { URL.revokeObjectURL(u); });
    objectUrls = [];
  }

  function renderPreview(rows) {
    var html = "<thead><tr>";
    rows[0].forEach(function (h) { html += "<th>" + h + "</th>"; });
    html += "</tr></thead><tbody>";
    for (var i = 1; i < rows.length; i++) {
      html += "<tr>";
      rows[i].forEach(function (c) { html += "<td>" + c + "</td>"; });
      html += "</tr>";
    }
    preview.innerHTML = html + "</tbody>";
  }

  function clampRows() {
    var n = parseInt(rowsInput.value, 10);
    if (isNaN(n) || n < 1) n = 1;
    if (n > 2000) n = 2000;
    rowsInput.value = n;
    return n;
  }

  if (btn) {
    btn.addEventListener("click", function () {
      var n = clampRows();
      var withRoster = !!(rosterCheck && rosterCheck.checked);
      var data = generate(n, withRoster);

      revokeUrls();
      dlMain.href = freshUrl(data.main);
      if (withRoster && data.roster) {
        dlRoster.href = freshUrl(data.roster);
        dlRoster.hidden = false;
      } else {
        dlRoster.hidden = true;
      }

      note.textContent =
        "Generated " + n + " performance row" + (n === 1 ? "" : "s") + " for " +
        data.athleteCount + " athlete" + (data.athleteCount === 1 ? "" : "s") +
        (withRoster ? " (+ matching roster)" : "") +
        ". Download, then upload above — Results is required, Roster is optional.";
      renderPreview(data.preview);
      output.hidden = false;
    });
  }
})();
