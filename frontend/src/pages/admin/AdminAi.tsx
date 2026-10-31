import "../shared/fields.css";
import "../../components/research/research.css";
import "./Admin.css";

import { useState, type FormEvent } from "react";
import { Badge } from "@/components/shadcn/badge";
import { Button } from "@/components/shadcn/button";
import { Input } from "@/components/shadcn/input";
import {
  AssistantApiError,
  useAssistantModels,
  useAssistantSettings,
  useRemoveProviderKey,
  useSaveAssistantSettings,
  useSaveProviderKey,
  useTestProviderKey,
} from "../../api/client";
import { Missing } from "../../components/ui/Missing";
import { Notice } from "../../components/ui/Notice";
import { ErrorState, LoadingState } from "../../components/ui/States";
import type { CopyKey } from "../../i18n";
import { useLang } from "../../i18n/useLang";
import { capInputValue, parseCapInput } from "../../lib/assistant";
import { fmtDate, toNumber } from "../../lib/format";
import type { AssistantModel, AssistantProviderId, AssistantProviderRow, AssistantSettings } from "../../types";
import { Field } from "../shared/Field";
import { FormMessage } from "../shared/FormMessage";

interface Message {
  kind: "success" | "error";
  text: string;
  detail?: string | null;
}

const ERROR_KEYS: Readonly<Record<string, CopyKey>> = {
  KEY_REJECTED: "aiset_err_KEY_REJECTED",
  AI_SECRETS_KEY_MISSING: "aiset_err_AI_SECRETS_KEY_MISSING",
  INSECURE_TRANSPORT: "aiset_err_INSECURE_TRANSPORT",
};

/** A localized sentence for a failed settings call; the server's English detail is kept only for the codes this page does not know. */
function describeAiError(err: unknown, t: (key: CopyKey) => string): Message {
  if (err instanceof AssistantApiError) {
    const key = err.code ? ERROR_KEYS[err.code] : undefined;
    if (key) return { kind: "error", text: t(key) };
    if (err.status === 403) return { kind: "error", text: t("aiset_err_forbidden") };
    return { kind: "error", text: t("aiset_err_generic"), detail: err.detail };
  }
  return { kind: "error", text: t("aiset_err_generic") };
}

