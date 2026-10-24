import "./shared/fields.css";
import "./Events.css";

import { useMemo, useState } from "react";
import { exportEvents, useEvents } from "../api/client";
import { Tag } from "../components/ui/Badges";
import CompanySearch from "../components/ui/CompanySearch";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { EmptyState, ErrorState, LoadingState, NoMatch } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import type { Company, PhaseEvent } from "../types";
import { describeError, type ErrorView } from "./shared/apiError";
import { Field, FieldGroup } from "./shared/Field";
import { ErrorMessage } from "./shared/FormMessage";
import { ForeignText } from "./shared/ForeignText";
import { CompanyRef } from "./tracking/CompanyRef";
import { fmtDateTime } from "./tracking/dateTime";
import {
  EMPTY_FILTERS,
  EVENT_TYPES,
  eventTypeLabel,
  hasFilters,
  snapshotHighlights,
  stringifySnapshot,
  toQueryParams,
  type EventFilters,
} from "./tracking/eventFormat";
import { useCompanyIndex } from "./shared/useCompanyIndex";

export default function Events() {
  const { t } = useLang();
  const { byId: companies, loading: companiesLoading } = useCompanyIndex();
  const [filters, setFilters] = useState<EventFilters>(EMPTY_FILTERS);
  const [picked, setPicked] = useState<Company | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<ErrorView | null>(null);

  const params = useMemo(() => toQueryParams(filters), [filters]);
  const { data, isLoading, isError, refetch } = useEvents(params);
  const events = useMemo(() => [...(data ?? [])].sort((a, b) => b.ts.localeCompare(a.ts)), [data]);
  const filtered = hasFilters(filters);

  const clear = (): void => {
    setFilters(EMPTY_FILTERS);
    setPicked(null);
  };

  const setCompany = (company: Company | null): void => {
    setPicked(company);
    setFilters((f) => ({ ...f, symbol: company?.id ?? "" }));
  };

  const handleExport = async (): Promise<void> => {
    setExporting(true);
    setExportError(null);
    try {
      const payload = await exportEvents(params);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "events.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(describeError(err, t, "ev_export_failed"));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="page">
      <PageTitle parts={[t("nav_events")]} />
      <PageHeader
        title={t("nav_events")}
        subtitle={t("ev_subtitle")}
        actions={
          <button type="button" className="btn btn-secondary" onClick={() => void handleExport()} disabled={exporting}>
            {exporting ? t("ev_exporting") : t("ev_export")}
          </button>
        }
      />

      <form className="card ev-filters" onSubmit={(e) => e.preventDefault()}>
        <FieldGroup label={t("ev_company")}>
          <CompanySearch mode="picker" value={picked} onSelect={setCompany} onClear={() => setCompany(null)} />
          {!picked && <span className="fld-hint">{t("ev_all_companies")}</span>}
        </FieldGroup>
        <Field label={t("ev_type")}>
          <select value={filters.type} onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value }))}>
            <option value="">{t("ev_all_types")}</option>
            {EVENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {eventTypeLabel(type, t)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("ev_from")}>
          <input
            type="date"
            dir="ltr"
            value={filters.date_from}
            max={filters.date_to || undefined}
            onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
          />
        </Field>
        <Field label={t("ev_to")}>
          <input
            type="date"
            dir="ltr"
            value={filters.date_to}
            min={filters.date_from || undefined}
            onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
          />
        </Field>
        {filtered && (
          <div>
            <button type="button" className="btn btn-secondary" onClick={clear}>
              {t("clear_filters")}
            </button>
          </div>
        )}
      </form>

      {exportError && <ErrorMessage view={exportError} />}

      {isLoading ? (
        <LoadingState thing={t("ev_things")} />
      ) : isError ? (
        <ErrorState thing={t("ev_things")} onRetry={() => void refetch()} />
      ) : events.length === 0 ? (
        filtered ? (
          <NoMatch things={t("ev_things_plural")} onClear={clear} />
        ) : (
          <EmptyState>{t("ev_empty")}</EmptyState>
        )
      ) : (
        <ul className="ev-feed" aria-label={t("nav_events")}>
          {events.map((event) => (
            <EventRow key={event.id} event={event} companies={companies} loading={companiesLoading} />
          ))}
        </ul>
      )}
    </div>
  );
}

function EventRow({
  event,
  companies,
  loading,
}: {
  event: PhaseEvent;
  companies: ReadonlyMap<string, Company>;
  loading: boolean;
}) {
  const { t, locale } = useLang();
  const highlights = snapshotHighlights(event.inputs_snapshot ?? {}, t, locale);
  const when = fmtDateTime(locale, event.ts);
  return (
    <li id={`event-${event.id}`} className="card ev-row">
      <div className="ev-head">
        <Tag title={t("ev_rule_version", { version: event.rule_version })}>{eventTypeLabel(event.type, t)}</Tag>
        <span className="text-note" dir="ltr">
          {when ?? t("no_value")}
        </span>
      </div>
      <p>{event.reason ? <ForeignText>{event.reason}</ForeignText> : t("ev_no_reason")}</p>
      <p className="ev-companies">
        {event.symbols.length > 0
          ? event.symbols.map((id) => <CompanyRef key={id} company={companies.get(id)} loading={loading} />)
          : <span className="text-note">{t("ev_no_company")}</span>}
      </p>
      {highlights.length > 0 && <p className="text-note">{t("ev_inputs", { items: highlights.join(" · ") })}</p>}
      {event.supersedes_id && (
        <p className="text-note">
          <a href={`#event-${event.supersedes_id}`}>{t("ev_corrects")}</a> {t("ev_corrects_note")}
        </p>
      )}
      <details className="fold">
        <summary>{t("al_technical_details")}</summary>
        <pre className="ev-json" dir="ltr">
          {stringifySnapshot(event.inputs_snapshot ?? {})}
        </pre>
      </details>
      <p className="text-note">
        {t("ev_frame")} {event.actor_type === "system" ? t("ev_recorded_system") : t("ev_recorded_you")}
      </p>
    </li>
  );
}
