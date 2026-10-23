import "./Companies.css";

/*
 * Official filings intake: the priority checklist (EGX33 Shariah members + the
 * 30 most-traded companies) and an entry form. Every value is copied by a
 * person from the official filing together with its page number; the backend
 * runs the same validation gates as automated extraction and returns each
 * line's outcome. Filing-backed lines replace provisional vendor lines.
 */

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { recordManualFiling, useFilingsIntake } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import type { IntakeItem, IntakeLineDef, ManualFilingResponse } from "../types";

const STATUS_KEY: Record<IntakeItem["status"], CopyKey> = {
  missing: "intake_status_missing",
  vendor_only: "intake_status_vendor_only",
  filed: "intake_status_filed",
};

const STATUS_CLASS: Record<IntakeItem["status"], string> = {
  missing: "radar-stance radar-stance-reduce",
  vendor_only: "radar-stance radar-stance-hold",
  filed: "radar-stance radar-stance-buy",
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

export default function FilingsIntake() {
  const { t } = useLang();
  const { data, isLoading, error } = useFilingsIntake();
  const [selected, setSelected] = useState<IntakeItem | null>(null);

  return (
    <div>
      <div className="page-header">
        <h1>{t("intake_title")}</h1>
        <p>{t("intake_subtitle")}</p>
      </div>
      {isLoading && <div className="loading">{t("loading")}</div>}
      {error && <div className="alert alert-error">{t("load_error")}</div>}

      {selected && data && (
        <FilingForm
          key={selected.ticker}
          item={selected}
          lines={data.lines}
          onClose={() => setSelected(null)}
        />
      )}

      {data && (
        <div className="table-container">
          <table className="radar-table">
            <thead>
              <tr>
                <th>{t("intake_col_company")}</th>
                <th>{t("intake_col_status")}</th>
                <th>{t("intake_col_target")}</th>
                <th>{t("intake_col_filed")}</th>
                <th>{t("intake_col_vendor")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.company_id}>
                  <td>
                    <Link to={`/companies/${item.ticker}/statements`} className="ticker-link">
                      {item.ticker}
                    </Link>
                    <div className="radar-name">{item.name}</div>
                    <div className="radar-shariah-stack">
                      {item.reasons.map((r) => (
                        <span key={r} className="radar-shariah radar-shariah-ok">
                          {t(REASON_KEY[r])}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <span className={STATUS_CLASS[item.status]}>{t(STATUS_KEY[item.status])}</span>
                  </td>
                  <td className="num" dir="ltr">
                    {item.target_year}
                  </td>
                  <td className="num" dir="ltr">
                    {item.filing_years.join(", ") || t("no_value")}
                  </td>
                  <td className="num" dir="ltr">
                    {item.vendor_years.join(", ") || t("no_value")}
                  </td>
                  <td>
                    <button type="button" className="link-btn" onClick={() => setSelected(item)}>
                      {t("intake_enter")}
                    </button>
                    {item.disclosure_url && (
                      <>
                        {" · "}
                        <a href={item.disclosure_url} target="_blank" rel="noreferrer">
                          {t("intake_disclosures")}
                        </a>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
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
  const { t, lang } = useLang();
  const queryClient = useQueryClient();
  const [fiscalYear, setFiscalYear] = useState(String(item.target_year));
  const [periodEnd, setPeriodEnd] = useState(`${item.target_year}-12-31`);
  const [documentUrl, setDocumentUrl] = useState("");
  const [publicationDate, setPublicationDate] = useState("");
  const [currency, setCurrency] = useState("EGP");
  const [inputs, setInputs] = useState<Record<string, LineInput>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<ManualFilingResponse | null>(null);

  const bySection = useMemo(() => {
    const groups: Record<IntakeLineDef["section"], IntakeLineDef[]> = {
      income: [],
      balance: [],
      cash_flow: [],
    };
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
    if (entered.some(([, v]) => v.page.trim() === "")) {
      setMessage(t("intake_need_page"));
      return;
    }
    setSaving(true);
    setMessage(null);
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
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card intake-form" onSubmit={submit}>
      <div className="intake-form-head">
        <h2>
          {t("intake_form_title")} · {item.ticker}
        </h2>
        <button type="button" className="link-btn" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="filters">
        <label>
          {t("intake_fiscal_year")}
          <input
            className="filter-input"
            type="number"
            required
            value={fiscalYear}
            onChange={(e) => setFiscalYear(e.target.value)}
          />
        </label>
        <label>
          {t("intake_period_end")}
          <input
            className="filter-input"
            type="date"
            required
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
          />
        </label>
        <label>
          {t("intake_publication_date")}
          <input
            className="filter-input"
            type="date"
            value={publicationDate}
            onChange={(e) => setPublicationDate(e.target.value)}
          />
        </label>
        <label>
          {t("intake_currency")}
          <input
            className="filter-input"
            maxLength={3}
            required
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          />
        </label>
      </div>
      <label className="intake-url">
        {t("intake_document_url")}
        <input
          className="filter-input"
          type="url"
          required
          placeholder="https://www.egx.com.eg/…"
          value={documentUrl}
          onChange={(e) => setDocumentUrl(e.target.value)}
        />
      </label>

      {(Object.keys(bySection) as IntakeLineDef["section"][]).map((section) => (
        <table key={section} className="statements-table">
          <caption>{t(SECTION_KEY[section])}</caption>
          <thead>
            <tr>
              <th scope="col">{t("col_line")}</th>
              <th scope="col">{t("intake_value")}</th>
              <th scope="col">{t("intake_page")}</th>
            </tr>
          </thead>
          <tbody>
            {bySection[section].map((line) => {
              const outcome = result?.lines.find((r) => r.code === line.code);
              return (
                <tr key={line.code}>
                  <td>
                    {lang === "ar" ? line.label_ar : line.label_en}
                    {outcome && (
                      <div className={outcome.status === "rejected" ? "intake-reject" : "muted"}>
                        {outcome.status}
                        {outcome.reason ? ` — ${outcome.reason}` : ""}
                      </div>
                    )}
                  </td>
                  <td>
                    <input
                      className="filter-input num"
                      dir="ltr"
                      inputMode="decimal"
                      value={inputs[line.code]?.value ?? ""}
                      onChange={(e) => setLine(line.code, { value: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="filter-input"
                      dir="ltr"
                      size={4}
                      value={inputs[line.code]?.page ?? ""}
                      onChange={(e) => setLine(line.code, { page: e.target.value })}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ))}

      {message && <div className="alert alert-error">{message}</div>}
      {result && <p className="muted">{t("intake_result")}: {result.lines.length}</p>}
      <button type="submit" className="btn btn-primary" disabled={saving}>
        {saving ? t("intake_saving") : t("intake_submit")}
      </button>
    </form>
  );
}
