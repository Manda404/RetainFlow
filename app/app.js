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

const columnLabels = {
  observation_date: "Observation date",
  customer_id: "Customer ID",
  client_id: "Customer ID",
  split_name: "Split",
  first_name: "First name",
  last_name: "Last name",
  region: "Region",
  agency_name: "Branch",
  priority_tier: "Priority tier",
  priority_score: "Priority score",
  churn_probability: "Churn probability",
  expected_saved_value: "Expected saved value",
  recommended_action_type: "Recommended action",
  recommended_channel: "Recommended channel",
  recommended_offer: "Recommended offer",
  estimated_offer_value: "Estimated offer value",
  advisor_message: "Advisor message",
  decision_rationale: "Decision rationale",
  next_best_step: "Next best step",
  human_review_status: "Review status",
  approval_decision: "Approval decision",
  approval_comment: "Approval comment",
  mlflow_run_id: "MLflow run ID",
  customer_segment: "Customer segment",
  main_product_family: "Main product family",
  title: "Title",
  document_id: "Document ID",
  source_path: "Source path",
  score: "Score",
  clients: "Customers",
  customers_to_contact: "Customers to contact",
  avg_churn_probability: "Average churn probability",
  approved_action_rate: "Approved action rate",
};

const exactValueTranslations = new Map([
  ["Remise fidelite controlee", "Controlled loyalty discount"],
  ["Appel de resolution prioritaire", "Priority resolution call"],
  ["Appel sauvegarde renouvellement", "Renewal save call"],
  ["Amenagement de paiement", "Payment plan adjustment"],
  ["Reactivation digitale accompagnee", "Assisted digital reactivation"],
  ["Controle retention proactif", "Proactive retention check"],
  ["Validation manager retention avant proposition commerciale.", "Retention manager approval before commercial proposal."],
  ["Assigner un conseiller service senior sous 24h.", "Assign a senior service advisor within 24 hours."],
  ["Planifier un appel sortant avant la prochaine echeance.", "Schedule an outbound call before the next renewal date."],
  ["Verifier eligibilite paiement fractionne.", "Check eligibility for split payment."],
  ["Declencher campagne email personnalisee.", "Trigger a personalized email campaign."],
  ["Creer une tache conseiller pour qualification.", "Create an advisor task for qualification."],
  ["risque churn eleve et valeur client significative", "high churn risk and significant customer value"],
  ["hausse de prime recente", "recent premium increase"],
  ["pression tarifaire concurrente", "competitor price pressure"],
  ["reclamations recentes", "recent complaints"],
  ["dossier service non resolu", "unresolved service case"],
  ["renouvellement proche", "upcoming renewal"],
  ["incident de paiement", "payment incident"],
  ["faible engagement digital", "low digital engagement"],
  ["Strategie Retention - Clients Sensibles Au Prix", "Retention Strategy - Price-Sensitive Customers"],
  ["Strategie Retention - Insatisfaction Service", "Retention Strategy - Service Dissatisfaction"],
  ["Strategie Retention - Incidents De Paiement", "Retention Strategy - Payment Incidents"],
  ["Strategie Retention - Renouvellement Proche", "Retention Strategy - Upcoming Renewal"],
  ["Strategie Retention - Reengagement Digital", "Retention Strategy - Digital Re-Engagement"],
  ["Strategie Retention - Sinistre Recent", "Retention Strategy - Recent Claim"],
  ["Strategie Retention - Client Haute Valeur", "Retention Strategy - High-Value Customer"],
]);

const textReplacements = [
  [/\bAgence RetainFlow\b/g, "RetainFlow Branch"],
  [/\bAgence\b/g, "Branch"],
  [/\bEquipe sinistres\b/g, "Claims team"],
  [/\bEquipe retention\b/g, "Retention team"],
  [/\bPriorite\b/g, "Priority"],
  [/\bProbabilite de churn\b/g, "Churn probability"],
  [/\bValeur sauvee attendue\b/g, "Expected saved value"],
  [/\bRaisons\b/g, "Reasons"],
  [/\bCanal recommande\b/g, "Recommended channel"],
  [/\bDossier documentaire introuvable\b/g, "Document folder not found"],
  [/\bbudget max\b/g, "max budget"],
  [/\bremise fidelite\b/gi, "loyalty discount"],
  [/\bsensibilite prix\b/gi, "price sensitivity"],
  [/\bresiliation\b/gi, "churn"],
  [/\breclamations recentes\b/gi, "recent complaints"],
  [/\brenouvellement proche\b/gi, "upcoming renewal"],
  [/\bincident de paiement\b/gi, "payment incident"],
  [/\bfaible engagement digital\b/gi, "low digital engagement"],
  [/\bvaleur annuelle estimee\b/gi, "estimated annual value"],
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
  return translateText(`${value}`);
}

