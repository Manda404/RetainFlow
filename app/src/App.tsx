import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronRight,
  Circle,
  FileText,
  Loader2,
  Mail,
  MessageSquarePlus,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
} from "lucide-react";

import { API_BASE, chat, customerProfile, health, rowsFromResponse, type ActivityItem, type ChatResponse, type RetainFlowRow } from "./api";
import { sampleCustomers } from "./sample-data";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { cn, formatMoney, formatPercent } from "./lib/utils";

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  payload?: ChatResponse;
};

const starterPrompts = [
  "Donne-moi les 10 clients les plus susceptibles de churn.",
  "Pourquoi CUST_000123 est-il a risque ?",
  "Quels leviers de retention utiliser pour les clients sensibles au prix ?",
  "Redige-moi un email pour ce client.",
];

const recentAnalyses = [
  "Clients a risque eleve",
  "Strategies prix",
  "Explication CUST_000123",
];

function numberValue(row: RetainFlowRow | undefined, keys: string[]) {
  if (!row) return null;
  for (const key of keys) {
    const value = Number(row[key]);
    if (Number.isFinite(value)) return value;
  }
  return null;
}

function textValue(row: RetainFlowRow | undefined, keys: string[], fallback = "--") {
  if (!row) return fallback;
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && String(value).trim()) return String(value);
  }
  return fallback;
}

function rowId(row: RetainFlowRow | undefined) {
  return textValue(row, ["customer_id", "client_id"]);
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function arrayValue(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(objectValue(item))) : [];
}

function riskLabel(score: number | null) {
  if (score === null) return "Non estime";
  if (score >= 0.75) return "Risque eleve";
  if (score >= 0.5) return "Risque moyen";
  return "Risque faible";
}

function riskClass(score: number | null) {
  if (score === null) return "bg-slate-100 text-slate-600 ring-slate-200";
  if (score >= 0.75) return "bg-red-50 text-red-700 ring-red-200";
  if (score >= 0.5) return "bg-amber-50 text-amber-700 ring-amber-200";
  return "bg-emerald-50 text-emerald-700 ring-emerald-200";
}

function answerTitle(payload: ChatResponse | undefined) {
  if (!payload) return "Retention Copilot";
  if (payload.business_type === "customer_not_found") return "Client introuvable";
  if (payload.response_type === "email_draft") return "Email pret a relire";
  if (payload.business_type === "risk_explanation" || payload.business_type === "customer_profile") return "Analyse du risque client";
  if (payload.business_type === "retention_strategy") return "Strategie de retention";
  if (payload.business_type === "data_count") return "Volume de donnees client";
  if (payload.business_type === "data_query") return "Recherche client";
  if (payload.business_type === "data_table" || payload.business_type === "kpi") return "Resultat data";
  if (rowsFromResponse(payload).length) return "Clients prioritaires identifies";
  if (payload.metadata?.strategy_rag) return "Strategie de retention recommandee";
  return "Analyse RetainFlow";
}