function ProviderCard({
  row,
  secretsKeySet,
  freeTier,
}: {
  row: AssistantProviderRow;
  secretsKeySet: boolean;
  /** Every provider currently marked free tier (the setting is saved as one list). */
  freeTier: readonly AssistantProviderId[];
}) {
  const { t, locale } = useLang();
  const save = useSaveProviderKey();
  const saveSettings = useSaveAssistantSettings();
  const remove = useRemoveProviderKey();
  const test = useTestProviderKey();
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState<Message | null>(null);
  const busy = save.isPending || remove.isPending || test.isPending;
  const setAt = fmtDate(locale, row.set_at);
  const inputId = `aiset-key-${row.provider}`;

  const onSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    const typed = apiKey.trim();
    // The field is emptied the moment the form is submitted: the key lives only in this request.
    setApiKey("");
    if (typed.length < 8 || busy) return;
    setMessage(null);
    try {
      await save.mutateAsync({ provider: row.provider, apiKey: typed });
      setMessage({ kind: "success", text: t("aiset_saved") });
    } catch (err) {
      setMessage(describeAiError(err, t));
    } finally {
      // Drop the request variables (they hold the key) from the query cache.
      save.reset();
    }
  };

  const onTest = async (): Promise<void> => {
    setMessage(null);
    try {
      const result = await test.mutateAsync(row.provider);
      setMessage(
        result.ok
          ? { kind: "success", text: t("aiset_test_ok") }
          : { kind: "error", text: t("aiset_test_fail"), detail: result.detail },
      );
    } catch (err) {
      setMessage(describeAiError(err, t));
    }
  };

  const onFreeTier = async (on: boolean): Promise<void> => {
    setMessage(null);
    const others = freeTier.filter((p) => p !== row.provider);
    try {
      await saveSettings.mutateAsync({ free_tier_providers: on ? [...others, row.provider] : others });
      setMessage({ kind: "success", text: t(on ? "aiset_free_tier_on" : "aiset_free_tier_off") });
    } catch (err) {
      setMessage(describeAiError(err, t));
    }
  };

  const onRemove = async (): Promise<void> => {
    if (!window.confirm(t("aiset_delete_confirm", { provider: row.label }))) return;
    setMessage(null);
    try {
      await remove.mutateAsync(row.provider);
      setMessage({ kind: "success", text: t("aiset_removed") });
    } catch (err) {
      setMessage(describeAiError(err, t));
    }
  };

  return (
    <li className="card-surface flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="me-auto text-h3 font-semibold">{row.label}</h3>
        <Badge variant={row.configured ? "gain" : "muted"}>
          {row.configured ? t("aiset_status_configured") : t("aiset_status_missing")}
        </Badge>
        {row.source && <Badge variant="outline">{row.source === "ui" ? t("aiset_source_ui") : t("aiset_source_env")}</Badge>}
      </div>

      {row.configured && (
        <dl className="rs-kv">
          <dt>{t("aiset_key_label")}</dt>
          <dd dir="ltr">{row.last4 ? <code>{`•••• ${row.last4}`}</code> : <Missing />}</dd>
          {setAt && (
            <>
              <dt>{t("aiset_source_label")}</dt>
              <dd>
                {row.source === "ui" ? t("aiset_source_ui") : t("aiset_source_env")} · {t("aiset_set_at", { date: setAt })}
              </dd>
            </>
          )}
        </dl>
      )}
      {row.source === "ui" && (
        <div>
          <Button
            variant="destructive"
            size="sm"
            disabled={busy}
            aria-label={t("aiset_remove_aria", { provider: row.label })}
            onClick={() => void onRemove()}
          >
            {remove.isPending ? t("aiset_removing") : t("aiset_remove")}
          </Button>
        </div>
      )}
      {row.source === "env" && <p className="text-meta text-muted-foreground">{t("aiset_env_source_note")}</p>}

      <div className="flex flex-col gap-1">
        <label className="fld-check">
          <input
            type="checkbox"
            checked={row.free_tier}
            disabled={saveSettings.isPending}
            onChange={(e) => void onFreeTier(e.target.checked)}
          />
          {t("aiset_free_tier")}
        </label>
        <p className="text-meta text-muted-foreground">{t("aiset_free_tier_hint")}</p>
      </div>

      <form className="flex flex-col gap-2" onSubmit={(e) => void onSubmit(e)} autoComplete="off">
        <Field label={t("aiset_key_input", { provider: row.label })} hint={t("aiset_key_hint")}>
          <Input
            id={inputId}
            type="password"
            name={`${row.provider}-secret`}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            maxLength={400}
            dir="ltr"
            data-1p-ignore
            data-lpignore="true"
            disabled={!secretsKeySet || busy}
            value={apiKey}
            placeholder={t("aiset_key_placeholder")}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={!secretsKeySet || busy || apiKey.trim().length < 8}>
            {save.isPending ? t("aiset_saving") : t("aiset_test_save")}
          </Button>
          {row.configured && (
            <Button variant="outline" disabled={busy} onClick={() => void onTest()}>
              {test.isPending ? t("aiset_testing") : t("aiset_test")}
            </Button>
          )}
        </div>
      </form>
      {message && <FormMessage kind={message.kind} text={message.text} detail={message.detail} />}
    </li>
  );
}

/** Keep a currency amount in one piece inside Arabic text (left-to-right isolate). */
function isolate(text: string): string {
  return "⁦" + text + "⁩";
}