function formatColumnLabel(column) {
  return columnLabels[column] || humanize(column);
}

function translateText(value) {
  let text = exactValueTranslations.get(value) || value;
  textReplacements.forEach(([pattern, replacement]) => {
    text = text.replace(pattern, replacement);
  });
  return text;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function addMessage(role, text) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.innerHTML = `
    <div class="avatar">${role === "user" ? "YOU" : "RF"}</div>
    <div class="bubble">
      <strong>${role === "user" ? "Business request" : "RetainFlow Copilot"}</strong>
      <div class="bubble-content"></div>
    </div>
  `;
  renderMessageContent(node.querySelector(".bubble-content"), text, role);
  ui.messages.appendChild(node);
  ui.messages.scrollTop = ui.messages.scrollHeight;
  return node;
}

function renderMessageContent(container, text, role) {
  const cleanText = formatValue(text);
  if (role === "user") {
    container.textContent = cleanText;
    return;
  }

  const [mainText, explanationText] = cleanText.split("Global model explanation:");
  const fragments = [];
  if (mainText?.trim()) {
    fragments.push(`<p>${escapeHtml(mainText.trim())}</p>`);
  }
  if (explanationText?.trim()) {
    fragments.push(`
      <div class="message-section">
        <span>Model explanation</span>
        ${formatDriverList(explanationText)}
      </div>
    `);
  }
  container.innerHTML = fragments.join("");
}

function formatDriverList(text) {
  const normalized = text.replace(/^Top global model drivers:\s*/i, "").trim();
  const drivers = normalized.split(";").map((item) => item.trim()).filter(Boolean);
  if (!drivers.length) return `<p>${escapeHtml(normalized)}</p>`;
  return `
    <ul class="driver-list">
      ${drivers.map((driver) => `<li>${escapeHtml(formatDriverLabel(driver))}</li>`).join("")}
    </ul>
  `;
}

function formatDriverLabel(driver) {
  return driver
    .replace(/_/g, " ")
    .replace(/\bincreases churn risk\b/g, "increases churn risk")
    .replace(/\bdecreases churn risk\b/g, "decreases churn risk")
    .replace(/(^|:\s*)([a-z])/g, (match) => match.toUpperCase());
}

function setBusy(isBusy) {
  ui.send.disabled = isBusy;
  ui.send.querySelector("span").textContent = isBusy ? "Analyzing..." : "Send";
  ui.analysisState.textContent = isBusy ? "Analysis running" : "Ready";
  ui.heroDecision.textContent = isBusy ? "Analysis" : "Ready";
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
    if (!response.ok) throw new Error("API unavailable");
    const data = await response.json();
    ui.apiDot.className = "status-dot ok";
    ui.apiText.textContent = `API ${data.status}`;
  } catch {
    ui.apiDot.className = "status-dot error";
    ui.apiText.textContent = "API not connected";
  }
}

async function sendMessage(message) {
  addMessage("user", message);
  const loading = addMessage("assistant", "Analysis running: reading the request, routing agents, and preparing results.");
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
    if (!response.ok) throw new Error(payload.detail || "API error");

    loading.remove();
    await animatePipeline(payload.metadata?.steps || [payload.agent_name]);
    const assistantMessage = addMessage("assistant", formatValue(payload.answer));
    renderInlineFigure(payload.figure, assistantMessage);
    renderPayload(payload);
  } catch (error) {
    loading.remove();
    addMessage("assistant", `Error: ${error.message}`);
    ui.analysisState.textContent = "Error";
    ui.heroDecision.textContent = "Error";
  } finally {
    setBusy(false);
  }
}

