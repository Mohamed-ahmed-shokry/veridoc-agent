"""Static review-page rendering without a frontend build dependency."""


def render_review_page() -> str:
    """Return the minimal local interface for submitting and reviewing one invoice."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Veridoc review</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 52rem; padding: 0 1rem; }
    form, section { border: 1px solid #d1d5db; border-radius: .5rem; padding: 1rem; margin: 1rem 0; }
    button { margin-top: .75rem; padding: .5rem .75rem; }
    .review_required { border-left: .4rem solid #b45309; }
    .clear { border-left: .4rem solid #15803d; }
    .finding { background: #f9fafb; }
    .error { color: #b91c1c; }
  </style>
</head>
<body>
  <main>
    <h1>Veridoc review</h1>
    <p>Submit one fictional or approved invoice image/PDF for local processing.</p>
    <form id="review-form">
      <label for="invoice-file">Invoice or purchase order</label><br>
      <input id="invoice-file" name="file" type="file" accept="application/pdf,image/jpeg,image/png" required>
      <br><button type="submit">Process document</button>
    </form>
    <p id="review-status" aria-live="polite"></p>
    <div id="review-result"></div>
  </main>
  <script>
    const form = document.getElementById("review-form");
    const fileInput = document.getElementById("invoice-file");
    const status = document.getElementById("review-status");
    const result = document.getElementById("review-result");

    function textRow(label, value) {
      const row = document.createElement("p");
      const name = document.createElement("strong");
      name.textContent = label + ": ";
      row.append(name, document.createTextNode(value ?? "Not provided"));
      return row;
    }

    function addEvidence(extraction) {
      const section = document.createElement("section");
      const heading = document.createElement("h2");
      heading.textContent = "Extraction evidence";
      section.append(heading);
      Object.entries(extraction.evidence).forEach(([field, references]) => {
        const item = document.createElement("p");
        const values = references.map(reference =>
          "page " + reference.page_number + " (" + reference.source + ")" +
          (reference.text_span ? ": " + reference.text_span : "")
        );
        item.textContent = field + ": " + values.join("; ");
        section.append(item);
      });
      result.append(section);
    }

    function addFindings(data) {
      const section = document.createElement("section");
      const heading = document.createElement("h2");
      heading.textContent = "Findings";
      section.append(heading);
      if (!data.findings.length) {
        const empty = document.createElement("p");
        empty.textContent = "No deterministic findings were returned.";
        section.append(empty);
      }
      data.findings.forEach((finding, index) => {
        const item = document.createElement("section");
        item.className = "finding";
        const title = document.createElement("h3");
        title.textContent = finding.finding_type + " (" + finding.severity + ")";
        item.append(title, textRow("Evidence", finding.explanation));
        const explanation = data.explanations[index];
        if (explanation) {
          item.append(textRow("Review guidance", explanation.narrative));
          item.append(textRow("Numerical context", explanation.numerical_context));
        }
        section.append(item);
      });
      result.append(section);
    }

    function renderResult(data) {
      result.replaceChildren();
      const verdict = document.createElement("section");
      verdict.className = data.verdict.status;
      const heading = document.createElement("h2");
      heading.textContent = "Verdict: " + data.verdict.status.replace("_", " ");
      verdict.append(heading, textRow("Summary", data.verdict.summary));
      verdict.append(textRow("Findings", String(data.verdict.finding_count)));
      verdict.append(textRow("Highest severity", data.verdict.highest_severity));
      result.append(verdict);
      addEvidence(data.extraction);
      addFindings(data);
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!fileInput.files.length) {
        status.textContent = "Choose a document before processing.";
        status.className = "error";
        return;
      }
      status.textContent = "Processing document…";
      status.className = "";
      result.replaceChildren();
      const payload = new FormData();
      payload.append("file", fileInput.files[0]);
      try {
        const response = await fetch("/process", { method: "POST", body: payload });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail?.message || "The document could not be processed.");
        }
        renderResult(data);
        status.textContent = "Processing complete.";
      } catch (error) {
        status.textContent = error.message;
        status.className = "error";
      }
    });
  </script>
</body>
</html>"""