function usd(locale: string, value: string | number | null | undefined): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  return new Intl.NumberFormat(locale, { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(n);
}

function DefaultsForm({ settings, models }: { settings: AssistantSettings; models: readonly AssistantModel[] }) {
  const { t, locale } = useLang();
  const save = useSaveAssistantSettings();
  const [model, setModel] = useState(settings.default_model ?? "");
  const [cap, setCap] = useState(capInputValue(settings.monthly_cap_usd));
  const [message, setMessage] = useState<Message | null>(null);
  const capCheck = parseCapInput(cap);
  const spend = usd(locale, settings.month_spend_usd);
  const capText = usd(locale, settings.monthly_cap_usd);

  const onSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    if (!capCheck.ok) return;
    setMessage(null);
    const body: { default_model?: string; monthly_cap_usd: string | null } = { monthly_cap_usd: capCheck.value };
    if (model !== "") body.default_model = model;
    try {
      await save.mutateAsync(body);
      setMessage({ kind: "success", text: t("aiset_settings_saved") });
    } catch (err) {
      setMessage(describeAiError(err, t));
    }
  };

  return (
    <form className="card-surface flex min-w-0 flex-col gap-4" onSubmit={(e) => void onSubmit(e)}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label={t("aiset_default_model")}>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {model === "" && <option value="">{t("aiset_default_model_none")}</option>}
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.available ? m.label : t("aiset_model_no_key", { label: m.label })}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("aiset_cap")} hint={capCheck.ok ? t("aiset_cap_hint") : undefined}>
          <Input
            type="text"
            inputMode="decimal"
            dir="ltr"
            autoComplete="off"
            value={cap}
            placeholder={t("aiset_cap_placeholder")}
            aria-invalid={!capCheck.ok}
            onChange={(e) => setCap(e.target.value)}
          />
        </Field>
      </div>
      {!capCheck.ok && <FormMessage kind="error" text={t("aiset_cap_invalid")} />}

      <dl className="rs-kv">
        <dt>{t("aiset_spend")}</dt>
        <dd>
          {spend ? <bdi dir="ltr">{spend}</bdi> : <Missing />}
          {capText ? ` ${t("aiset_spend_of_cap", { cap: isolate(capText) })}` : ""}
        </dd>
      </dl>
      <p className="text-meta text-muted-foreground">{t("aiset_spend_note")}</p>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={save.isPending || !capCheck.ok}>
          {t("aiset_save")}
        </Button>
      </div>
      {message && <FormMessage kind={message.kind} text={message.text} detail={message.detail} />}
    </form>
  );
}

/** Admin > AI settings: provider keys (write-only), default model, monthly cap and this month's spend. */
export default function AdminAi() {
  const { t } = useLang();
  const settingsQuery = useAssistantSettings();
  const modelsQuery = useAssistantModels();

  if (settingsQuery.isLoading) return <LoadingState thing={t("aiset_thing")} />;
  const settings = settingsQuery.data;
  if (settingsQuery.isError || !settings) {
    return <ErrorState thing={t("aiset_thing")} onRetry={() => void settingsQuery.refetch()} />;
  }

  return (
    <div className="adm-stack">
      <p className="text-text-2">{t("aiset_subtitle")}</p>
      {!settings.secrets_key_set && <Notice variant="warning">{t("aiset_secrets_missing")}</Notice>}

      <section className="adm-stack" aria-labelledby="aiset-providers">
        <h2 id="aiset-providers" className="section-title">
          {t("aiset_providers")}
        </h2>
        <ul className="adm-stack list-none">
          {settings.providers.map((row) => (
            <ProviderCard
              key={row.provider}
              row={row}
              secretsKeySet={settings.secrets_key_set}
              freeTier={settings.providers.filter((p) => p.free_tier).map((p) => p.provider)}
            />
          ))}
        </ul>
      </section>

      <section className="adm-stack" aria-labelledby="aiset-defaults">
        <h2 id="aiset-defaults" className="section-title">
          {t("aiset_defaults")}
        </h2>
        <DefaultsForm
          key={`${settings.default_model ?? ""}|${settings.monthly_cap_usd ?? ""}`}
          settings={settings}
          models={modelsQuery.data?.models ?? []}
        />
      </section>
    </div>
  );
}