function renderPayload(payload) {
  const rows = Array.isArray(payload.data) ? payload.data : [];
  ui.activeAgent.textContent = payload.agent_name || "SupervisorAgent";
  ui.responseType.textContent = payload.response_type || "text";
  ui.rowCount.textContent = `${rows.length}`;
  ui.summary.textContent = formatValue(payload.answer || "Response received.");
  renderMetadata(payload.metadata || {});
  ui.confidenceLevel.textContent = rows.length ? "Data available" : "Text analysis";
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
  if (text.includes("email") || text.includes("mail")) return "Review draft";
  if (text.includes("visual") || text.includes("graph")) return "Read chart";
  if (text.includes("strategie") || text.includes("strategy")) return "Adapt offer";
  if (rows.length) return "Handle listed customers";
  return "Analyze response";
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
    ui.riskLevel.textContent = "No score";
    return;
  }

  ui.riskCircle.style.strokeDashoffset = circumference - score * circumference;
  ui.scoreValue.textContent = `${Math.round(score * 100)}%`;
  if (score >= 0.7) {
    ui.riskCircle.style.stroke = "#e5484d";
    ui.riskLevel.textContent = "Critical risk";
  } else if (score >= 0.45) {
    ui.riskCircle.style.stroke = "#f59e0b";
    ui.riskLevel.textContent = "Risk to monitor";
  } else {
    ui.riskCircle.style.stroke = "#16a34a";
    ui.riskLevel.textContent = "Moderate risk";
  }
}

function renderPriorityCards(rows) {
  ui.priorityList.innerHTML = "";
  ui.priorityCount.textContent = `${rows.length} customer${rows.length > 1 ? "s" : ""}`;

  if (!rows.length) {
    ui.priorityList.innerHTML = "<p>No priority loaded.</p>";
    return;
  }

  rows.slice(0, 5).forEach((row, index) => {
    const score = readScore(row);
    const customer = row.customer_id || row.client_id || `Result ${index + 1}`;
    const segment = row.customer_segment || row.segment || row.region || row.agency_name || "Customer";
    const reason =
      row.decision_rationale ||
      row.rationale ||
      row.top_driver ||
      row.recommended_offer ||
      row.next_best_step ||
      "Check the table for details.";

    const card = document.createElement("article");
    card.className = "priority-card";
    card.innerHTML = `
      <div>
        <strong>${escapeHtml(formatValue(customer))}</strong>
        <span>${escapeHtml(formatValue(segment))}</span>
      </div>
      <b>${score === null ? "N/A" : `${Math.round(score * 100)}%`}</b>
      <p>${escapeHtml(formatValue(reason))}</p>
    `;
    ui.priorityList.appendChild(card);
  });
}

function renderTable(rows) {
  ui.table.innerHTML = "";
  if (!rows.length) {
    ui.table.textContent = "No table to display.";
    return;
  }

  const columns = Object.keys(rows[0]);
  const table = document.createElement("table");
  table.innerHTML = `
    <thead><tr>${columns.map((column) => `<th>${escapeHtml(formatColumnLabel(column))}</th>`).join("")}</tr></thead>
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
    ui.plot.textContent = "No chart for this response.";
    return;
  }
  if (!window.Plotly) {
    ui.plot.textContent = "Plotly is not loaded in the browser.";
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

function renderMetadata(metadata) {
  ui.metadata.innerHTML = "";
  if (!metadata || !Object.keys(metadata).length) {
    ui.metadata.textContent = "No traces available.";
    return;
  }

  const routing = metadata.routing || {};
  const cards = [
    ["Agent route", routing.intent || metadata.agent_name || "--"],
    ["Routing mode", routing.mode ? humanize(routing.mode) : "--"],
    ["Rows", metadata.row_count ?? "--"],
    ["KPI", metadata.kpi || "--"],
  ];

  if (metadata.retrieval_status) {
    cards.push(["RAG status", humanize(metadata.retrieval_status)]);
    cards.push(["Corrected", metadata.corrected ? "Yes" : "No"]);
  }

  ui.metadata.appendChild(metadataCards(cards));

  if (routing.reason || routing.confidence !== undefined) {
    ui.metadata.appendChild(
      metadataSection(
        "LLM routing",
        `
          <p>${escapeHtml(routing.reason || "No LLM reason available.")}</p>
          <span class="metadata-chip">Confidence: ${escapeHtml(formatValue(routing.confidence ?? "--"))}</span>
        `,
      ),
    );
  }

  const query = metadata.corrected_query && metadata.corrected ? metadata.corrected_query : null;
  if (query) {
    ui.metadata.appendChild(
      metadataSection("Corrected query", `<p>${escapeHtml(query)}</p>`),
    );
  }

  const sql = metadata.sql || metadata.priority_sql || metadata.profile_sql || metadata.recommendation_sql;
  if (sql) {
    ui.metadata.appendChild(
      metadataSection("SQL query", `<pre><code>${escapeHtml(formatSql(sql))}</code></pre>`),
    );
  }

  const sourceMetadata = metadata.strategy_rag || metadata.visualization || null;
  if (sourceMetadata) {
    ui.metadata.appendChild(
      metadataSection("Additional traces", `<pre><code>${escapeHtml(JSON.stringify(sourceMetadata, null, 2))}</code></pre>`),
    );
  }
}

function metadataCards(cards) {
  const wrapper = document.createElement("div");
  wrapper.className = "metadata-grid";
  wrapper.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="metadata-card">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(formatValue(value))}</strong>
        </article>
      `,
    )
    .join("");
  return wrapper;
}

