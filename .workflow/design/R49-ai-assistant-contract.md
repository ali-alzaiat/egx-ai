# R49 AI assistant: API contract (source of truth for backend and frontend)

Rulings: `.workflow/decisions/R49-ai-assistant.md` (A1–A9). AGENTS.md rules 1, 6, 10 bind: the model only interprets
figures our tools return, never invents them, never says BUY/SELL, never sounds certain. Not a licensed advisor.

New router `app/api/assistant.py`, prefix `/api/assistant`, mounted in `main.py` with `dependencies=protected`.
The legacy `/api/ai` router stays untouched.

## Backend layout (`backend/app/ai/`)

| Module | Role |
|---|---|
| `gateway/base.py` | `ChatProvider` protocol: `stream(model, api_key, messages, tools, max_tokens) -> AsyncIterator[ChatEvent]`; events `TextDelta(text)`, `ToolCall(id, name, arguments: dict)`, `Done(input_tokens, output_tokens, cost_usd: Decimal | None)`. Messages/tools are our own dataclasses (OpenAI-style roles: system, user, assistant(+tool_calls), tool). |
| `gateway/litellm_provider.py` | The only module importing `litellm`. `acompletion(stream=True, api_key=...)`, no custom `api_base` ever. Telemetry, callbacks and verbose/debug logging off. Cost from LiteLLM's cost map. Any exception text is scrubbed of the key before it is logged or re-raised. |
| `gateway/fake.py` | Scripted provider for tests (no network anywhere in tests). |
| `catalog.py` | Curated models per provider (`anthropic`, `openai`, `gemini`): id, label, provider. Claude: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. OpenAI and Gemini: a flagship and a small model each, chosen from LiteLLM 1.105.1's `model_cost` map — each entry must exist there with `mode == "chat"`, `supports_function_calling` true and a token price (a test asserts this for every catalog entry). |
| `keys.py` | Key store: Fernet with `AI_SECRETS_KEY` (settings, from `.env`). If `AI_SECRETS_KEY` is unset, saving a key fails closed (503 `AI_SECRETS_KEY_MISSING`); `.env` keys still work. Resolution per provider: UI-saved key, else `.env` (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`), else none. |
| `tools/` | Read-only tools over existing services (never raw SQL from the model, never writes): `company_overview`, `investment_score`, `valuation`, `stance`, `shariah_status`, `price_summary`, `chart_patterns`, `financial_metrics`, `search_companies`, `screen_companies` (fixed filters: sector, shariah status, stance, forming pattern, a few metric thresholds). Each returns JSON with `as_of`, methodology versions and source; `INSUFFICIENT_DATA` is passed through, never turned into zero. Ticker arguments are validated against the company table. |
| `prompts.py` | System prompts as constants; `AI_PROMPT_VERSION = "assistant-1.0"` in `ai/constants.py` (bump on any prompt or tool change). Answer in the user's language (EN or AR); every figure must come from a tool; say when data is missing; no advice or certainty; mention the source tool. |
| `orchestrator.py` | Loop: model → tool calls → run tools → model, at most `MAX_TOOL_ROUNDS = 6`, `MAX_OUTPUT_TOKENS = 1500`. Then `verify`; on failure one retry with the unverified numbers listed; on second failure the answer is withheld (A3). |
| `verify.py` | **Pure.** Extract numbers from the answer: Western and Arabic-Indic digits (`٠-٩`, `٫` decimal, `٬` thousands), `,` thousands, `%`, units k/m/bn/million/billion/مليون/مليار. Match each against all numbers in this turn's tool results (and the user's own message) allowing display rounding (match at the answer's shown decimals, or 0.5% relative) and percent↔fraction (12% vs 0.12). Ignore years 1900–2100 written as dates/years and list ordinals. Returns `{verified: bool, checked: int, unverified: [str]}`. |
| `service.py` | Conversations, monthly cap, persistence, settings. |

## Storage (migration 026)

- `ai_provider_keys(provider PK, ciphertext, last4, set_at)`.
- `ai_settings` (single row): `default_model`, `monthly_cap_usd NUMERIC NULL` (NULL = off).
- `ai_conversations(id, title, company_id NULL, created_at, updated_at)`.
- `ai_messages(id, conversation_id NULL (explain calls), role, content, provider, model, prompt_version, tool_calls JSONB, verification JSONB, status ('answered'|'unverified'|'error'|'cap_reached'), input_tokens, output_tokens, cost_usd NUMERIC NULL, created_at)`.
- Month spend = sum of `cost_usd` for the current calendar month (UTC).

## Endpoints

All JSON responses from settings/key endpoints carry `Cache-Control: no-store`. A key is never returned after saving.

| Method + path | Body / query | Response |
|---|---|---|
| `GET /models` | — | `{default_model, models: [{id, label, provider, available}]}`; `available` = the provider has a key. |
| `GET /settings` | — | `{providers: [{provider, label, configured, source: "ui"\|"env"\|null, last4, set_at, free_tier}], default_model, monthly_cap_usd, month_spend_usd, secrets_key_set}` |
| `PUT /settings` | `{default_model?, monthly_cap_usd?: string\|null, free_tier_providers?: provider[]}` (A10: free-tier calls cost $0 and skip the cap) | settings as above; 422 on unknown model or negative cap. |
| `PUT /keys/{provider}` | `{api_key}` (`SecretStr`, 8–400 chars) | Tests the key with one minimal call first; 422 `KEY_REJECTED` if the provider refuses it; else saves and returns the provider row. |
| `POST /keys/{provider}/test` | — | `{ok, detail}` using the active key. |
| `DELETE /keys/{provider}` | — | provider row (falls back to `.env` if present). |
| `POST /chat` | `{message (1–4000 chars), conversation_id?, model?, ticker?, lang: "en"\|"ar"}` | `text/event-stream` (below). `ticker` scopes the chat to that company (its overview goes in context). |
| `POST /explain` | `{ticker, card: "score"\|"valuation"\|"stance"\|"shariah", model?, lang}` | Same stream; runs the card's tool and a fixed explain prompt; stored with `conversation_id NULL`. |
| `GET /conversations` | `limit` ≤ 50 | `[{id, title, ticker, updated_at}]` newest first. |
| `GET /conversations/{id}` | — | `{id, title, ticker, messages: [{role, content, status, model, verification, created_at}]}` |
| `DELETE /conversations/{id}` | — | 204 |

### Stream events (`event:` name, `data:` JSON)

The answer is never streamed before verification (A3), so the stream carries progress then the final answer:

- `meta` `{conversation_id, model}`
- `status` `{stage: "thinking"|"tool"|"verifying"|"retrying", tool?: name}`
- `answer` `{text, verified: true, checked, sources: [{tool, ticker?}]}`
- `unverified` `{checked, unverified: [str], sources}`: answer withheld; the UI says it couldn't verify the figures.
- `error` `{code, detail}`: codes `NO_KEY`, `CAP_REACHED`, `PROVIDER_ERROR`, `INSUFFICIENT_DATA`, `UNKNOWN_MODEL`.
- `done` `{input_tokens, output_tokens, cost_usd, month_spend_usd}`

Errors before the stream starts use normal HTTP codes (404 unknown ticker/conversation, 422 bad body).

## Safeguards (A7)

- Key-changing endpoints (`PUT/DELETE /keys/*`, `PUT /settings`) reject a request whose `Origin` header is present and not in `CORS_ORIGINS` (403), and accept keys only over HTTPS or from loopback / private-network clients (the compose ports bind to 127.0.0.1; other containers reach the backend over the docker network). Otherwise 403 `INSECURE_TRANSPORT`.
- The model never sees a key; tools are read-only; tool output and user text are data, never instructions.
- Monthly cap checked before every model call; reached → `error CAP_REACHED`, no call made.
- Tests prove: the key never appears in any response or captured log; the fake provider is used everywhere; the verifier rejects a planted number and accepts rounded / Arabic-digit forms.

## Frontend

- `api/client.ts`: hooks `useAssistantModels`, `useAssistantSettings`, `useConversations`, `useConversation`, mutations for settings/keys/delete; `streamAssistant(path, body, onEvent, signal)` over `fetch` + `ReadableStream`, with the SSE parser as a pure module (`lib/sse.ts`, vitest in node).
- **Floating button** on every page (bottom inline-end corner; above the mobile bottom area), opens a **non-modal side panel** (inline-end side, full screen on phones, Escape closes, focus returns to the button). On a company page the panel is scoped to that ticker and says so.
- **Assistant page** `/assistant` in the sidebar nav: conversation list + the same chat view.
- Chat view: native model `<select>` (only available models; when none, a link to Admin > AI settings), message list, progress line from `status` events, answers with a "Figures checked against our data (N)" note and sources linking to the company tabs, the unverified state, a one-line "Not investment advice" note, Stop button (abort).
- **Explain this** button on the Score, Valuation, Stance and Shariah cards: opens the panel and runs `/explain`.
- **Admin > AI settings** (`/admin/ai`): a row per provider (status, source, masked key, set date, Remove), password field (autocomplete off, cleared after submit) with Test & save, default model, monthly cap and this month's spend, and a notice when `secrets_key_set` is false.
- All copy EN/AR via `t()`; RTL; 375px; dark mode.
