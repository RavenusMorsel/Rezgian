// roomId and roomAudio are injected by room.html

const TOKEN_KEY = "rezgian_character_token";
let activeCharacter = null;
let actionModeEnabled = false;
let chatSocket = null;

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Character load
// ---------------------------------------------------------------------------

async function loadCharacter() {
    const token = getToken();
    if (!token) {
        window.location.href = "/";
        return;
    }

    try {
        const res = await fetch("/api/auth/me", {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!res.ok) {
            localStorage.removeItem(TOKEN_KEY);
            window.location.href = "/";
            return;
        }

        const data = await res.json();
        activeCharacter = data.character;

        const badge = document.getElementById("active-character");
        if (badge) {
            badge.textContent = `Character: ${activeCharacter.name}`;
        }
    } catch (err) {
        console.error("Character load error:", err);
    }
}

// ---------------------------------------------------------------------------
// Message rendering
// ---------------------------------------------------------------------------

function appendMessage(username, message) {
    const log = document.getElementById("chat-log");
    const line = document.createElement("div");

    const isAction = typeof message === "string" && message.startsWith("/me ");
    if (isAction) {
        line.classList.add("chat-action");
        line.textContent = `* ${username} ${message.slice(4).trim()}`;
    } else {
        line.textContent = `${username}: ${message}`;
    }

    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
}

// ---------------------------------------------------------------------------
// Load history once via HTTP on page open
// ---------------------------------------------------------------------------

async function fetchHistory() {
    try {
        const res = await fetch(`/api/chat/fetch/${roomId}`);
        if (!res.ok) return;
        const data = await res.json();
        const log = document.getElementById("chat-log");
        log.innerHTML = "";
        data.messages.forEach(msg => appendMessage(msg.username, msg.message));
    } catch (err) {
        console.error("History fetch error:", err);
    }
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

function openSocket() {
    const token = getToken();
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/chat/ws/${roomId}?token=${encodeURIComponent(token)}`;

    chatSocket = new WebSocket(url);

    chatSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        appendMessage(data.username, data.message);
    };

    chatSocket.onclose = (event) => {
        if (event.code === 4001) {
            localStorage.removeItem(TOKEN_KEY);
            window.location.href = "/";
            return;
        }
        // Reconnect after 2s on unexpected close
        setTimeout(openSocket, 2000);
    };

    chatSocket.onerror = () => {
        chatSocket.close();
    };
}

// ---------------------------------------------------------------------------
// Send
// ---------------------------------------------------------------------------

function sendMessage() {
    const messageInput = document.getElementById("message");
    const message = messageInput.value.trim();

    if (!activeCharacter || !message) return;

    const messageToSend = actionModeEnabled ? `/me ${message}` : message;

    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(messageToSend);
        messageInput.value = "";
        return;
    }

    // Fallback for startup/reconnect windows where WebSocket is not yet open.
    fetch("/api/chat/send", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken()}`
        },
        body: JSON.stringify({
            room_id: roomId,
            message: messageToSend
        })
    })
        .then((res) => {
            if (!res.ok) {
                throw new Error(`HTTP send failed: ${res.status}`);
            }
            messageInput.value = "";
            return fetchHistory();
        })
        .catch((err) => {
            console.error("Send fallback error:", err);
        });
}

// ---------------------------------------------------------------------------
// Controls
// ---------------------------------------------------------------------------

function setActionMode(enabled) {
    actionModeEnabled = enabled;
    const actionButton = document.getElementById("action-toggle");
    if (!actionButton) return;
    actionButton.classList.toggle("active", enabled);
    actionButton.textContent = "*";
    actionButton.title = enabled ? "Action mode enabled (/me)" : "Toggle action (/me)";
}

function initializeChatControls() {
    const messageInput = document.getElementById("message");
    const actionButton = document.getElementById("action-toggle");

    if (actionButton) {
        actionButton.addEventListener("click", () => {
            setActionMode(!actionModeEnabled);
            if (messageInput) messageInput.focus();
        });
    }

    if (messageInput) {
        messageInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                sendMessage();
            }
        });
    }

    setActionMode(false);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

(async () => {
    await loadCharacter();
    await fetchHistory();
    openSocket();
    initializeChatControls();
})();


let audioPlayer = null;
let ambienceEnabled = false;

function playRandomTrack() {
    if (!roomAudio || roomAudio.length === 0) return;

    const track = roomAudio[Math.floor(Math.random() * roomAudio.length)];
    audioPlayer = new Audio(track);
    audioPlayer.volume = 0.5;
    audioPlayer.loop = true;
    audioPlayer.play();
}

document.getElementById("ambience-toggle").addEventListener("click", () => {
    ambienceEnabled = !ambienceEnabled;

    const btn = document.getElementById("ambience-toggle");

    if (ambienceEnabled) {
        playRandomTrack();
        btn.textContent = "♫";
    } else {
        if (audioPlayer) {
            audioPlayer.pause();
            audioPlayer = null;
        }
        btn.textContent = "♪";
    }
});