export default function App() {
  const [apiState, setApiState] = useState<"checking" | "ok" | "offline">("checking");
  const [customers, setCustomers] = useState<RetainFlowRow[]>(sampleCustomers);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [profileResponse, setProfileResponse] = useState<ChatResponse | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Bonjour. Pose une question metier : clients a risque, explication d'un client, strategie de retention ou email a envoyer.",
    },
  ]);
  const [selectedResponseId, setSelectedResponseId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);

  useEffect(() => {
    health()
      .then(() => setApiState("ok"))
      .catch(() => setApiState("offline"));
  }, []);

  const selectedCustomer = useMemo(() => {
    if (!selectedId) return undefined;
    const profileRow = rowsFromResponse(profileResponse)[0];
    return profileRow || customers.find((customer) => rowId(customer) === selectedId);
  }, [customers, profileResponse, selectedId]);

  async function runPrompt(prompt: string) {
    if (!prompt.trim() || isThinking) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text: prompt,
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setIsThinking(true);

    try {
      const payload = await chat(prompt, 10);
      const rows = rowsFromResponse(payload);
      if (rows.length) {
        setCustomers(rows);
        const firstId = rowId(rows[0]);
        if (firstId !== "--" && ["customer_profile", "risk_explanation", "email_draft"].includes(payload.business_type)) {
          setSelectedId(firstId);
        }
      }
      const assistantId = crypto.randomUUID();
      setMessages((current) => [
        ...current,
        {
          id: assistantId,
          role: "assistant",
          text: payload.answer,
          payload,
        },
      ]);
      setSelectedResponseId(assistantId);
    } catch (error) {
      const assistantId = crypto.randomUUID();
      setMessages((current) => [
        ...current,
        {
          id: assistantId,
          role: "assistant",
          text: error instanceof Error ? error.message : "L'analyse n'a pas pu etre realisee.",
          payload: {
            agent_name: "RetainFlow",
            answer: error instanceof Error ? error.message : "L'analyse n'a pas pu etre realisee.",
            response_type: "text",
            business_type: "text",
            data: null,
            figure: null,
            metadata: {},
          },
        },
      ]);
      setSelectedResponseId(assistantId);
    } finally {
      setIsThinking(false);
    }
  }

  async function selectCustomer(id: string) {
    setSelectedId(id);
    setProfileResponse(null);
    try {
      setProfileResponse(await customerProfile(id));
    } catch {
      setProfileResponse(null);
    }
  }

  const selectedResponse = useMemo(() => {
    const assistantMessages = messages.filter((message) => message.role === "assistant" && message.payload);
    return (
      assistantMessages.find((message) => message.id === selectedResponseId)?.payload ||
      assistantMessages.at(-1)?.payload ||
      null
    );
  }, [messages, selectedResponseId]);

  return (
    <div className="grid h-screen grid-cols-1 bg-background text-foreground xl:grid-cols-[240px_minmax(0,1fr)_360px]">
      <aside className="hidden border-r bg-white xl:flex xl:flex-col">
        <div className="border-b p-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-md bg-primary text-sm font-black text-white">RF</div>
            <div>
              <h1 className="text-lg font-bold">Retention Copilot</h1>
              <p className="text-xs text-muted-foreground">Assistant metier agentique</p>
            </div>
          </div>
        </div>
        <div className="grid gap-5 p-4">
          <Button
            onClick={() => {
              setMessages([]);
              setSelectedResponseId(null);
              setSelectedId(null);
              setProfileResponse(null);
            }}
            variant="outline"
            className="justify-start"
          >
            <MessageSquarePlus className="h-4 w-4" />
            Nouvelle analyse
          </Button>
          <section>
            <p className="mb-2 text-xs font-bold uppercase text-muted-foreground">Analyses recentes</p>
            <div className="grid gap-1">
              {recentAnalyses.map((item) => (
                <button key={item} className="flex items-center justify-between rounded-md px-2 py-2 text-left text-sm text-slate-600 hover:bg-slate-50">
                  {item}
                  <ChevronRight className="h-4 w-4" />
                </button>
              ))}
            </div>
          </section>
        </div>
        <div className="mt-auto border-t p-4">
          <div className="rounded-md border bg-slate-50 p-3 text-xs text-slate-600">
            <div className="mb-2 flex items-center gap-2 font-semibold text-slate-900">
              <span className={cn("h-2 w-2 rounded-full", apiState === "ok" ? "bg-emerald-500" : apiState === "offline" ? "bg-red-500" : "bg-amber-500")} />
              {apiState === "ok" ? "System Ready" : apiState === "offline" ? "Mode demo" : "Connexion"}
            </div>
            <span className="break-all">{API_BASE}</span>
          </div>
        </div>
      </aside>

      <main className="flex min-h-0 flex-col">
        <header className="border-b bg-white px-5 py-5">
          <div className="grid items-center gap-3 md:grid-cols-[1fr_auto_1fr]">
            <div />
            <div className="text-center">
              <h2 className="text-2xl font-black tracking-normal text-slate-950 md:text-3xl">
                Agentic Customer Retention Platform
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Priorisez les clients a risque, comprenez les signaux et declenchez les bonnes actions de retention.
              </p>
            </div>
            <div className="justify-self-end flex items-center gap-2 rounded-md border bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
              <span className={cn("h-2 w-2 rounded-full", apiState === "ok" ? "bg-emerald-500" : "bg-red-500")} />
              {apiState === "ok" ? "API active" : "Demo"}
            </div>
          </div>
        </header>

        <section className="min-h-0 flex-1 overflow-auto px-5 py-6">
          <div className="mx-auto grid max-w-5xl gap-5">
            <AnimatePresence initial={false}>
              {messages.map((message) => (
                <MessageBlock
                  key={message.id}
                  message={message}
                  selectedId={selectedId}
                  selectedResponseId={selectedResponseId}
                  onSelectCustomer={selectCustomer}
                  onSelectResponse={setSelectedResponseId}
                  onPrompt={runPrompt}
                />
              ))}
              {isThinking && <ThinkingBlock key="thinking" />}
            </AnimatePresence>
          </div>
        </section>

        <footer className="border-t bg-white p-4">
          <div className="mx-auto grid max-w-5xl gap-3">
            <div className="flex flex-wrap gap-2">
              {starterPrompts.slice(0, 3).map((prompt) => (
                <Button key={prompt} variant="secondary" size="sm" onClick={() => runPrompt(prompt)}>
                  <Sparkles className="h-3.5 w-3.5" />
                  {prompt.split(" ").slice(0, 5).join(" ")}
                </Button>
              ))}
            </div>
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                runPrompt(input);
              }}
            >
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                className="min-h-12 flex-1 rounded-md border bg-white px-4 text-sm outline-none focus:ring-2 focus:ring-ring"
                placeholder="Exemple : Pourquoi ce client est-il a risque ?"
              />
              <Button type="submit" disabled={isThinking || !input.trim()} className="h-12 px-5">
                {isThinking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Envoyer
              </Button>
            </form>
          </div>
        </footer>
      </main>

      <AgentActivityPanel response={selectedResponse} customer={selectedCustomer} selectedId={selectedId} onPrompt={runPrompt} />
    </div>
  );
}

