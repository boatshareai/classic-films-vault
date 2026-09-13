/* Licensing inquiry form: validation, ?title= prefill, submit. */
(function () {
  "use strict";

  var cfg = window.CFV_CONFIG || {};
  var form = document.getElementById("inquiry");
  var ok = document.getElementById("ok");
  var err = document.getElementById("err");
  var unconfigured = document.getElementById("unconfigured");
  var submit = document.getElementById("submit");
  var statusLine = document.getElementById("status-line");

  var REQUIRED = ["name", "company", "email"];

  /* --- prefill "Titles of interest" from a film page ------------------- */
  (function prefill() {
    var t = new URLSearchParams(location.search).get("title");
    if (!t) return;
    var field = document.getElementById("titles");
    field.value = t;
    // Make it obvious the field was filled for them.
    field.closest(".field").querySelector(".hint").textContent =
      "Pre-filled from " + t + " — add more titles if you like.";
    form.scrollIntoView({ behavior: "smooth", block: "center" });
  })();

  if (!cfg.ENDPOINT) unconfigured.hidden = false;

  function showErr(field, on) {
    var el = document.getElementById(field);
    var msg = form.querySelector('[data-err="' + field + '"]');
    if (el) el.setAttribute("aria-invalid", on ? "true" : "false");
    if (msg) msg.hidden = !on;
  }

  function validate() {
    var bad = null;
    REQUIRED.forEach(function (f) {
      var el = document.getElementById(f);
      var v = el.value.trim();
      var invalid =
        !v || (f === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v));
      showErr(f, invalid);
      if (invalid && !bad) bad = el;
    });
    return bad;
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    ok.hidden = true;
    err.hidden = true;

    var bad = validate();
    if (bad) {
      bad.focus();
      return;
    }

    var data = {
      name: document.getElementById("name").value.trim(),
      company: document.getElementById("company").value.trim(),
      email: document.getElementById("email").value.trim(),
      titles: document.getElementById("titles").value.trim(),
      use: document.getElementById("use").value,
      volume: document.getElementById("volume").value,
      message: document.getElementById("message").value.trim(),
    };

    if (!cfg.ENDPOINT) {
      unconfigured.hidden = false;
      unconfigured.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    var payload = data;
    if (cfg.MODE === "service") {
      // Shape the payload the way a generic form-to-email service expects.
      payload = {
        access_key: cfg.ACCESS_KEY,
        subject: "New licensing inquiry — " + (data.company || "unknown company"),
        from_name: data.name,
        email: data.email,
        Name: data.name,
        Company: data.company,
        Email: data.email,
        "Titles of interest": data.titles || "(not specified)",
        "Intended use": data.use || "(not specified)",
        "Estimated volume": data.volume || "(not specified)",
        Message: data.message || "(none)",
      };
      if (cfg.NOTIFY_TO) payload.to = cfg.NOTIFY_TO;
    }

    submit.disabled = true;
    statusLine.textContent = "Sending…";

    fetch(cfg.ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json().catch(function () {
          return {};
        });
      })
      .then(function () {
        form.hidden = true;
        unconfigured.hidden = true;
        ok.hidden = false;
        ok.scrollIntoView({ behavior: "smooth", block: "center" });
      })
      .catch(function (e) {
        err.textContent =
          "Sorry — that didn't go through (" +
          e.message +
          "). Please email us directly and we'll pick it up from there.";
        err.hidden = false;
        err.scrollIntoView({ behavior: "smooth", block: "center" });
      })
      .finally(function () {
        submit.disabled = false;
        statusLine.textContent = "";
      });
  });

  // Clear a field's error as soon as the user starts fixing it.
  REQUIRED.forEach(function (f) {
    document.getElementById(f).addEventListener("input", function () {
      showErr(f, false);
    });
  });
})();
