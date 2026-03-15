async function fetchMessages() {
    const res = await fetch("/api/chat/fetch");
    const data = await res.json();

    const log = document.getElementById("chat-log");
    log.innerHTML = "";

    data.messages.forEach(msg => {
        const line = document.createElement("div");
        line.textContent = `${msg.username}: ${msg.message}`;
        log.appendChild(line);
    });
}

async function sendMessage() {
    const username = document.getElementById("username").value;
    const message = document.getElementById("message").value;

    const formData = new FormData();
    formData.append("username", username);
    formData.append("message", message);

    await fetch("/api/chat/send", {
        method: "POST",
        body: formData
    });

    document.getElementById("message").value = "";
}

setInterval(fetchMessages, 1000);
