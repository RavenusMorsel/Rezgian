// roomId and roomAudio are injected by room.html

const TOKEN_KEY = "rezgian_character_token";
let activeCharacter = null;
let actionModeEnabled = false;
let chatSocket = null;
let economyState = null;
let economyRouteMissing = false;

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function authHeaders() {
    return {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`
    };
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
// Economy
// ---------------------------------------------------------------------------

function renderEconomyPanel() {
    const coinDisplay = document.getElementById("coin-display");
    const inventoryEl = document.getElementById("inventory-items");
    const shopPanel = document.getElementById("shop-panel");
    const shopItemsEl = document.getElementById("shop-items");

    if (!economyState) {
        if (coinDisplay) coinDisplay.textContent = "Coins: 0";
        if (inventoryEl) inventoryEl.textContent = "Empty pack";
        if (shopItemsEl) shopItemsEl.textContent = "";
        return;
    }

    if (coinDisplay) {
        coinDisplay.textContent = `Coins: ${economyState.character.currency}`;
    }

    if (inventoryEl) {
        inventoryEl.innerHTML = "";
        if (!economyState.inventory || economyState.inventory.length === 0) {
            inventoryEl.textContent = "Empty pack";
        } else {
            economyState.inventory.forEach(item => {
                const row = document.createElement("div");
                row.className = "inventory-item";

                const meta = document.createElement("div");
                meta.className = "item-meta";
                meta.innerHTML = `<span class="item-name">${item.name}</span><span class="item-sub">x${item.quantity}</span>`;

                const sellBtn = document.createElement("button");
                sellBtn.className = "econ-btn";
                sellBtn.type = "button";
                sellBtn.textContent = `Sell +${Math.max(1, Math.floor((item.base_price || 0) / 2))}`;
                sellBtn.onclick = () => sellItem(item.item_id, 1);

                row.appendChild(meta);
                row.appendChild(sellBtn);
                inventoryEl.appendChild(row);
            });
        }
    }

    if (shopItemsEl && shopPanel) {
        shopItemsEl.innerHTML = "";
        const shop = economyState.shop || [];
        if (shop.length === 0) {
            shopPanel.hidden = true;
        } else {
            shopPanel.hidden = false;
            shop.forEach(item => {
                const row = document.createElement("div");
                row.className = "shop-item";

                const meta = document.createElement("div");
                meta.className = "item-meta";
                meta.innerHTML = `<span class="item-name">${item.name}</span><span class="item-sub">${item.price} coins</span>`;

                const buyBtn = document.createElement("button");
                buyBtn.className = "econ-btn";
                buyBtn.type = "button";
                buyBtn.textContent = "Buy";
                buyBtn.disabled = economyState.character.currency < item.price;
                buyBtn.onclick = () => buyItem(item.item_id, 1);

                row.appendChild(meta);
                row.appendChild(buyBtn);
                shopItemsEl.appendChild(row);
            });
        }
    }
}

async function fetchEconomyState() {
    if (economyRouteMissing) {
        return;
    }

    try {
        const res = await fetch(`/api/economy/state?room_id=${encodeURIComponent(roomId)}`, {
            headers: { Authorization: `Bearer ${getToken()}` }
        });

        if (res.status === 404) {
            economyRouteMissing = true;
            const panel = document.getElementById("economy-panel");
            if (panel) {
                panel.hidden = true;
            }
            console.info("Economy API not available yet. Restart/redeploy backend to enable it.");
            return;
        }

        if (!res.ok) return;
        economyState = await res.json();
        renderEconomyPanel();
    } catch (err) {
        console.error("Economy fetch error:", err);
    }
}

async function buyItem(itemId, quantity) {
    try {
        const res = await fetch("/api/economy/buy", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ room_id: roomId, item_id: itemId, quantity })
        });
        if (!res.ok) {
            const data = await res.json().catch(() => null);
            throw new Error(data?.detail || `Buy failed (${res.status})`);
        }
        await fetchEconomyState();
    } catch (err) {
        console.error("Buy error:", err);
    }
}

async function sellItem(itemId, quantity) {
    try {
        const res = await fetch("/api/economy/sell", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ item_id: itemId, quantity })
        });
        if (!res.ok) {
            const data = await res.json().catch(() => null);
            throw new Error(data?.detail || `Sell failed (${res.status})`);
        }
        await fetchEconomyState();
    } catch (err) {
        console.error("Sell error:", err);
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
        fetchEconomyState();
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
        })
        .finally(() => {
            fetchEconomyState();
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
    await fetchEconomyState();
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
