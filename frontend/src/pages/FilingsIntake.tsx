import "./shared/fields.css";
import "./admin/Admin.css";

/*
 * Official filings intake (now under /admin/intake): the priority checklist
 * (EGX33 Shariah members + the 30 most-traded companies) and an entry form.
 * Every value is copied by a person from the official filing together with its
 * page number; the backend runs the same validation gates as automated
 * extraction and returns each line's outcome. Filing-backed lines replace
 * provisional vendor lines.
 */

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { recordManualFiling, useFilingsIntake } from "../api/client";
import { Tag } from "../components/ui/Badges";
import DataTable, { StockCell, type Column } from "../components/ui/DataTable";
import { ExternalLinkIcon } from "../components/ui/icons";
import { Missing } from "../components/ui/Missing";
import { PageTitle } from "../components/ui/PageTitle";
import { ErrorState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtInt } from "../lib/format";
import type { CopyKey } from "../i18n";
import type { IntakeItem, IntakeLineDef, ManualFilingResponse } from "../types";
import { describeError, type ErrorView } from "./shared/apiError";
import { Field } from "./shared/Field";
import { ErrorMessage, FormMessage } from "./shared/FormMessage";
import { ForeignText } from "./shared/ForeignText";

const STATUS_KEY: Record<IntakeItem["status"], CopyKey> = {
  missing: "intake_status_missing",
  vendor_only: "intake_status_vendor_only",
  filed: "intake_status_filed",
};

const REASON_KEY: Record<IntakeItem["reasons"][number], CopyKey> = {
  egx33: "intake_reason_egx33",
  most_traded: "intake_reason_most_traded",
};

const SECTION_KEY: Record<IntakeLineDef["section"], CopyKey> = {
  income: "section_income",
  balance: "section_balance",
  cash_flow: "section_cash_flow",
};

/** Server line statuses (ExtStatus) as reader-facing words. */
const OUTCOME_KEY: Record<string, CopyKey> = {
  approved: "intake_outcome_accepted",
  auto_validated: "intake_outcome_accepted",
  extraction_candidate: "intake_outcome_review",
  rejected: "intake_outcome_rejected",
};

export default function FilingsIntake() {
  const { t, locale } = useLang();
  const { data, isLoading, isError, refetch } = useFilingsIntake();
  const [selected, setSelected] = useState<IntakeItem | null>(null);

  const columns = useMemo<Column<IntakeItem>[]>(
    () => [
      {
        id: "company",
        header: t("intake_col_company"),
        sticky: true,
        sortable: true,
        sortValue: (i) => i.ticker,
        cell: (i) => (
          <span className="adm-company-cell">
            <StockCell ticker={i.ticker} href={`/companies/${encodeURIComponent(i.ticker)}/financials`} name={<bdi dir="ltr">{i.name}</bdi>} />
            <span className="adm-tags">
              {i.reasons.map((r) => (
                <Tag key={r}>{t(REASON_KEY[r])}</Tag>
              ))}
            </span>
          </span>
        ),
      },
      {
        id: "status",
        header: t("intake_col_status"),
        sortable: true,
        sortValue: (i) => i.status,
        cell: (i) => <Tag>{t(STATUS_KEY[i.status])}</Tag>,
      },
      { id: "target", header: t("intake_col_target"), type: "num", cell: (i) => i.target_year },
      {
        id: "filed",
        header: t("intake_col_filed"),
        type: "num",
        cell: (i) => (i.filing_years.length > 0 ? i.filing_years.join(", ") : <Missing />),
      },
      {
        id: "vendor",
        header: t("intake_col_vendor"),
        type: "num",
        cell: (i) => (i.vendor_years.length > 0 ? i.vendor_years.join(", ") : <Missing />),
      },
      {
        id: "action",
        header: t("intake_col_action"),
        cell: (i) => (
          <span className="adm-actions">
            <button type="button" className="link-btn" onClick={() => setSelected(i)}>
              {t("intake_enter")}
            </button>
            {i.disclosure_url && (
              <a href={i.disclosure_url} target="_blank" rel="noreferrer">
                {t("intake_disclosures")} <ExternalLinkIcon size={12} />
              </a>
            )}
          </span>
        ),
      },
    ],
    [t],
  );

  return (
    <section className="page">
      <PageTitle parts={[t("nav_intake"), t("admin_title")]} />
      <div>
        <h2 className="section-title">{t("intake_title")}</h2>
        <p className="muted">{t("intake_subtitle")}</p>
      </div>

      {selected && data && (
        <FilingForm key={selected.ticker} item={selected} lines={data.lines} onClose={() => setSelected(null)} />
      )}

      {isError ? (
        <ErrorState thing={t("intake_things")} onRetry={() => void refetch()} />
      ) : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(i) => i.company_id}
          caption={t("intake_title")}
          loading={isLoading}
          loadingThing={t("intake_things")}
          hideDensityToggle
          meta={data ? t("intake_count", { n: fmtInt(locale, data.items.length) ?? "" }) : undefined}
        />
      )}
    </section>
  );
}

interface LineInput {
  value: string;
  page: string;
}