function metadataSection(title, html) {
  const section = document.createElement("section");
  section.className = "metadata-section";
  section.innerHTML = `<h4>${escapeHtml(title)}</h4>${html}`;
  return section;
}

function humanize(value) {
  return `${value ?? ""}`.replaceAll("_", " ");
}

function formatSql(sql) {
  return `${sql}`
    .replace(/\bSELECT\b/g, "\nSELECT")
    .replace(/\bFROM\b/g, "\nFROM")
    .replace(/\bWHERE\b/g, "\nWHERE")
    .replace(/\bGROUP BY\b/g, "\nGROUP BY")
    .replace(/\bORDER BY\b/g, "\nORDER BY")
    .replace(/\bLIMIT\b/g, "\nLIMIT")
    .trim();
}

function renderInlineFigure(figure, messageNode) {
  if (!figure || !messageNode || !window.Plotly) return;

  messageNode.classList.add("has-plot");
  const container = document.createElement("div");
  container.className = "inline-plot";
  messageNode.querySelector(".bubble").appendChild(container);

  const layout = {
    ...(figure.layout || {}),
    autosize: true,
    height: Math.max(380, Number(figure.layout?.height || 380)),
    paper_bgcolor: "rgba(255,255,255,0)",
    plot_bgcolor: "rgba(255,255,255,0)",
    font: { family: "Inter, system-ui, sans-serif", color: "#172033" },
    margin: { l: 110, r: 28, t: 58, b: 46, ...(figure.layout?.margin || {}) },
  };

  Plotly.newPlot(container, figure.data || [], layout, {
    responsive: true,
    displayModeBar: false,
  });
  ui.messages.scrollTop = ui.messages.scrollHeight;
}

function renderEmail(payload) {
  if (payload.response_type !== "email_draft" || !payload.data) return;
  ui.summary.innerHTML = `
    <div class="email-draft">
      <strong>${escapeHtml(formatValue(payload.data.subject || "Email draft"))}</strong>
      <span>Channel: ${escapeHtml(formatValue(payload.data.channel || "EMAIL"))}</span>
      <pre>${escapeHtml(formatValue(payload.data.body || ""))}</pre>
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
    "Hello, I am RetainFlow Copilot. I can prioritize at-risk customers, explain churn factors, search marketing strategy, and create visuals.",
  );
  ui.summary.textContent = "No analysis started.";
  ui.priorityList.innerHTML = "<p>No priority loaded.</p>";
  ui.priorityCount.textContent = "0 customers";
  ui.responseType.textContent = "--";
  ui.rowCount.textContent = "0";
  ui.nextAction.textContent = "To define";
  ui.confidenceLevel.textContent = "--";
  ui.metadata.textContent = "Waiting.";
  renderRisk([]);
  setPipeline([]);
});

addMessage(
  "assistant",
  "Hello, I am RetainFlow Copilot. I can prioritize at-risk customers, explain churn factors, search marketing strategy, and create visuals.",
);
renderRisk([]);
setPipeline([]);
checkHealth();
