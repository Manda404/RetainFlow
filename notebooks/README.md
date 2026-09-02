# RetainFlow Notebooks

## LLM Provider Validation Lab

`llm_provider_api_tests.ipynb` is an isolated notebook for validating LLM providers before integrating them into RetainFlow.

It tests:

- API connectivity
- API key validity without printing secrets
- basic chat
- French instruction following
- JSON / structured outputs
- native tool calling with mock tools
- multi-step tool planning with mock outputs
- streaming
- controlled error handling
- latency
- token usage reporting when available
- RetainFlow SupervisorAgent-specific routing decisions
- capability matrix and recommendation score

## Required Environment Variables

Use `.env` or `.env.local`. Secrets must never be committed.

```bash
GEMINI_API_KEY=...
GOOGLE_API_KEY=...
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
OPENAI_API_KEY=...
```

Model overrides are optional:

```bash
GEMINI_MODEL=gemini-1.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENAI_MODEL=gpt-4o-mini
```

## How To Run

From the repository root:

```bash
poetry install
poetry run jupyter lab notebooks/llm_provider_api_tests.ipynb
```

Or with the local virtual environment:

```bash
.venv/bin/jupyter lab notebooks/llm_provider_api_tests.ipynb
```

Run the notebook cell by cell. Providers without API keys are skipped.

## Adding A Provider

In the notebook, update the centralized `PROVIDERS` dictionary:

- add provider name
- set API key environment variable
- set base URL
- set default model
- implement provider-specific payload/response parsing if it is not OpenAI-compatible or Gemini REST

Keep provider tests isolated in the notebook until the model has passed the capability matrix.