function FilingForm({
  item,
  lines,
  onClose,
}: {
  item: IntakeItem;
  lines: IntakeLineDef[];
  onClose: () => void;
}) {
  const { t, lang, locale } = useLang();
  const queryClient = useQueryClient();
  const [fiscalYear, setFiscalYear] = useState(String(item.target_year));
  const [periodEnd, setPeriodEnd] = useState(`${item.target_year}-12-31`);
  const [documentUrl, setDocumentUrl] = useState("");
  const [publicationDate, setPublicationDate] = useState("");
  const [currency, setCurrency] = useState("EGP");
  const [inputs, setInputs] = useState<Record<string, LineInput>>({});
  const [saving, setSaving] = useState(false);
  const [needPage, setNeedPage] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);
  const [result, setResult] = useState<ManualFilingResponse | null>(null);

  const bySection = useMemo(() => {
    const groups: Record<IntakeLineDef["section"], IntakeLineDef[]> = { income: [], balance: [], cash_flow: [] };
    for (const line of lines) groups[line.section].push(line);
    return groups;
  }, [lines]);

  const setLine = (code: string, patch: Partial<LineInput>): void => {
    setInputs((prev) => ({
      ...prev,
      [code]: { value: prev[code]?.value ?? "", page: prev[code]?.page ?? "", ...patch },
    }));
  };

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    const entered = Object.entries(inputs).filter(([, v]) => v.value.trim() !== "");
    setNeedPage(false);
    setError(null);
    if (entered.some(([, v]) => v.page.trim() === "")) {
      setNeedPage(true);
      return;
    }
    setSaving(true);
    try {
      const response = await recordManualFiling({
        ticker: item.ticker,
        fiscal_year: Number(fiscalYear),
        period_end: periodEnd,
        document_url: documentUrl.trim(),
        publication_date: publicationDate || null,
        currency: currency.trim().toUpperCase(),
        lines: entered.map(([code, v]) => ({
          code,
          value: v.value.replace(/[,\s]/g, ""),
          page: v.page.trim(),
        })),
      });
      setResult(response);
      await queryClient.invalidateQueries({ queryKey: ["filingsIntake"] });
      await queryClient.invalidateQueries({ queryKey: ["statements", item.ticker] });
    } catch (err) {
      setError(describeError(err, t, "intake_failed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card panel" onSubmit={(e) => void submit(e)}>
      <div className="adm-form-head">
        <h3>
          {t("intake_form_title")} · <bdi dir="ltr">{item.ticker}</bdi>
        </h3>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          {t("intake_close")}
        </button>
      </div>
      <div className="fld-row">
        <Field label={t("intake_fiscal_year")}>
          <input type="number" dir="ltr" required value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)} />
        </Field>
        <Field label={t("intake_period_end")}>
          <input type="date" dir="ltr" required value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
        </Field>
        <Field label={t("intake_publication_date")}>
          <input type="date" dir="ltr" value={publicationDate} onChange={(e) => setPublicationDate(e.target.value)} />
        </Field>
        <Field label={t("intake_currency")}>
          <input dir="ltr" maxLength={3} required value={currency} onChange={(e) => setCurrency(e.target.value)} />
        </Field>
      </div>
      <Field label={t("intake_document_url")}>
        <input
          type="url"
          dir="ltr"
          required
          placeholder="https://www.egx.com.eg/…"
          value={documentUrl}
          onChange={(e) => setDocumentUrl(e.target.value)}
        />
      </Field>

      {(Object.keys(bySection) as IntakeLineDef["section"][]).map((section) => (
        <div key={section} className="adm-stack">
          <h4 className="section-title">{t(SECTION_KEY[section])}</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("col_line")}</th>
                  <th scope="col" className="num" dir="ltr">
                    {t("intake_value")}
                  </th>
                  <th scope="col" className="num" dir="ltr">
                    {t("intake_page")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {bySection[section].map((line) => {
                  const outcome = result?.lines.find((r) => r.code === line.code);
                  const outcomeKey = outcome ? OUTCOME_KEY[outcome.status] : undefined;
                  return (
                    <tr key={line.code}>
                      <td>
                        <div className="adm-line-cell">
                        {lang === "ar" ? line.label_ar : line.label_en}
                        {outcome && (
                          <span className="text-note">
                            {outcomeKey ? t(outcomeKey) : t("intake_outcome_unknown")}
                            {outcome.reason ? (
                              <>
                                {" "}
                                <ForeignText>{outcome.reason}</ForeignText>
                              </>
                            ) : null}
                          </span>
                        )}
                        </div>
                      </td>
                      <td className="num" dir="ltr">
                        <div className="fld adm-cell-input">
                          <input
                            dir="ltr"
                            inputMode="decimal"
                            aria-label={`${lang === "ar" ? line.label_ar : line.label_en}: ${t("intake_value")}`}
                            value={inputs[line.code]?.value ?? ""}
                            onChange={(e) => setLine(line.code, { value: e.target.value })}
                          />
                        </div>
                      </td>
                      <td className="num" dir="ltr">
                        <div className="fld adm-cell-input adm-cell-input-page">
                          <input
                            dir="ltr"
                            aria-label={`${lang === "ar" ? line.label_ar : line.label_en}: ${t("intake_page")}`}
                            value={inputs[line.code]?.page ?? ""}
                            onChange={(e) => setLine(line.code, { page: e.target.value })}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {needPage && <FormMessage kind="error" text={t("intake_need_page")} />}
      {error && <ErrorMessage view={error} />}
      {result && <FormMessage kind="success" text={t("intake_saved", { n: fmtInt(locale, result.lines.length) ?? "" })} />}
      <div>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? t("intake_saving") : t("intake_submit")}
        </button>
      </div>
    </form>
  );
}
