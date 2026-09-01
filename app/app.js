const API_URL = window.RETAINFLOW_API_BASE_URL || "http://127.0.0.1:8000";

const $ = (selector) => document.querySelector(selector);

const ui = {
  messages: $("#messages"),
  form: $("#chatForm"),
  input: $("#userInput"),
  limit: $("#limitInput"),
  send: $("#sendBtn"),
  clear: $("#clearBtn"),
  apiDot: $("#apiStatusDot"),
  apiText: $("#apiStatusText"),
  heroDecision: $("#heroDecision"),
  pipeline: $("#pipeline"),
  activeAgent: $("#activeAgent"),
  analysisState: $("#analysisState"),
  responseType: $("#responseType"),
  rowCount: $("#rowCount"),
  nextAction: $("#nextAction"),
  confidenceLevel: $("#confidenceLevel"),
  summary: $("#summaryBox"),
  priorityCount: $("#priorityCount"),
  priorityList: $("#priorityList"),
  riskCircle: $("#riskCircle"),
  scoreValue: $("#scoreValue"),
  riskLevel: $("#riskLevel"),
  table: $("#tableOutput"),
  plot: $("#plotOutput"),
  metadata: $("#metadataOutput"),
};

const scoreColumns = [
  "churn_probability",
  "prediction_probability",
  "churn_score",
  "risk_score",
  "probability",
];

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isInteger(value) ? `${value}` : value.toFixed(4);
  return `${value}`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function addMessage(role, text) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.innerHTML = `
    <div class="avatar">${role === "user" ? "VOUS" : "RF"}</div>
    <div class="bubble">
      <strong>${role === "user" ? "Demande métier" : "RetainFlow Copilot"}</strong>
      <p></p>
    </div>
  `;
  node.querySelector("p").textContent = text;
  ui.messages.appendChild(node);
  ui.messages.scrollTop = ui.messages.scrollHeight;
  return node;
}

function setBusy(isBusy) {
  ui.send.disabled = isBusy;
  ui.send.querySelector("span").textContent = isBusy ? "Analyse..." : "Envoyer";
  ui.analysisState.textContent = isBusy ? "Analyse en cours" : "Prêt";
  ui.heroDecision.textContent = isBusy ? "Analyse" : "Prête";
}

function setPipeline(steps = []) {
  const active = new Set(["SupervisorAgent", ...steps]);
  ui.pipeline.querySelectorAll(".pipeline-step").forEach((step) => {
    step.classList.toggle("active", active.has(step.dataset.step));
  });
}

