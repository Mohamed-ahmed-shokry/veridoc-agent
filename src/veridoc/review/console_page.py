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

    function readCookie(name) {
      const prefix = name + "=";
      const cookie = document.cookie.split("; ").find(entry => entry.startsWith(prefix));
      return cookie ? cookie.slice(prefix.length) : null;
    }

    function showSignedOut() {
      loginSection.classList.remove("hidden");
      sessionSection.classList.add("hidden");
      credentialInput.value = "";
    }

    function showSignedIn(actor) {
      loginSection.classList.add("hidden");
      sessionSection.classList.remove("hidden");
      sessionSummary.replaceChildren();
      const label = document.createElement("strong");
      label.textContent = "Signed in as: ";
      sessionSummary.append(label, document.createTextNode(actor.actor_id + " (" + actor.role + ")"));
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

    refreshSessionState();
  </script>
</body>
</html>"""
