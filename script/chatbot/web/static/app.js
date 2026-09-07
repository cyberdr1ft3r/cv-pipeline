const form = document.getElementById("chat-form");
const input = document.getElementById("chat-text");
const messages = document.getElementById("chat-messages");

function addMessage(role, text, isHtml = false) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (isHtml) {
    bubble.innerHTML = text;
  } else {
    bubble.textContent = text;
  }

  wrapper.appendChild(bubble);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
}

function formatBotText(text) {
  if (!text) return "";
  let t = text.replace(/\r\n/g, "\n");
  t = t.replace(/^\s+$/gm, "");
  t = t.replace(/\n{3,}/g, "\n\n");
  t = t.trim();

  // Escape HTML to keep output safe
  const escapeMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  t = t.replace(/[&<>"']/g, (m) => escapeMap[m]);

  // Bold (**text**) -> <strong>
  t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\(Score:\s*([0-9]*\.?[0-9]+)\)/gi, (_m, numStr) => {
    const val = Number(numStr);
    if (Number.isNaN(val)) return _m;
    const pct = Math.round(val * 100);
    return `(Score: ${pct}%)`;
  });

  const lines = t.split("\n");
  const out = [];

  for (let i = 0; i < lines.length; i += 1) {
    let trimmed = lines[i].trim();
    if (!trimmed) {
      out.push("<div class=\"md-spacer\"></div>");
      continue;
    }

    if (/^[-]{3,}$/.test(trimmed)) {
      out.push("<div class=\"md-divider\"></div>");
      continue;
    }

    const h2 = trimmed.match(/^##\s+(.*)$/);
    if (h2) {
      out.push(`<div class="md-title">${h2[1]}</div>`);
      continue;
    }

    const h3 = trimmed.match(/^###\s+(.*)$/);
    if (h3) {
      out.push(`<div class="md-subtitle">${h3[1]}</div>`);
      continue;
    }

    const numSolo = trimmed.match(/^(\d+)\.$/);
    if (numSolo) {
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j += 1;
      const next = j < lines.length ? lines[j].trim() : "";
      if (next) {
        out.push(
          `<div class="md-num"><span class="md-num-idx">${numSolo[1]}.</span><span class="md-num-text">${next}</span></div>`
        );
        i = j;
        continue;
      }
    }

    const num = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (num) {
      out.push(
        `<div class="md-num"><span class="md-num-idx">${num[1]}.</span><span class="md-num-text">${num[2]}</span></div>`
      );
      continue;
    }

    if (trimmed === "•" || trimmed === "-") {
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j += 1;
      const next = j < lines.length ? lines[j].trim() : "";
      if (next) {
        out.push(
          `<div class="md-bullet"><span class="md-dot">•</span><span class="md-bullet-text">${next}</span></div>`
        );
        i = j;
        continue;
      }
    }

    const bullet = trimmed.match(/^[-•]\s+(.*)$/);
    if (bullet) {
      out.push(
        `<div class="md-bullet"><span class="md-dot">•</span><span class="md-bullet-text">${bullet[1]}</span></div>`
      );
      continue;
    }

    out.push(`<div class="md-line">${trimmed}</div>`);
  }

  return out.join("");
}

function addTyping() {
  const wrapper = document.createElement("div");
  wrapper.className = "message bot";
  wrapper.id = "typing-indicator";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = "En cours de reponse...";

  wrapper.appendChild(bubble);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
}

function removeTyping() {
  const typing = document.getElementById("typing-indicator");
  if (typing) typing.remove();
}

async function sendMessage(message) {
  addTyping();
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();
    removeTyping();

    if (!data.success) {
      addMessage("bot", data.error || "Erreur inconnue.");
      return;
    }

    const formatted = formatBotText(data.response);
    addMessage("bot", formatted || "Aucune reponse.", true);
  } catch (err) {
    removeTyping();
    addMessage("bot", "Impossible de contacter le serveur.");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMessage("user", text);
  input.value = "";
  sendMessage(text);
});