function MessageBlock({
  message,
  selectedId,
  selectedResponseId,
  onSelectCustomer,
  onSelectResponse,
  onPrompt,
}: {
  message: Message;
  selectedId: string | null;
  selectedResponseId: string | null;
  onSelectCustomer: (id: string) => void;
  onSelectResponse: (id: string) => void;
  onPrompt: (prompt: string) => void;
}) {
  const rows = rowsFromResponse(message.payload || null);
  const isAssistant = message.role === "assistant";

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      onClick={() => {
        if (isAssistant && message.payload) onSelectResponse(message.id);
      }}
      className={cn("flex gap-3", message.role === "user" && "justify-end", isAssistant && "cursor-pointer")}
    >
      {isAssistant && (
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary text-white">
          <Bot className="h-4 w-4" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[820px] rounded-lg border bg-white p-4 shadow-sm",
          message.role === "user" && "border-primary bg-primary text-white",
          isAssistant && selectedResponseId === message.id && "ring-2 ring-primary/30",
        )}
      >
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className={cn("text-sm font-bold", message.role === "user" && "text-white")}>{message.role === "user" ? "Vous" : answerTitle(message.payload)}</p>
          {message.payload?.agent_name && <span className="text-xs text-muted-foreground">{message.payload.agent_name}</span>}
        </div>
        {isAssistant ? (
                  <StructuredAnswer payload={message.payload} rows={rows} selectedId={selectedId} onSelectCustomer={onSelectCustomer} onPrompt={onPrompt} fallback={message.text} />
        ) : (
          <p className="text-sm leading-6">{message.text}</p>
        )}
      </div>
      {!isAssistant && (
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-slate-200 text-slate-700">
          <UserRound className="h-4 w-4" />
        </div>
      )}
    </motion.article>
  );
}

