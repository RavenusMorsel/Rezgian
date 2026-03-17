// roomId is injected by room.html:
// <script>const roomId = "{{ room.id }}";</script>

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
            line.textContent = `${msg.username}: ${msg.message}`;
            log.appendChild(line);
        });

        log.scrollTop = log.scrollHeight;
    } catch (err) {
        console.error("Fetch error:", err);
    }
}

// --- Send a message ---
async function sendMessage() {
    const username = document.getElementById("username").value.trim();
    const message = document.getElementById("message").value.trim();

    if (!username || !message) return;

    try {
        await fetch("/api/chat/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                room_id: roomId,
                username: username,
                message: message
            })
        });

        document.getElementById("message").value = "";
        fetchMessages();
    } catch (err) {
        console.error("Send error:", err);
    }
}

// --- Poll every second ---
setInterval(fetchMessages, 1000);

// Initial load
fetchMessages();
