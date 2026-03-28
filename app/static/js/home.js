const TOKEN_KEY = "rezgian_character_token";

function setSectionVisibility(elementId, isVisible) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }

    element.style.display = isVisible ? "" : "none";
}

function setLoggedInUI(hasToken) {
    setSectionVisibility("create-section", !hasToken);
    setSectionVisibility("import-section", !hasToken);
}

function setStatus(message, isError = false) {
    const status = document.getElementById("status");
    status.textContent = message;
    status.style.color = isError ? "#ffbc9a" : "#f3d7a8";
}

function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function redirectToLastRoom(character) {
    const room = character.last_room_id || "tavern";
    window.location.href = `/room/${room}`;
}

async function createCharacter() {
    const name = document.getElementById("character-name").value.trim();
    if (!name) {
        setStatus("Enter a character name.", true);
        return;
    }

    try {
        const res = await fetch("/api/auth/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name })
        });
        const data = await res.json();
        if (!res.ok) {
            setStatus(data.detail || "Could not create character.", true);
            return;
        }

        saveToken(data.token);
        setStatus(`Welcome, ${data.character.name}. Redirecting...`);
        redirectToLastRoom(data.character);
    } catch (error) {
        setStatus("Network error while creating character.", true);
    }
}

async function continueCharacter() {
    const token = getToken();
    if (!token) {
        setLoggedInUI(false);
        setStatus("No saved token found in this browser.", true);
        return;
    }

    try {
        const res = await fetch("/api/auth/continue", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token })
        });
        const data = await res.json();
        if (!res.ok) {
            localStorage.removeItem(TOKEN_KEY);
            setLoggedInUI(false);
            setStatus(data.detail || "Saved token is invalid.", true);
            return;
        }

        saveToken(data.token);
        setStatus(`Welcome back, ${data.character.name}. Redirecting...`);
        redirectToLastRoom(data.character);
    } catch (error) {
        setStatus("Network error while continuing.", true);
    }
}

async function importToken() {
    const token = document.getElementById("import-token").value.trim();
    if (!token) {
        setStatus("Paste a token to import.", true);
        return;
    }

    try {
        const res = await fetch("/api/auth/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token })
        });
        const data = await res.json();
        if (!res.ok) {
            setStatus(data.detail || "Token import failed.", true);
            return;
        }

        saveToken(data.token);
        setStatus(`Token imported for ${data.character.name}. Redirecting...`);
        redirectToLastRoom(data.character);
    } catch (error) {
        setStatus("Network error while importing token.", true);
    }
}

function showToken() {
    const token = getToken();
    if (!token) {
        setStatus("No saved token in this browser.", true);
        return;
    }

    setStatus(`Saved token: ${token}`);
}

function initializeTokenUI() {
    const hasToken = Boolean(getToken());
    setLoggedInUI(hasToken);

    if (hasToken) {
        setStatus("Saved token found. Press Continue to log back in.");
    }
}

document.getElementById("create-btn").addEventListener("click", createCharacter);
document.getElementById("continue-btn").addEventListener("click", continueCharacter);
document.getElementById("import-btn").addEventListener("click", importToken);
document.getElementById("show-token-btn").addEventListener("click", showToken);
initializeTokenUI();