function StructuredAnswer({
  payload,
  rows,
  selectedId,
  onSelectCustomer,
  onPrompt,
  fallback,
}: {
  payload?: ChatResponse;
  rows: RetainFlowRow[];
  selectedId: string | null;
  onSelectCustomer: (id: string) => void;
  onPrompt: (prompt: string) => void;
  fallback: string;
}) {
  if (payload?.business_type === "retention_strategy") {
    return <StrategyResponse payload={payload} rows={rows} fallback={fallback} />;
  }

  if (payload?.business_type === "risk_explanation" || payload?.business_type === "customer_profile") {
    return <CustomerRiskResponse payload={payload} rows={rows} selectedId={selectedId} onPrompt={onPrompt} fallback={fallback} />;
  }

  if (payload?.business_type === "data_count") {
    return <DataCountResponse payload={payload} rows={rows} fallback={fallback} />;
  }

  if (payload?.business_type === "data_query" || payload?.business_type === "data_table" || payload?.business_type === "kpi") {
    return <GenericTableResponse payload={payload} rows={rows} fallback={fallback} />;
  }

  if (rows.length) {
    return (
      <div className="grid gap-4">
        <p className="text-sm leading-6 text-slate-700">{payload?.answer || fallback}</p>
        <div className="overflow-hidden rounded-md border">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3 text-left">Client</th>
                <th className="p-3 text-left">Risque</th>
                <th className="p-3 text-left">Principal signal</th>
                <th className="p-3 text-left">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 10).map((row) => {
                const id = rowId(row);
                const score = numberValue(row, ["churn_probability", "prediction_probability", "risk_score"]);
                return (
                  <tr key={id} className={cn("border-t", selectedId && id === selectedId && "bg-teal-50/70")}>
                    <td className="p-3">
                      <button className="font-semibold text-slate-950" onClick={() => onSelectCustomer(id)}>
                        {id}
                      </button>
                      <p className="text-xs text-muted-foreground">{textValue(row, ["customer_segment", "region"])}</p>
                    </td>
                    <td className="p-3">
                      <span className={cn("rounded-md px-2 py-1 text-xs font-bold ring-1", riskClass(score))}>{formatPercent(score)}</span>
                    </td>
                    <td className="max-w-[220px] p-3 text-slate-600">{textValue(row, ["decision_rationale", "action_reason"], "Risque churn eleve")}</td>
                    <td className="max-w-[220px] p-3 text-slate-700">{textValue(row, ["next_best_step", "recommended_action_type", "recommended_offer"])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {selectedId && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => onPrompt(`Pourquoi ${selectedId} est-il a risque ?`)}>
              Expliquer le client
            </Button>
            <Button variant="outline" size="sm" onClick={() => onPrompt(`Quelle strategie recommandes-tu pour ${selectedId} ?`)}>
              Creer une strategie
            </Button>
            <Button size="sm" onClick={() => onPrompt(`Redige-moi un email de retention pour ${selectedId}.`)}>
              <Mail className="h-4 w-4" />
              Rediger un email
            </Button>
          </div>
        )}
        <Trace activity={payload?.metadata.activity || []} />
      </div>
    );
  }

  if (payload?.response_type === "email_draft" && payload.data && !Array.isArray(payload.data)) {
    return (
      <div className="grid gap-3">
        <div className="rounded-md border bg-slate-50 p-4">
          <p className="mb-1 text-xs font-bold uppercase text-muted-foreground">Objet</p>
          <p className="font-semibold">{textValue(payload.data, ["subject"], "Email de retention")}</p>
        </div>
        <div className="rounded-md border bg-white p-4">
          <p className="mb-2 text-xs font-bold uppercase text-muted-foreground">Message</p>
          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{textValue(payload.data, ["body"], payload.answer)}</p>
        </div>
        <Trace activity={payload.metadata.activity || []} />
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="rounded-md border bg-slate-50 p-4">
        <p className="mb-2 text-xs font-bold uppercase text-primary">Reponse metier</p>
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{payload?.answer || fallback}</p>
      </div>
      {selectedId && (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => onPrompt(`Quelle strategie recommandes-tu pour ${selectedId} ?`)}>
            Strategie
          </Button>
          <Button size="sm" onClick={() => onPrompt(`Redige-moi un email de retention pour ${selectedId}.`)}>
            <Mail className="h-4 w-4" />
            Email
          </Button>
        </div>
      )}
      <Trace activity={payload?.metadata.activity || []} />
    </div>
  );
}

function DataCountResponse({
  payload,
  rows,
  fallback,
}: {
  payload: ChatResponse;
  rows: RetainFlowRow[];
  fallback: string;
}) {
  const total = numberValue(rows[0], ["total_customers", "count", "total"]);

  return (
    <div className="grid gap-4">
      <div className="rounded-md border bg-slate-50 p-4">
        <p className="mb-2 text-xs font-bold uppercase text-primary">Comptage base client</p>
        <p className="text-sm leading-6 text-slate-700">{payload.answer || fallback}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Metric label="Clients uniques" value={total === null ? "--" : new Intl.NumberFormat("fr-FR").format(total)} />
        <Metric label="Source" value="dim_customer" />
      </div>
      <Trace activity={payload.metadata.activity || []} />
    </div>
  );
}

function GenericTableResponse({
  payload,
  rows,
  fallback,
}: {
  payload: ChatResponse;
  rows: RetainFlowRow[];
  fallback: string;
}) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 8);

  return (
    <div className="grid gap-4">
      <div className="rounded-md border bg-slate-50 p-4">
        <p className="mb-2 text-xs font-bold uppercase text-primary">Resultat de recherche</p>
        <p className="text-sm leading-6 text-slate-700">{payload.answer || fallback}</p>
      </div>
      {rows.length > 0 && (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-muted-foreground">
              <tr>
                {columns.map((column) => (
                  <th key={column} className="p-3 text-left">{column.replaceAll("_", " ")}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 10).map((row, index) => (
                <tr key={String(row.customer_id ?? index)} className="border-t">
                  {columns.map((column) => (
                    <td key={column} className="max-w-[220px] p-3 text-slate-700">{String(row[column] ?? "--")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Trace activity={payload.metadata.activity || []} />
    </div>
  );
}

function CustomerRiskResponse({
  payload,
  rows,
  selectedId,
  onPrompt,
  fallback,
}: {
  payload: ChatResponse;
  rows: RetainFlowRow[];
  selectedId: string | null;
  onPrompt: (prompt: string) => void;
  fallback: string;
}) {
  const customer = rows[0];
  const customerId = rowId(customer);
  const score = numberValue(customer, ["churn_probability", "prediction_probability", "risk_score"]);
  const action = textValue(customer, ["next_best_step", "recommended_action_type", "recommended_offer"], "Action conseiller a definir.");
  const signal = textValue(customer, ["action_reason", "decision_rationale"], "Signaux de risque a analyser.");
  const displayId = customerId !== "--" ? customerId : selectedId;
  const reasoning = objectValue(payload.metadata.reasoning);
  const prediction = objectValue(reasoning?.prediction);
  const signals = arrayValue(reasoning?.signals);
  const shapDrivers = arrayValue(reasoning?.shap_drivers);
  const llmReasoning = objectValue(payload.metadata.llm_reasoning);
  const llmUsed = llmReasoning?.used === true;
  const probabilityLabel = String(prediction?.probability_label || formatPercent(score));
  const riskBandLabel = String(prediction?.risk_band_label || riskLabel(score));

  return (
    <div className="grid gap-4">
      <div className="rounded-md border bg-slate-50 p-4">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase text-primary">Diagnostic client</p>
            <p className="mt-1 text-lg font-bold text-slate-950">{displayId || "Client selectionne"}</p>
            <p className="text-sm text-muted-foreground">
              {textValue(customer, ["first_name"])} {textValue(customer, ["last_name"], "")} · {textValue(customer, ["customer_segment"])} · {textValue(customer, ["region", "agency_name"])}
            </p>
          </div>
          <span className={cn("rounded-md px-2 py-1 text-xs font-bold ring-1", riskClass(score))}>{probabilityLabel}</span>
        </div>
        <p className="text-sm leading-6 text-slate-700">{payload.answer || fallback}</p>
        <p className="mt-3 text-xs text-muted-foreground">
          {llmUsed ? "Explication finale redigee par le LLM a partir des preuves controlees." : "Explication finale produite par le raisonnement deterministe controle."}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Metric label="Probabilite churn" value={probabilityLabel} />
        <Metric label="Niveau de risque" value={riskBandLabel} />
        <Metric label="Priorite" value={textValue(customer, ["priority_tier", "churn_risk_band"], "Non classee")} />
        <Metric label="Prime annuelle" value={formatMoney(numberValue(customer, ["total_annual_premium", "annual_premium_amount"]))} />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-md border bg-white p-4">
          <p className="mb-2 text-xs font-bold uppercase text-muted-foreground">Signal principal</p>
          <p className="text-sm leading-6 text-slate-700">{signal}</p>
        </div>
        <div className="rounded-md border bg-white p-4">
          <p className="mb-2 text-xs font-bold uppercase text-muted-foreground">Action recommandee</p>
          <p className="text-sm leading-6 text-slate-700">{action}</p>
        </div>
      </div>

      {signals.length > 0 && (
        <div className="rounded-md border bg-white p-4">
          <p className="mb-3 text-xs font-bold uppercase text-muted-foreground">Signaux client observes</p>
          <div className="grid gap-2">
            {signals.slice(0, 5).map((item) => (
              <div key={String(item.field || item.label)} className="flex items-center justify-between gap-3 rounded-md bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium text-slate-800">{String(item.label || item.field)}</span>
                <span className="text-xs text-muted-foreground">{String(item.value ?? "")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {shapDrivers.length > 0 && (
        <div className="rounded-md border bg-white p-4">
          <p className="mb-1 text-xs font-bold uppercase text-muted-foreground">Contexte SHAP utilise</p>
          <p className="mb-3 text-xs leading-5 text-slate-500">
            Ces drivers expliquent le comportement global du modele; ils aident a interpreter la prediction du client.
          </p>
          <div className="grid gap-2">
            {shapDrivers.slice(0, 5).map((driver) => (
              <div key={String(driver.feature)} className="flex items-center justify-between gap-3 rounded-md bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium text-slate-800">{String(driver.label || driver.feature)}</span>
                <span className="text-xs text-muted-foreground">
                  {String(driver.impact_direction || "impact modele")} · {String(driver.importance_pct ?? "--")}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {displayId && (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => onPrompt(`Quelle strategie recommandes-tu pour ${displayId} ?`)}>
            Strategie
          </Button>
          <Button size="sm" onClick={() => onPrompt(`Redige-moi un email de retention pour ${displayId}.`)}>
            <Mail className="h-4 w-4" />
            Email
          </Button>
        </div>
      )}
      <Trace activity={payload.metadata.activity || []} />
    </div>
  );
}

function StrategyResponse({
  payload,
  rows,
  fallback,
}: {
  payload: ChatResponse;
  rows: RetainFlowRow[];
  fallback: string;
}) {
  return (
    <div className="grid gap-4">
      <div className="rounded-md border bg-slate-50 p-4">
        <p className="mb-2 text-xs font-bold uppercase text-primary">Strategie recommandee</p>
        <p className="text-sm leading-6 text-slate-700">{payload.answer || fallback}</p>
      </div>
      {rows.length > 0 && (
        <div className="grid gap-3">
          {rows.slice(0, 3).map((row) => (
            <article key={textValue(row, ["document_id", "title"])} className="rounded-md border bg-white p-4">
              <div className="mb-2 flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-950">{textValue(row, ["title"], "Document strategie")}</p>
                  <p className="text-xs text-muted-foreground">{textValue(row, ["document_id", "path"])}</p>
                </div>
                <span className="rounded-md bg-teal-50 px-2 py-1 text-xs font-bold text-teal-700 ring-1 ring-teal-200">
                  Score {Number(row.score ?? 0).toFixed(2)}
                </span>
              </div>
              <p className="line-clamp-4 text-sm leading-6 text-slate-600">{textValue(row, ["preview"], "Aucun extrait disponible.")}</p>
            </article>
          ))}
        </div>
      )}
      <Trace activity={payload.metadata.activity || []} />
    </div>
  );
}

function ThinkingBlock() {
  return (
    <motion.article initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary text-white">
        <Bot className="h-4 w-4" />
      </div>
      <div className="w-full max-w-[760px] rounded-lg border bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center gap-2 text-sm font-bold">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          RetainFlow analyse la demande
        </div>
        <p className="text-sm text-slate-600">L'activite exacte sera affichee des que le backend retourne sa trace.</p>
      </div>
    </motion.article>
  );
}

function Trace({ activity }: { activity: ActivityItem[] }) {
  if (!activity.length) return null;

  return (
    <details className="rounded-md border bg-white p-3">
      <summary className="cursor-pointer text-xs font-bold uppercase text-muted-foreground">Comment cette reponse a ete produite</summary>
      <div className="mt-3 grid gap-2">
        {activity.map((item) => (
          <div key={item.id} className="flex items-center gap-2 text-sm text-slate-600">
            <StatusIcon status={item.status} />
            {item.business_label}
          </div>
        ))}
      </div>
    </details>
  );
}

function AgentActivityPanel({
  response,
  customer,
  selectedId,
  onPrompt,
}: {
  response: ChatResponse | null;
  customer: RetainFlowRow | undefined;
  selectedId: string | null;
  onPrompt: (prompt: string) => void;
}) {
  const score = numberValue(customer, ["churn_probability", "prediction_probability", "risk_score"]);
  const activity = response?.metadata.activity || [];
  const hasCustomerContext = Boolean(selectedId && customer);

  return (
    <aside className="hidden min-h-0 overflow-auto border-l bg-white xl:block">
      <div className="grid gap-4 p-4">
        <Card>
          <CardHeader>
            <CardTitle>Suivi agentique</CardTitle>
            <CardDescription>
              {activity.length ? `${activity.length} etape${activity.length > 1 ? "s" : ""} executee${activity.length > 1 ? "s" : ""}` : "Aucune requete selectionnee"}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {activity.length ? (
              <div className="grid gap-3">
                {activity.map((item, index) => (
                  <ActivityCard key={item.id} item={item} index={index + 1} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Pose une question pour voir le routage, les agents appeles et les outils utilises.</p>
            )}
          </CardContent>
        </Card>

        {hasCustomerContext && (
          <Card>
            <CardHeader>
              <CardTitle>Contexte client</CardTitle>
              <CardDescription>{selectedId}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div>
                <div className="mb-2 flex items-end justify-between gap-3">
                  <div>
                    <p className="text-lg font-bold">
                      {textValue(customer, ["first_name"])} {textValue(customer, ["last_name"], "")}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {textValue(customer, ["customer_segment"])} · {textValue(customer, ["region", "agency_name"])}
                    </p>
                  </div>
                  <span className={cn("rounded-md px-2 py-1 text-xs font-bold ring-1", riskClass(score))}>{formatPercent(score)}</span>
                </div>
              </div>
              <Button onClick={() => onPrompt(`Pourquoi ${selectedId} est-il a risque ?`)} variant="outline">
                <Sparkles className="h-4 w-4" />
                Expliquer
              </Button>
              <Button onClick={() => onPrompt(`Redige-moi un email de retention pour ${selectedId}.`)}>
                <Mail className="h-4 w-4" />
                Rediger l'email
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </aside>
  );
}

function ActivityCard({ item, index }: { item: ActivityItem; index: number }) {
  return (
    <details className="rounded-md border bg-slate-50 p-3" open={item.status === "failed"}>
      <summary className="cursor-pointer list-none">
        <div className="flex items-start gap-3">
          <div className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-white text-xs font-bold text-slate-700 ring-1 ring-slate-200">
            {index}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold text-sm">{item.business_label}</p>
              <span className="flex items-center gap-1 text-[11px] uppercase text-muted-foreground">
                <StatusIcon status={item.status} />
                {item.status}
              </span>
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-600">{item.summary}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {item.agent}
              {item.tool ? ` · ${item.tool}` : ""}
            </p>
          </div>
        </div>
      </summary>
      <div className="mt-3 grid gap-2 border-t pt-3 text-xs text-slate-600">
        <div className="flex justify-between gap-3">
          <span>Agent</span>
          <span className="font-semibold text-slate-900">{item.agent}</span>
        </div>
        {item.tool && (
          <div className="flex justify-between gap-3">
            <span>Tool</span>
            <span className="font-semibold text-slate-900">{item.tool}</span>
          </div>
        )}
        {item.details && <pre className="max-h-48 overflow-auto rounded-md bg-slate-950 p-3 text-slate-100">{JSON.stringify(item.details, null, 2)}</pre>}
        {item.sources && <pre className="max-h-48 overflow-auto rounded-md bg-slate-950 p-3 text-slate-100">{JSON.stringify(item.sources, null, 2)}</pre>}
        {item.error && <p className="rounded-md bg-red-50 p-2 text-red-700">{item.error}</p>}
      </div>
    </details>
  );
}

function StatusIcon({ status }: { status: ActivityItem["status"] }) {
  if (status === "completed") return <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />;
  if (status === "running") return <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />;
  if (status === "failed") return <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />;
  if (status === "skipped") return <Circle className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />;
  return <Circle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-white p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  );
}
