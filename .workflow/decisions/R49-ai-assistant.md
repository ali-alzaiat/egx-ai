# R49: AI assistant (owner rulings 2026-10-30)

Rules that bind every item: AGENTS.md 1 (formulas in code), 6 (AI interprets, never invents), 10 (no certainty, no "BUY").

| # | Ruling |
|---|---|
| A1 | **Model-agnostic backend AI API.** The app is not tied to one model; the user picks from a list of popular models. Gateway: see A6. |
| A2 | **Data access option A**: the company's computed data goes to the model directly; questions across companies use read-only tool calls into our services. No embeddings for now (option B, text search over disclosures/theses, is a later step). |
| A3 | **Number guardrail: block and retry.** Every number in an answer must match a value a tool returned; otherwise the answer is rejected and retried once, then shown as "couldn't verify". |
| A4 | **First features**: company Q&A and "Explain this" on result cards. **UI**: a floating button that opens the chat in a side panel, plus a full-page Assistant page in the sidebar nav (general questions); on a company page the panel is scoped to that company. |
| A5 | **Model list**: Claude, OpenAI and Google Gemini; only providers with a key (UI or `.env`, see A7) appear, and only models that support tool calling. |
| A6 | **Gateway: option 1**, our own `ChatProvider` interface with the LiteLLM library inside (exact pin `litellm==1.105.1`, released 2026-10-14; upgraded only on purpose). **Model and API keys are set from the UI** (owner, 2026-10-30); storage and safeguards per the security notes given to the owner. |
| A7 | **Key handling**: keys are encrypted at rest (Fernet, `AI_SECRETS_KEY` only in `.env`) and write-only (UI shows a masked tail and the date set); provider endpoints are fixed in code (no custom URLs); key changes check `Origin`; a Test button validates before saving; the model never sees a key; LiteLLM verbose logging off. A UI-saved key wins; a `.env` key is the fallback; the UI shows which is active. |
| A8 | **Settings live in Admin > AI settings** (keys, default model, monthly cap); the chat's model picker links there when no key is set. |
| A9 | **Monthly cost cap**, set in the UI, off until set; when reached the chat says so and stops calling the model. Token usage is logged per call and the month's total is shown. |
| A10 | **Free-tier switch per provider** (owner, 2026-10-31): a provider marked free tier in Admin > AI settings has its calls stored at $0 and never blocked by the monthly cap (a cap of 0 still blocks every priced call). The switch notes the provider's rate limits and that free-tier prompts may be used to improve the provider's products. Migration 027. |
