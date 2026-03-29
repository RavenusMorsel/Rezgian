// roomId and roomAudio are injected by room.html

const TOKEN_KEY = "rezgian_character_token";
let activeCharacter = null;
let actionModeEnabled = false;
let chatSocket = null;
let economyState = null;
let economyRouteMissing = false;
let combatState = null;

function setCombatPanelVisibility(isVisible) {
    const combatPanel = document.getElementById("combat-panel");
    if (!combatPanel) return;
    combatPanel.hidden = !isVisible;
}

function setCombatLog(text, isError = false) {
    const combatLog = document.getElementById("combat-log");
    const combatPanel = document.getElementById("combat-panel");
    if (!combatLog || (combatPanel && combatPanel.hidden)) return;
    combatLog.textContent = text;
    combatLog.style.color = isError ? "#f0a7a0" : "#d7be90";
}

function renderVitals(vitals) {
    const healthDisplay = document.getElementById("health-display");
    if (!healthDisplay) return;

    if (!vitals) {
        healthDisplay.textContent = "HP: 0/0";
        return;
    }

    healthDisplay.textContent = `HP: ${vitals.health}/${vitals.max_health}`;
}

function closeShopPanel() {
    const shopPanel = document.getElementById("shop-panel");
    if (shopPanel) {
        shopPanel.hidden = true;
    }
}

function openShopPanel() {
    const shopPanel = document.getElementById("shop-panel");
    const inventoryPanel = document.getElementById("inventory-panel");
    if (inventoryPanel) {
        inventoryPanel.hidden = true;
    }
    if (shopPanel) {
        shopPanel.hidden = false;
    }
}

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
    const healthDisplay = document.getElementById("health-display");
    const inventoryEl = document.getElementById("inventory-items");
    const inventoryPanel = document.getElementById("inventory-panel");
    const inventoryToggle = document.getElementById("inventory-toggle");
    const shopPanel = document.getElementById("shop-panel");
    const shopToggle = document.getElementById("shop-toggle-header");
    const shopItemsEl = document.getElementById("shop-items");

    if (!economyState) {
        if (coinDisplay) coinDisplay.textContent = "Coins: 0";
        if (healthDisplay) healthDisplay.textContent = "HP: 0/0";
        if (inventoryEl) inventoryEl.textContent = "Empty pack";
        if (shopItemsEl) shopItemsEl.textContent = "";
        if (shopToggle) shopToggle.hidden = true;
        if (shopPanel) shopPanel.hidden = true;
        if (inventoryToggle) inventoryToggle.hidden = true;
        if (inventoryPanel) inventoryPanel.hidden = true;
        return;
    }

    if (coinDisplay) {
        coinDisplay.textContent = `Coins: ${economyState.character.currency}`;
    }
    renderVitals(economyState.vitals);

    if (inventoryToggle) {
        inventoryToggle.hidden = false;
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

                const actions = document.createElement("div");
                actions.className = "item-actions";

                if (item.usable) {
                    const useBtn = document.createElement("button");
                    useBtn.className = "econ-btn";
                    useBtn.type = "button";
                    useBtn.textContent = "Use";
                    useBtn.onclick = () => useItem(item.item_id, 1);
                    actions.appendChild(useBtn);
                }

                actions.appendChild(sellBtn);

                row.appendChild(meta);
                row.appendChild(actions);
                inventoryEl.appendChild(row);
            });
        }
    }

    if (shopItemsEl && shopPanel) {
        shopItemsEl.innerHTML = "";
        const shop = economyState.shop || [];
        if (shop.length === 0) {
            if (shopToggle) {
                shopToggle.hidden = true;
            }
            shopPanel.hidden = true;
        } else {
            if (shopToggle) {
                shopToggle.hidden = false;
            }
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
            const shopToggle = document.getElementById("shop-toggle-header");
            const shopPanel = document.getElementById("shop-panel");
            const inventoryToggle = document.getElementById("inventory-toggle");
            const inventoryPanel = document.getElementById("inventory-panel");
            const coinDisplay = document.getElementById("coin-display");
            if (shopToggle) shopToggle.hidden = true;
            if (shopPanel) shopPanel.hidden = true;
            if (inventoryToggle) inventoryToggle.hidden = true;
            if (inventoryPanel) inventoryPanel.hidden = true;
            if (coinDisplay) coinDisplay.hidden = true;
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
        closeShopPanel();
        await fetchEconomyState();
    } catch (err) {
        console.error("Buy error:", err);
        setCombatLog(`Shop error: ${err.message}`, true);
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
        setCombatLog(`Sell error: ${err.message}`, true);
    }
}

async function useItem(itemId, quantity) {
    try {
        const res = await fetch("/api/economy/use", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ item_id: itemId, quantity })
        });
        if (!res.ok) {
            const data = await res.json().catch(() => null);
            throw new Error(data?.detail || `Use failed (${res.status})`);
        }
        const data = await res.json();
        setCombatLog(`Used ${quantity} ${itemId.replaceAll("_", " ")}. Healed ${data.effects.healed}.`);
        await fetchEconomyState();
        await fetchCombatState();
    } catch (err) {
        console.error("Use item error:", err);
        setCombatLog(`Use error: ${err.message}`, true);
    }
}

// ---------------------------------------------------------------------------
// Combat
// ---------------------------------------------------------------------------

