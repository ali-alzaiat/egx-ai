import { useMemo, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { parseFiling, registerFiling, uploadFiling, useFacts, useFilings } from "../../api/client";
import { Tag } from "../../components/ui/Badges";
import DataTable, { type Column } from "../../components/ui/DataTable";
import { ExternalLinkIcon } from "../../components/ui/icons";
import { EmptyState, ErrorState } from "../../components/ui/States";
import { useLang } from "../../i18n/useLang";
import { fmtDate } from "../../lib/format";
import type { Company, DisclosureFiling } from "../../types";
import { describeError, type ErrorView } from "../shared/apiError";
import { Field } from "../shared/Field";
import { ErrorMessage, FormMessage } from "../shared/FormMessage";
import {
  ACCOUNTING_BASES,
  FILING_TYPES,
  FILING_TYPE_KEY,
  enumLabel,
  filingParseState,
  optionalFields,
  parseOutcome,
  shortUrl,
  type ParseState,
} from "./adminFormat";

interface Notice {
  text: string;
  detail?: string | null;
}

const PARSE_TAG: Record<ParseState, "adm_parse_parsed" | "adm_parse_none" | "adm_parse_reference"> = {
  parsed: "adm_parse_parsed",
  no_facts: "adm_parse_none",
  reference: "adm_parse_reference",
};

function TypeBasisFields({
  type,
  basis,
  onType,
  onBasis,
}: {
  type: string;
  basis: string;
  onType: (v: string) => void;
  onBasis: (v: string) => void;
}) {
  const { t } = useLang();
  return (
    <>
      <Field label={t("adm_filing_type")}>
        <select value={type} onChange={(e) => onType(e.target.value)}>
          <option value="">{t("adm_server_default")}</option>
          {FILING_TYPES.map((v) => (
            <option key={v} value={v}>
              {enumLabel(v, FILING_TYPE_KEY, t)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("adm_basis")}>
        <select value={basis} onChange={(e) => onBasis(e.target.value)}>
          <option value="">{t("adm_server_default")}</option>
          {ACCOUNTING_BASES.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}

/** Register a filing by URL. Optional fields sit under "More details". */
function RegisterForm({ company, onDone }: { company: Company; onDone: () => Promise<void> }) {
  const { t } = useLang();
  const [url, setUrl] = useState("");
  const [date, setDate] = useState("");
  const [bulletin, setBulletin] = useState("");
  const [type, setType] = useState("");
  const [basis, setBasis] = useState("");
  const [hash, setHash] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const res = await registerFiling({
        company_id: company.id,
        filing_url: url.trim(),
        report_date: date,
        ...optionalFields({ bulletin_id: bulletin, filing_type: type, accounting_basis: basis, content_hash: hash }),
      });
      await onDone();
      setOk(res.created ? t("adm_registered") : t("adm_already_registered"));
      if (res.created) setUrl("");
    } catch (err) {
      setError(describeError(err, t, "adm_register_failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card panel" onSubmit={(e) => void submit(e)}>
      <h3>{t("adm_register_title")}</h3>
      <p className="panel-lead">{t("adm_register_lead")}</p>
      <div className="fld-row">
        <Field label={t("adm_filing_url")}>
          <input type="url" dir="ltr" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" />
        </Field>
        <Field label={t("adm_report_date")}>
          <input type="date" dir="ltr" required value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
      </div>
      <details className="fold">
        <summary>{t("adm_more_details")}</summary>
        <div className="fold-body">
          <div className="fld-row">
            <TypeBasisFields type={type} basis={basis} onType={setType} onBasis={setBasis} />
            <Field label={t("adm_bulletin")}>
              <input dir="ltr" value={bulletin} onChange={(e) => setBulletin(e.target.value)} />
            </Field>
            <Field label={t("adm_hash")}>
              <input dir="ltr" value={hash} onChange={(e) => setHash(e.target.value)} />
            </Field>
          </div>
        </div>
      </details>
      {error && <ErrorMessage view={error} />}
      {ok && <FormMessage kind="success" text={ok} />}
      <div>
        <button type="submit" className="btn btn-primary" disabled={busy || url.trim() === "" || date === ""}>
          {busy ? t("adm_registering") : t("adm_register")}
        </button>
      </div>
    </form>
  );
}

/** Upload a PDF; the server parses it straight away (R43 #11). */
function UploadForm({ company, onDone }: { company: Company; onDone: () => Promise<void> }) {
  const { t } = useLang();
  const [file, setFile] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [date, setDate] = useState("");
  const [bulletin, setBulletin] = useState("");
  const [type, setType] = useState("");
  const [basis, setBasis] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const form = new FormData();
      form.set("company_id", company.id);
      form.set("file", file);
      form.set("report_date", date);
      for (const [key, value] of Object.entries(
        optionalFields({ bulletin_id: bulletin, filing_type: type, accounting_basis: basis }),
      )) {
        form.set(key, value);
      }
      const res = await uploadFiling(form);
      await onDone();
      const outcome = parseOutcome(res);
      const base = res.created ? t("adm_uploaded") : t("adm_already_stored");
      if (outcome.status === "ok") {
        setNotice({ text: `${base} ${t("adm_parsed_facts", { n: outcome.facts })}` });
      } else if (outcome.status === "failed") {
        setNotice({ text: `${base} ${t("adm_parse_no_facts")}`, detail: outcome.reason });
      } else {
        setNotice({ text: base });
      }
      setFile(null);
      setFileKey((k) => k + 1);
    } catch (err) {
      setError(describeError(err, t, "adm_upload_failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card panel" onSubmit={(e) => void submit(e)}>
      <h3>{t("adm_upload_title")}</h3>
      <p className="panel-lead">{t("adm_upload_lead")}</p>
      <div className="fld-row">
        <Field label={t("adm_file")}>
          <input
            key={fileKey}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field>
        <Field label={t("adm_report_date")}>
          <input type="date" dir="ltr" required value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
      </div>
      <details className="fold">
        <summary>{t("adm_more_details")}</summary>
        <div className="fold-body">
          <div className="fld-row">
            <TypeBasisFields type={type} basis={basis} onType={setType} onBasis={setBasis} />
            <Field label={t("adm_bulletin")}>
              <input dir="ltr" value={bulletin} onChange={(e) => setBulletin(e.target.value)} />
            </Field>
          </div>
        </div>
      </details>
      {error && <ErrorMessage view={error} />}
      {notice && <FormMessage kind="success" text={notice.text} detail={notice.detail} />}
      <div>
        <button type="submit" className="btn btn-primary" disabled={busy || !file || date === ""}>
          {busy ? t("adm_uploading") : t("adm_upload")}
        </button>
      </div>
    </form>
  );
}

/** Disclosures admin for one company: registry, then register and upload. */
export default function AdminDisclosures({ company }: { company: Company }) {
  const { t, locale } = useLang();
  const queryClient = useQueryClient();
  const filings = useFilings(company.id);
  const facts = useFacts(company.id);
  const [parsingId, setParsingId] = useState<string | null>(null);
  const [parseNotice, setParseNotice] = useState<Notice | null>(null);
  const [parseError, setParseError] = useState<ErrorView | null>(null);

  const refresh = async (): Promise<void> => {
    for (const key of ["filings", "facts", "comparison", "diffs"]) {
      await queryClient.invalidateQueries({ queryKey: [key] });
    }
  };

  const parseAgain = async (filing: DisclosureFiling): Promise<void> => {
    setParsingId(filing.id);
    setParseError(null);
    setParseNotice(null);
    try {
      const res = await parseFiling(filing.id, {});
      await refresh();
      const outcome = parseOutcome({ parse: res });
      setParseNotice(
        outcome.status === "ok"
          ? { text: t("adm_parsed_facts", { n: outcome.facts }) }
          : { text: t("adm_parse_no_facts"), detail: outcome.reason },
      );
    } catch (err) {
      setParseError(describeError(err, t, "adm_parse_failed"));
    } finally {
      setParsingId(null);
    }
  };

  const factRows = useMemo(() => facts.data ?? [], [facts.data]);
  const columns = useMemo<Column<DisclosureFiling>[]>(
    () => [
      {
        id: "source",
        header: t("adm_col_source"),
        sticky: true,
        cell: (f) => (
          <a href={f.filing_url} target="_blank" rel="noreferrer" dir="ltr" title={f.filing_url}>
            {shortUrl(f.filing_url)} <ExternalLinkIcon size={12} />
          </a>
        ),
      },
      {
        id: "date",
        header: t("adm_report_date"),
        type: "num",
        sortable: true,
        sortValue: (f) => f.report_date,
        cell: (f) => fmtDate(locale, f.report_date) ?? t("no_value"),
      },
      {
        id: "type",
        header: t("adm_filing_type"),
        cell: (f) => enumLabel(f.filing_type, FILING_TYPE_KEY, t),
      },
      { id: "basis", header: t("adm_basis"), cell: (f) => <bdi dir="ltr">{f.accounting_basis}</bdi> },
      {
        id: "stored",
        header: t("adm_col_stored"),
        cell: (f) => <Tag>{f.has_bytes ? t("adm_stored") : t("adm_reference_only")}</Tag>,
      },
      {
        id: "parse",
        header: t("adm_col_parse"),
        cell: (f) => <Tag>{t(PARSE_TAG[filingParseState(f, factRows)])}</Tag>,
      },
      {
        id: "action",
        header: t("adm_col_action"),
        cell: (f) =>
          filingParseState(f, factRows) === "no_facts" ? (
            <button
              type="button"
              className="link-btn"
              disabled={parsingId === f.id}
              onClick={() => void parseAgain(f)}
            >
              {parsingId === f.id ? t("adm_parsing") : t("adm_parse_again")}
            </button>
          ) : null,
      },
    ],
    // parseAgain only closes over setters and the query client.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, locale, factRows, parsingId],
  );

  return (
    <div className="adm-stack">
      <section className="adm-stack" aria-label={t("adm_registry")}>
        <h2 className="section-title">{t("adm_registry")}</h2>
        {filings.isError ? (
          <ErrorState thing={t("adm_things_filings")} onRetry={() => void filings.refetch()} />
        ) : (
          <DataTable
            columns={columns}
            rows={filings.data ?? []}
            rowKey={(f) => f.id}
            caption={t("adm_registry")}
            loading={filings.isLoading}
            loadingThing={t("adm_things_filings")}
            defaultSort={{ id: "date", dir: "desc" }}
            empty={<EmptyState>{t("adm_registry_empty", { ticker: company.ticker })}</EmptyState>}
            hideDensityToggle
          />
        )}
        {parseError && <ErrorMessage view={parseError} />}
        {parseNotice && <FormMessage kind="success" text={parseNotice.text} detail={parseNotice.detail} />}
      </section>
      <RegisterForm company={company} onDone={refresh} />
      <UploadForm company={company} onDone={refresh} />
    </div>
  );
}
