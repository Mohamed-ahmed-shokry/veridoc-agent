"""Static rendering for the authenticated Phase 9 review console."""


def render_review_console_page() -> str:
    """Return the browser-session login/logout shell for the review console."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Veridoc review console</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 52rem; padding: 0 1rem; }
    form, section { border: 1px solid #d1d5db; border-radius: .5rem; padding: 1rem; margin: 1rem 0; }
    button { margin-top: .75rem; padding: .5rem .75rem; }
    label { display: block; margin-top: .5rem; }
    input { width: 100%; box-sizing: border-box; padding: .4rem; }
    .error { color: #b91c1c; }
    .hidden { display: none; }
    .case-row { border: 1px solid #e5e7eb; border-radius: .4rem; padding: .6rem; margin: .5rem 0; }
    .case-row p { margin: .2rem 0; }
    .finding, .event-row { background: #f9fafb; border-radius: .4rem; padding: .6rem; margin: .5rem 0; }
    .review_required { border-left: .4rem solid #b45309; }
    .clear { border-left: .4rem solid #15803d; }
  </style>
</head>
<body>
  <main>
    <h1>Veridoc review console</h1>

    <section id="login-section">
      <h2>Sign in</h2>
      <form id="login-form">
        <label for="credential">Actor credential</label>
        <input id="credential" name="credential" type="password" autocomplete="off" required>
        <button type="submit">Sign in</button>
      </form>
      <p id="login-status" aria-live="polite"></p>
    </section>

    <section id="session-section" class="hidden">
      <h2>Session</h2>
      <p id="session-summary"></p>
      <button id="logout-button" type="button">Sign out</button>
      <p id="session-status" aria-live="polite"></p>
    </section>

    <section id="cases-section" class="hidden">
      <h2>Review cases</h2>
      <button id="refresh-cases-button" type="button">Refresh</button>
      <p id="case-list-status" aria-live="polite"></p>
      <div id="case-list"></div>
    </section>

    <section id="detail-section" class="hidden">
      <h2>Case detail</h2>
      <p id="detail-status" aria-live="polite"></p>
      <div id="case-detail"></div>

      <h3>Claim or assign</h3>
      <form id="assign-form">
        <label for="assign-actor-id">Assign to actor ID (blank claims for yourself)</label>
        <input id="assign-actor-id" name="assign-actor-id" type="text" autocomplete="off">
        <label for="assign-reason">Reason (required when reassigning)</label>
        <input id="assign-reason" name="assign-reason" type="text" autocomplete="off">
        <button type="submit">Claim / assign</button>
      </form>
      <p id="assign-status" aria-live="polite"></p>

      <h3>Escalate</h3>
      <form id="escalate-form">
        <label for="escalate-reason">Reason</label>
        <input id="escalate-reason" name="escalate-reason" type="text" autocomplete="off" required>
        <button type="submit">Escalate</button>
      </form>
      <p id="escalate-status" aria-live="polite"></p>

      <h3>Decide</h3>
      <form id="decide-form">
        <label for="decide-value">Decision</label>
        <select id="decide-value" name="decide-value">
          <option value="accept">Accept</option>
          <option value="reject">Reject</option>
          <option value="needs_correction">Needs correction</option>
        </select>
        <label for="decide-reason">Reason</label>
        <input id="decide-reason" name="decide-reason" type="text" autocomplete="off" required>
        <button type="submit">Record decision</button>
      </form>
      <p id="decide-status" aria-live="polite"></p>
    </section>
  </main>
  <script>
    const loginSection = document.getElementById("login-section");
    const loginForm = document.getElementById("login-form");
    const credentialInput = document.getElementById("credential");
    const loginStatus = document.getElementById("login-status");
    const sessionSection = document.getElementById("session-section");
    const sessionSummary = document.getElementById("session-summary");
    const sessionStatus = document.getElementById("session-status");
    const logoutButton = document.getElementById("logout-button");
    const casesSection = document.getElementById("cases-section");
    const caseList = document.getElementById("case-list");
    const caseListStatus = document.getElementById("case-list-status");
    const refreshCasesButton = document.getElementById("refresh-cases-button");
    const detailSection = document.getElementById("detail-section");
    const detailStatus = document.getElementById("detail-status");
    const caseDetail = document.getElementById("case-detail");
    const assignForm = document.getElementById("assign-form");
    const assignActorId = document.getElementById("assign-actor-id");
    const assignReason = document.getElementById("assign-reason");
    const assignStatus = document.getElementById("assign-status");
    const escalateForm = document.getElementById("escalate-form");
    const escalateReason = document.getElementById("escalate-reason");
    const escalateStatus = document.getElementById("escalate-status");
    const decideForm = document.getElementById("decide-form");
    const decideValue = document.getElementById("decide-value");
    const decideReason = document.getElementById("decide-reason");
    const decideStatus = document.getElementById("decide-status");

    let currentCaseId = null;
    let currentVersion = null;

    function readCookie(name) {
      const prefix = name + "=";
      const cookie = document.cookie.split("; ").find(entry => entry.startsWith(prefix));
      return cookie ? cookie.slice(prefix.length) : null;
    }

    function textRow(label, value) {
      const row = document.createElement("p");
      const name = document.createElement("strong");
      name.textContent = label + ": ";
      row.append(name, document.createTextNode(value));
      return row;
    }

    function showSignedOut() {
      loginSection.classList.remove("hidden");
      sessionSection.classList.add("hidden");
      casesSection.classList.add("hidden");
      detailSection.classList.add("hidden");
      caseList.replaceChildren();
      caseListStatus.textContent = "";
      caseDetail.replaceChildren();
      detailStatus.textContent = "";
      currentCaseId = null;
      currentVersion = null;
      assignStatus.textContent = "";
      escalateStatus.textContent = "";
      decideStatus.textContent = "";
      credentialInput.value = "";
    }

    function showSignedIn(actor) {
      loginSection.classList.add("hidden");
      sessionSection.classList.remove("hidden");
      casesSection.classList.remove("hidden");
      sessionSummary.replaceChildren();
      const label = document.createElement("strong");
      label.textContent = "Signed in as: ";
      sessionSummary.append(label, document.createTextNode(actor.actor_id + " (" + actor.role + ")"));
      loadCases();
    }

    function renderCases(page) {
      caseList.replaceChildren();
      if (!page.records.length) {
        const empty = document.createElement("p");
        empty.textContent = "No review cases yet.";
        caseList.append(empty);
        return;
      }
      page.records.forEach(record => {
        const row = document.createElement("div");
        row.className = "case-row";
        row.append(
          textRow("Case", record.case_id),
          textRow("Status", record.status),
          textRow("Assignee", record.assignee_id ?? "Unassigned"),
          textRow("Version", String(record.version)),
          textRow("Updated", record.updated_at),
        );
        const viewButton = document.createElement("button");
        viewButton.type = "button";
        viewButton.textContent = "View";
        viewButton.addEventListener("click", () => loadCaseDetail(record.case_id));
        row.append(viewButton);
        caseList.append(row);
      });
    }

    function renderSnapshot(container, result) {
      const verdict = document.createElement("section");
      verdict.className = result.verdict.status;
      const verdictHeading = document.createElement("h3");
      verdictHeading.textContent = "Verdict: " + result.verdict.status.replace(/_/g, " ");
      verdict.append(
        verdictHeading,
        textRow("Summary", result.verdict.summary),
        textRow("Findings", String(result.verdict.finding_count)),
        textRow("Highest severity", result.verdict.highest_severity ?? "None"),
      );
      container.append(verdict);

      const extraction = document.createElement("section");
      const extractionHeading = document.createElement("h3");
      extractionHeading.textContent = "Extraction";
      extraction.append(
        extractionHeading,
        textRow("Document type", result.extraction.document_type ?? "Unknown"),
        textRow("Invoice number", result.extraction.invoice_number ?? "Not provided"),
        textRow("Vendor", result.extraction.vendor_name ?? "Not provided"),
        textRow(
          "Total",
          result.extraction.total != null ? String(result.extraction.total) : "Not provided",
        ),
      );
      container.append(extraction);

      const findings = document.createElement("section");
      const findingsHeading = document.createElement("h3");
      findingsHeading.textContent = "Findings";
      findings.append(findingsHeading);
      if (!result.findings.length) {
        const empty = document.createElement("p");
        empty.textContent = "No deterministic findings were returned.";
        findings.append(empty);
      }
      result.findings.forEach((finding, index) => {
        const item = document.createElement("div");
        item.className = "finding";
        const title = document.createElement("h4");
        title.textContent = finding.finding_type + " (" + finding.severity + ")";
        item.append(title, textRow("Evidence", finding.explanation));
        const explanation = result.explanations[index];
        if (explanation) {
          item.append(textRow("Review guidance", explanation.narrative));
          item.append(textRow("Numerical context", explanation.numerical_context));
        }
        findings.append(item);
      });
      container.append(findings);
    }

    function renderEvents(container, events) {
      const section = document.createElement("section");
      const heading = document.createElement("h3");
      heading.textContent = "Event timeline";
      section.append(heading);
      events.forEach(event => {
        const row = document.createElement("div");
        row.className = "event-row";
        row.append(
          textRow("Event", event.event_type),
          textRow("Actor", event.actor_id),
          textRow("Occurred", event.occurred_at),
          textRow("Status", (event.prior_status ?? "—") + " → " + event.resulting_status),
        );
        if (event.reason) row.append(textRow("Reason", event.reason));
        if (event.decision) row.append(textRow("Decision", event.decision));
        if (event.assigned_actor_id) row.append(textRow("Assigned to", event.assigned_actor_id));
        section.append(row);
      });
      container.append(section);
    }

    async function loadCaseDetail(caseId) {
      detailSection.classList.remove("hidden");
      detailStatus.textContent = "Loading case detail…";
      detailStatus.className = "";
      caseDetail.replaceChildren();
      try {
        const response = await fetch("/review/cases/" + encodeURIComponent(caseId));
        if (response.status === 401) {
          showSignedOut();
          return;
        }
        if (response.status === 404) {
          detailStatus.textContent = "";
          const notFound = document.createElement("p");
          notFound.textContent = "Case not found.";
          caseDetail.append(notFound);
          return;
        }
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail?.message || "Case detail could not be loaded.");
        }
        detailStatus.textContent = "";
        currentCaseId = data.case_id;
        currentVersion = data.version;
        assignStatus.textContent = "";
        assignActorId.value = "";
        assignReason.value = "";
        escalateStatus.textContent = "";
        escalateReason.value = "";
        decideStatus.textContent = "";
        decideReason.value = "";
        const summary = document.createElement("section");
        summary.append(
          textRow("Case", data.case_id),
          textRow("Status", data.status),
          textRow("Assignee", data.assignee_id ?? "Unassigned"),
          textRow("Version", String(data.version)),
        );
        caseDetail.append(summary);
        renderSnapshot(caseDetail, data.snapshot.result);
        renderEvents(caseDetail, data.events);
      } catch (error) {
        detailStatus.textContent = error.message;
        detailStatus.className = "error";
      }
    }

    async function loadCases() {
      caseListStatus.textContent = "Loading review cases…";
      caseListStatus.className = "";
      try {
        const response = await fetch("/review/cases?limit=50");
        if (response.status === 401) {
          showSignedOut();
          return;
        }
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail?.message || "Review cases could not be loaded.");
        }
        caseListStatus.textContent = "";
        renderCases(data);
      } catch (error) {
        caseListStatus.textContent = error.message;
        caseListStatus.className = "error";
      }
    }

    async function refreshSessionState() {
      try {
        const response = await fetch("/review/session", { method: "GET" });
        if (response.ok) {
          showSignedIn(await response.json());
        } else {
          showSignedOut();
        }
      } catch {
        showSignedOut();
      }
    }

    loginForm.addEventListener("submit", async event => {
      event.preventDefault();
      loginStatus.textContent = "Signing in…";
      loginStatus.className = "";
      try {
        const response = await fetch("/review/session", {
          method: "POST",
          headers: { Authorization: "Bearer " + credentialInput.value },
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail?.message || "Sign-in failed.");
        }
        loginStatus.textContent = "";
        showSignedIn(data);
      } catch (error) {
        loginStatus.textContent = error.message;
        loginStatus.className = "error";
      }
    });

    logoutButton.addEventListener("click", async () => {
      sessionStatus.textContent = "Signing out…";
      sessionStatus.className = "";
      try {
        const response = await fetch("/review/session", {
          method: "DELETE",
          headers: { "X-CSRF-Token": readCookie("veridoc_review_csrf") || "" },
        });
        if (!response.ok && response.status !== 401) {
          const data = await response.json();
          throw new Error(data.detail?.message || "Sign-out failed.");
        }
      } catch (error) {
        sessionStatus.textContent = error.message;
        sessionStatus.className = "error";
        return;
      }
      sessionStatus.textContent = "";
      showSignedOut();
    });

    refreshCasesButton.addEventListener("click", loadCases);

    async function submitCaseAction(method, path, body, statusElement) {
      statusElement.textContent = "Submitting…";
      statusElement.className = "";
      try {
        const response = await fetch(path, {
          method,
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
            "X-CSRF-Token": readCookie("veridoc_review_csrf") || "",
          },
          body: JSON.stringify(body),
        });
        if (response.status === 401) {
          showSignedOut();
          return false;
        }
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail?.message || "The request could not be submitted.");
        }
        statusElement.textContent = "";
        return true;
      } catch (error) {
        statusElement.textContent = error.message;
        statusElement.className = "error";
        return false;
      }
    }

    assignForm.addEventListener("submit", async event => {
      event.preventDefault();
      if (currentCaseId === null) {
        return;
      }
      const body = { expected_version: currentVersion };
      if (assignActorId.value) {
        body.actor_id = assignActorId.value;
      }
      if (assignReason.value) {
        body.reason = assignReason.value;
      }
      const path = "/review/cases/" + encodeURIComponent(currentCaseId) + "/assignment";
      const succeeded = await submitCaseAction("PUT", path, body, assignStatus);
      if (succeeded) {
        loadCases();
        loadCaseDetail(currentCaseId);
      }
    });

    escalateForm.addEventListener("submit", async event => {
      event.preventDefault();
      if (currentCaseId === null) {
        return;
      }
      const body = { expected_version: currentVersion, reason: escalateReason.value };
      const path = "/review/cases/" + encodeURIComponent(currentCaseId) + "/escalations";
      const succeeded = await submitCaseAction("POST", path, body, escalateStatus);
      if (succeeded) {
        loadCases();
        loadCaseDetail(currentCaseId);
      }
    });

    decideForm.addEventListener("submit", async event => {
      event.preventDefault();
      if (currentCaseId === null) {
        return;
      }
      const body = {
        expected_version: currentVersion,
        decision: decideValue.value,
        reason: decideReason.value,
      };
      const path = "/review/cases/" + encodeURIComponent(currentCaseId) + "/decisions";
      const succeeded = await submitCaseAction("POST", path, body, decideStatus);
      if (succeeded) {
        loadCases();
        loadCaseDetail(currentCaseId);
      }
    });

    refreshSessionState();
  </script>
</body>
</html>"""
