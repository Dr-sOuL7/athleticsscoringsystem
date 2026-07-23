// Athletics Meet Scorer — small progressive-enhancement helpers.
// The app works fully without JavaScript; this only improves the experience.
(function () {
  "use strict";

  // ---- Upload: show the chosen filename and support drag & drop ----------
  var input = document.getElementById("file-input");
  var dropzone = document.getElementById("dropzone");
  var textEl = document.getElementById("dropzone-text");
  var submitBtn = document.getElementById("submit-btn");

  function showFilename(name) {
    if (textEl) {
      textEl.innerHTML = "<strong>" + name + "</strong> selected";
    }
    if (dropzone) dropzone.classList.add("has-file");
  }

  if (input) {
    input.addEventListener("change", function () {
      if (input.files && input.files.length) showFilename(input.files[0].name);
    });
  }

  // Optional mapping/roster file: reflect the chosen filename.
  var mapInput = document.getElementById("mapping-input");
  var mapZone = document.getElementById("dropzone-map");
  var mapText = document.getElementById("dropzone-map-text");
  if (mapInput) {
    mapInput.addEventListener("change", function () {
      if (mapInput.files && mapInput.files.length && mapText) {
        mapText.innerHTML = "<strong>" + mapInput.files[0].name + "</strong> selected";
        if (mapZone) mapZone.classList.add("has-file");
      }
    });
  }

  if (dropzone && input) {
    ["dragenter", "dragover"].forEach(function (evt) {
      dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        dropzone.classList.add("is-drag");
      });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        dropzone.classList.remove("is-drag");
      });
    });
    dropzone.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        showFilename(e.dataTransfer.files[0].name);
      }
    });
  }

  // Guard against double submits on large files.
  var form = document.querySelector(".upload-form");
  if (form && submitBtn) {
    form.addEventListener("submit", function () {
      submitBtn.disabled = true;
      submitBtn.textContent = "Scoring…";
    });
  }

  // ---- Results: tab switching -------------------------------------------
  var tabs = document.querySelector("[data-tabs]");
  if (tabs) {
    tabs.classList.add("tabs-enhanced");
    var buttons = tabs.querySelectorAll(".tab-btn");
    var panels = tabs.querySelectorAll(".tab-panel");

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var name = btn.getAttribute("data-tab");
        buttons.forEach(function (b) { b.classList.toggle("is-active", b === btn); });
        panels.forEach(function (p) {
          p.classList.toggle("is-active", p.getAttribute("data-panel") === name);
        });
      });
    });
  }
})();
