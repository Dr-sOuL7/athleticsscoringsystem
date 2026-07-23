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

  // Client-side upload-size guard + double-submit protection.
  var form = document.querySelector(".upload-form");
  if (form && submitBtn) {
    var maxBytes = parseInt(form.getAttribute("data-max-bytes") || "0", 10);
    var maxMb = form.getAttribute("data-max-mb") || "4";
    var sizeError = document.getElementById("size-error");

    function totalSelectedBytes() {
      var total = 0;
      [input, document.getElementById("mapping-input")].forEach(function (el) {
        if (el && el.files) {
          for (var i = 0; i < el.files.length; i++) total += el.files[i].size;
        }
      });
      return total;
    }

    form.addEventListener("submit", function (e) {
      // Reject oversized uploads before hitting the serverless body limit.
      if (maxBytes > 0 && totalSelectedBytes() > maxBytes) {
        e.preventDefault();
        if (sizeError) {
          sizeError.textContent =
            "Your file(s) exceed the " + maxMb + " MB limit. Please split the " +
            "meet into smaller files or remove the optional roster.";
          sizeError.hidden = false;
          sizeError.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        return;
      }
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
