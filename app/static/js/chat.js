// roomId is injected by room.html:
// <script>const roomId = "{{ room.id }}";</script>

const TOKEN_KEY = "rezgian_character_token";
let activeCharacter = null;
let actionModeEnabled = false;

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function authHeaders() {
    const token = getToken();
    if (!token) {
        return { "Content-Type": "application/json" };
    }

    return {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
    };
}

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

// --- Fetch and render messages ---
async function fetchMessages() {
    try {
        const res = await fetch(`/api/chat/fetch/${roomId}`);
        if (!res.ok) return;

        const data = await res.json();
        const log = document.getElementById("chat-log");

        log.innerHTML = ""; // clear before re-rendering

        data.messages.forEach(msg => {
            const line = document.createElement("div");

            const isAction = typeof msg.message === "string" && msg.message.startsWith("/me ");
            if (isAction) {
                line.classList.add("chat-action");
                const actionText = msg.message.slice(4).trim();
                line.textContent = `* ${msg.username} ${actionText}`;
            } else {
                line.textContent = `${msg.username}: ${msg.message}`;
            }

            log.appendChild(line);
        });

        log.scrollTop = log.scrollHeight;
    } catch (err) {
        console.error("Fetch error:", err);
    }
}

// --- Send a message ---
async function sendMessage() {
    const messageInput = document.getElementById("message");
    const message = messageInput.value.trim();

    if (!activeCharacter || !message) return;

    const messageToSend = actionModeEnabled ? `/me ${message}` : message;

    try {
        await fetch("/api/chat/send", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                room_id: roomId,
                message: messageToSend
            })
        });

        messageInput.value = "";
        fetchMessages();
    } catch (err) {
        console.error("Send error:", err);
    }
}

function setActionMode(enabled) {
    actionModeEnabled = enabled;
    const actionButton = document.getElementById("action-toggle");
    if (!actionButton) {
        return;
    }

    actionButton.classList.toggle("active", enabled);
    actionButton.textContent = enabled ? "*" : "action";
    actionButton.title = enabled ? "Action mode enabled (/me)" : "Toggle action (/me)";
}

function initializeChatControls() {
    const messageInput = document.getElementById("message");
    const actionButton = document.getElementById("action-toggle");

    if (actionButton) {
        actionButton.addEventListener("click", () => {
            setActionMode(!actionModeEnabled);
            if (messageInput) {
                messageInput.focus();
            }
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

// --- Poll every second ---
setInterval(fetchMessages, 1000);

// Initial load
initializeChatControls();
loadCharacter().then(fetchMessages);


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