async function animatePipeline(expectedSteps = []) {
  const steps = ["SupervisorAgent", ...expectedSteps];
  setPipeline([]);
  for (const step of steps) {
    setPipeline([step]);
    await sleep(160);
  }
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_URL}/health`);
    if (!response.ok) throw new Error("API indisponible");
    const data = await response.json();
    ui.apiDot.className = "status-dot ok";
    ui.apiText.textContent = `API ${data.status}`;
  } catch {
    ui.apiDot.className = "status-dot error";
    ui.apiText.textContent = "API non connectée";
  }
}

async function sendMessage(message) {
  addMessage("user", message);
  const loading = addMessage("assistant", "Analyse en cours : lecture de la demande, routage agent et préparation des résultats.");
  setBusy(true);
  setPipeline(["SQLAgent"]);

  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        limit: Number(ui.limit.value || 5),
      }),
    });

    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Erreur API");

    loading.remove();
    await animatePipeline(payload.metadata?.steps || [payload.agent_name]);
    addMessage("assistant", payload.answer);
    renderPayload(payload);
  } catch (error) {
    loading.remove();
    addMessage("assistant", `Erreur : ${error.message}`);
    ui.analysisState.textContent = "Erreur";
    ui.heroDecision.textContent = "Erreur";
  } finally {
    setBusy(false);
  }
}

function renderPayload(payload) {
  const rows = Array.isArray(payload.data) ? payload.data : [];
  ui.activeAgent.textContent = payload.agent_name || "SupervisorAgent";
  ui.responseType.textContent = payload.response_type || "text";
  ui.rowCount.textContent = `${rows.length}`;
  ui.summary.textContent = payload.answer || "Réponse reçue.";
  ui.metadata.textContent = JSON.stringify(payload.metadata || {}, null, 2);
  ui.confidenceLevel.textContent = rows.length ? "Données disponibles" : "Analyse textuelle";
  ui.nextAction.textContent = inferNextAction(payload, rows);

  setPipeline(payload.metadata?.steps || [payload.agent_name]);
  renderRisk(rows);
  renderPriorityCards(rows);
  renderTable(rows);
  renderFigure(payload.figure);
  renderEmail(payload);
}

function inferNextAction(payload, rows) {
  const first = rows[0] || {};
  const key = ["next_best_step", "recommended_offer", "recommended_action", "action"].find(
    (item) => first[item],
  );
  if (key) return formatValue(first[key]);

  const text = `${payload.answer || ""} ${JSON.stringify(payload.metadata || {})}`.toLowerCase();
  if (text.includes("email") || text.includes("mail")) return "Valider le brouillon";
  if (text.includes("visual") || text.includes("graph")) return "Lire le graphique";
  if (text.includes("strategie") || text.includes("stratégie")) return "Adapter l'offre";
  if (rows.length) return "Traiter les clients listés";
  return "Analyser la réponse";
}

function readScore(row) {
  const key = scoreColumns.find((column) => Number.isFinite(Number(row[column])));
  return key ? Math.max(0, Math.min(1, Number(row[key]))) : null;
}

function renderRisk(rows) {
  const scoredRow = rows.find((row) => readScore(row) !== null);
  const score = scoredRow ? readScore(scoredRow) : null;
  const circumference = 314;

  if (score === null) {
    ui.riskCircle.style.strokeDashoffset = circumference;
    ui.scoreValue.textContent = "--";
    ui.riskLevel.textContent = "Aucun score";
    return;
  }

  ui.riskCircle.style.strokeDashoffset = circumference - score * circumference;
  ui.scoreValue.textContent = `${Math.round(score * 100)}%`;
  if (score >= 0.7) {
    ui.riskCircle.style.stroke = "#e5484d";
    ui.riskLevel.textContent = "Risque critique";
  } else if (score >= 0.45) {
    ui.riskCircle.style.stroke = "#f59e0b";
    ui.riskLevel.textContent = "Risque à surveiller";
  } else {
    ui.riskCircle.style.stroke = "#16a34a";
    ui.riskLevel.textContent = "Risque modéré";
  }
}

function renderPriorityCards(rows) {
  ui.priorityList.innerHTML = "";
  ui.priorityCount.textContent = `${rows.length} client${rows.length > 1 ? "s" : ""}`;

  if (!rows.length) {
    ui.priorityList.innerHTML = "<p>Aucune priorité chargée.</p>";
    return;
  }

  rows.slice(0, 5).forEach((row, index) => {
    const score = readScore(row);
    const customer = row.customer_id || row.client_id || `Résultat ${index + 1}`;
    const segment = row.customer_segment || row.segment || row.region || row.agency_name || "Client";
    const reason =
      row.decision_rationale ||
      row.rationale ||
      row.top_driver ||
      row.recommended_offer ||
      row.next_best_step ||
      "Consulter la table pour les détails.";

    const card = document.createElement("article");
    card.className = "priority-card";
    card.innerHTML = `
      <div>
        <strong>${escapeHtml(customer)}</strong>
        <span>${escapeHtml(segment)}</span>
      </div>
      <b>${score === null ? "N/A" : `${Math.round(score * 100)}%`}</b>
      <p>${escapeHtml(reason)}</p>
    `;
    ui.priorityList.appendChild(card);
  });
}

function renderTable(rows) {
  ui.table.innerHTML = "";
  if (!rows.length) {
    ui.table.textContent = "Aucune table à afficher.";
    return;
  }

  const columns = Object.keys(rows[0]);
  const table = document.createElement("table");
  table.innerHTML = `
    <thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead>
    <tbody></tbody>
  `;
  const body = table.querySelector("tbody");
  rows.slice(0, 80).forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = columns
      .map((column) => `<td>${escapeHtml(formatValue(row[column]))}</td>`)
      .join("");
    body.appendChild(tr);
  });
  ui.table.appendChild(table);
}

function renderFigure(figure) {
  ui.plot.innerHTML = "";
  if (!figure) {
    ui.plot.textContent = "Aucun graphique pour cette réponse.";
    return;
  }
  if (!window.Plotly) {
    ui.plot.textContent = "Plotly n'est pas chargé dans le navigateur.";
    return;
  }
  const layout = {
    ...(figure.layout || {}),
    paper_bgcolor: "rgba(255,255,255,0)",
    plot_bgcolor: "rgba(255,255,255,0)",
    font: { family: "Inter, system-ui, sans-serif", color: "#172033" },
    margin: { l: 48, r: 24, t: 54, b: 46, ...(figure.layout?.margin || {}) },
  };
  Plotly.newPlot(ui.plot, figure.data || [], layout, { responsive: true, displayModeBar: false });
}

function renderEmail(payload) {
  if (payload.response_type !== "email_draft" || !payload.data) return;
  ui.summary.innerHTML = `
    <div class="email-draft">
      <strong>${escapeHtml(payload.data.subject || "Brouillon email")}</strong>
      <span>Canal : ${escapeHtml(payload.data.channel || "EMAIL")}</span>
      <pre>${escapeHtml(payload.data.body || "")}</pre>
    </div>
  `;
}

function activateTab(tabId) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === tabId);
  });
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

document.body.addEventListener("click", (event) => {
  const button = event.target.closest("[data-message]");
  if (!button) return;
  ui.input.value = button.dataset.message;
  sendMessage(button.dataset.message);
});

ui.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = ui.input.value.trim();
  if (!message) return;
  ui.input.value = "";
  sendMessage(message);
});

ui.clear.addEventListener("click", () => {
  ui.messages.innerHTML = "";
  addMessage(
    "assistant",
    "Bonjour, je suis RetainFlow Copilot. Je peux prioriser les clients à risque, expliquer les facteurs de churn, rechercher une stratégie marketing et produire des visuels.",
  );
  ui.summary.textContent = "Aucune analyse lancée.";
  ui.priorityList.innerHTML = "<p>Aucune priorité chargée.</p>";
  ui.priorityCount.textContent = "0 client";
  ui.responseType.textContent = "--";
  ui.rowCount.textContent = "0";
  ui.nextAction.textContent = "À définir";
  ui.confidenceLevel.textContent = "--";
  ui.metadata.textContent = "En attente.";
  renderRisk([]);
  setPipeline([]);
});

addMessage(
  "assistant",
  "Bonjour, je suis RetainFlow Copilot. Je peux prioriser les clients à risque, expliquer les facteurs de churn, rechercher une stratégie marketing et produire des visuels.",
);
renderRisk([]);
setPipeline([]);
checkHealth();