function renderCombatState() {
    const enemyDisplay = document.getElementById("enemy-display");
    if (!enemyDisplay) return;

    if (!combatState || !combatState.combat_available) {
        enemyDisplay.textContent = "Safe area";
        return;
    }

    if (!combatState.encounter) {
        enemyDisplay.textContent = "No active encounter";
        return;
    }

    const e = combatState.encounter;
    enemyDisplay.textContent = `${e.enemy_name}: ${e.enemy_health}/${e.enemy_max_health} HP`;
}

async function fetchCombatState() {
    try {
        const res = await fetch(`/api/combat/state?room_id=${encodeURIComponent(roomId)}`, {
            headers: { Authorization: `Bearer ${getToken()}` }
        });
        if (!res.ok) return;
        combatState = await res.json();
        setCombatPanelVisibility(Boolean(combatState.combat_available));
        renderVitals(combatState.vitals);
        renderCombatState();
    } catch (err) {
        console.error("Combat state error:", err);
    }
}

async function engageCombat() {
    try {
        const res = await fetch("/api/combat/engage", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ room_id: roomId })
        });
        if (!res.ok) {
            const data = await res.json().catch(() => null);
            throw new Error(data?.detail || `Engage failed (${res.status})`);
        }
        combatState = await res.json();
        setCombatPanelVisibility(Boolean(combatState.combat_available));
        renderVitals(combatState.vitals);
        renderCombatState();
        if (combatState.encounter) {
            setCombatLog(`Encountered ${combatState.encounter.enemy_name}.`);
        }
    } catch (err) {
        setCombatLog(`Engage error: ${err.message}`, true);
    }
}

async function attackCombat() {
    try {
        const res = await fetch("/api/combat/attack", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ room_id: roomId })
        });
        if (!res.ok) {
            const data = await res.json().catch(() => null);
            throw new Error(data?.detail || `Attack failed (${res.status})`);
        }
        const data = await res.json();
        combatState = {
            combat_available: data.combat_available,
            vitals: data.vitals,
            encounter: data.encounter
        };
        setCombatPanelVisibility(Boolean(combatState.combat_available));
        renderVitals(data.vitals);
        renderCombatState();
        if (data.log && data.log.length > 0) {
            setCombatLog(data.log.join(" "));
        }
        await fetchEconomyState();
    } catch (err) {
        setCombatLog(`Attack error: ${err.message}`, true);
    }
}

async function fleeCombat() {
    try {
        const res = await fetch("/api/combat/flee", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ room_id: roomId })
        });
        if (!res.ok) {
            const data = await res.json().catch(() => null);
            throw new Error(data?.detail || `Flee failed (${res.status})`);
        }
        combatState = {
            combat_available: data.combat_available ?? combatState?.combat_available ?? false,
            vitals: combatState?.vitals || economyState?.vitals || null,
            encounter: null
        };
        setCombatPanelVisibility(Boolean(combatState.combat_available));
        renderCombatState();
        if (combatState.combat_available) {
            setCombatLog("You disengage and step back.");
        }
    } catch (err) {
        setCombatLog(`Flee error: ${err.message}`, true);
    }
}

function useHealingHerb() {
    useItem("healing_herb", 1);
}

// ---------------------------------------------------------------------------
// Message rendering
// ---------------------------------------------------------------------------

function appendMessage(username, message) {
    const log = document.getElementById("chat-log");
    if (!log) return;

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
        if (!log) return;
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
    if (!messageInput) return;

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
    const shopToggle = document.getElementById("shop-toggle-header");
    const shopPanel = document.getElementById("shop-panel");
    const shopClose = document.getElementById("shop-close");
    const inventoryToggle = document.getElementById("inventory-toggle");
    const inventoryPanel = document.getElementById("inventory-panel");
    const engageButton = document.getElementById("engage-btn");
    const attackButton = document.getElementById("attack-btn");
    const fleeButton = document.getElementById("flee-btn");
    const useHerbButton = document.getElementById("use-herb-btn");

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

    if (shopToggle && shopPanel) {
        shopToggle.addEventListener("click", () => {
            if (shopPanel.hidden) {
                openShopPanel();
            } else {
                closeShopPanel();
            }
        });
    }

    if (shopClose) {
        shopClose.addEventListener("click", () => {
            closeShopPanel();
        });
    }

    if (inventoryToggle && inventoryPanel) {
        inventoryToggle.addEventListener("click", () => {
            const nextHidden = !inventoryPanel.hidden;
            inventoryPanel.hidden = nextHidden;
            inventoryToggle.textContent = nextHidden ? "Pack" : "Pack -";
            if (!nextHidden) {
                closeShopPanel();
            }
        });
    }

    if (engageButton) {
        engageButton.addEventListener("click", engageCombat);
    }

    if (attackButton) {
        attackButton.addEventListener("click", attackCombat);
    }

    if (fleeButton) {
        fleeButton.addEventListener("click", fleeCombat);
    }

    if (useHerbButton) {
        useHerbButton.addEventListener("click", useHealingHerb);
    }

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeShopPanel();
        }
    });

    setActionMode(false);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

(async () => {
    await loadCharacter();
    await fetchHistory();
    await fetchEconomyState();
    await fetchCombatState();
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
    audioPlayer.play().catch(() => {
        audioPlayer = null;
    });
}

const ambienceToggle = document.getElementById("ambience-toggle");
if (ambienceToggle) {
    ambienceToggle.addEventListener("click", () => {
        ambienceEnabled = !ambienceEnabled;

        const btn = document.getElementById("ambience-toggle");
        if (!btn) return;

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
}
