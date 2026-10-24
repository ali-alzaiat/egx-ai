import { Link } from "react-router-dom";
import { useCompanyMetrics, useIndustrySnapshot, usePeersMetrics } from "../api/client";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtNum, fmtPct, fmtPrice, fmtRatio, plural } from "../lib/format";
import { metricValueKind } from "../lib/metricsView";
import { ForeignText } from "../pages/shared/ForeignText";
import type { FinancialMetric, IndustryPercentile, IndustryPeer, IndustrySnapshot } from "../types";
import { metricLabelKey, peerBasisKey } from "./research/labels";
import { ResearchSection, TechnicalDetails } from "./research/parts";
import { MissingReason } from "./research/reasons";
import DataTable, { StockCell, type Column } from "./ui/DataTable";
import { CompanyName } from "./ui/CompanyName";
import { ErrorState, LoadingState } from "./ui/States";

interface PeersTabProps {
  companyId: string;
  ticker?: string;
}

/** The newest stored value of each metric code, by period end. */
function latestByCode(metrics: readonly FinancialMetric[] | undefined): Map<string, FinancialMetric> {
  const out = new Map<string, FinancialMetric>();
  for (const m of metrics ?? []) {
    if (m.value === null) continue;
    const seen = out.get(m.metric_code);
    if (!seen || (m.period_end ?? "") > (seen.period_end ?? "")) out.set(m.metric_code, m);
  }
  return out;
}

function formatMetricValue(locale: string, m: FinancialMetric | undefined): string | null {
  if (!m || m.value === null) return null;
  switch (metricValueKind(m.unit)) {
    case "pct": {
      const n = Number(m.value);
      return Number.isFinite(n) ? fmtPct(locale, n / 100) : null;
    }
    case "perShare":
      return fmtPrice(locale, m.value);
    default: {
      const text = fmtRatio(locale, m.value);
      return text === null ? null : m.unit === "ratio" ? `${text}×` : text;
    }
  }
}

function BasisLine({ data }: { data: IndustrySnapshot }) {
  const { t, locale } = useLang();
  const key = peerBasisKey(data.peers.basis);
  const basis = key ? t(key) : data.peers.basis.replace(/_/g, " ");
  const count = plural(locale, data.n_peers, {
    zero: t("rp_count_zero"),
    one: t("rp_count_one"),
    two: t("rp_count_two"),
    few: t("rp_count_few"),
    many: t("rp_count_many"),
    other: t("rp_count_other"),
  });
  const date = fmtDate(locale, data.as_of);
  return (
    <p className="rs-lead">
      {t("rp_basis_line", { basis, count, asof: date !== null ? t("rs_as_of", { date }) : t("rs_no_data_reason") })}
    </p>
  );
}

function PeersTable({
  peers,
  metricKeys,
  metricsByPeer,
  loading,
}: {
  peers: IndustryPeer[];
  metricKeys: string[];
  metricsByPeer: Record<string, FinancialMetric[]> | undefined;
  loading: boolean;
}) {
  const { t, locale } = useLang();
  const columns: Column<IndustryPeer>[] = [
    {
      id: "stock",
      header: t("rp_col_stock"),
      sticky: true,
      cell: (peer) => (
        <StockCell
          ticker={peer.ticker}
          name={<CompanyName name={peer.name} />}
          href={`/companies/${encodeURIComponent(peer.ticker)}`}
        />
      ),
    },
    ...metricKeys.map((key) => ({
      id: key,
      header: ((label) => (label ? t(label) : key.replace(/_/g, " ")))(metricLabelKey(key)),
      type: "num" as const,
      cell: (peer: IndustryPeer) =>
        formatMetricValue(locale, latestByCode(metricsByPeer?.[peer.id]).get(key)) ?? <MissingReason reason={null} />,
    })),
  ];
  return (
    <ResearchSection title={t("rp_peers_title")}>
      <DataTable
        columns={columns}
        rows={peers}
        rowKey={(peer) => peer.id}
        caption={t("rp_peers_caption")}
        loading={loading}
        loadingThing={t("rp_thing")}
        hideDensityToggle
      />
    </ResearchSection>
  );
}

function PercentilesTable({
  rows,
  metrics,
}: {
  rows: IndustryPercentile[];
  metrics: Map<string, FinancialMetric>;
}) {
  const { t, locale } = useLang();
  const columns: Column<IndustryPercentile>[] = [
    {
      id: "metric",
      header: t("rs_col_metric"),
      sticky: true,
      cell: (row) => {
        const key = metricLabelKey(row.metric_key);
        return key ? t(key) : <ForeignText>{row.display_name}</ForeignText>;
      },
    },
    {
      id: "value",
      header: t("rp_col_value"),
      type: "num",
      cell: (row) => formatMetricValue(locale, metrics.get(row.metric_key)) ?? <MissingReason reason={null} />,
    },
    {
      id: "percentile",
      header: t("rp_col_percentile"),
      type: "num",
      cell: (row) => {
        const n = row.value === null || row.status === "INSUFFICIENT_DATA" ? null : Number(row.value);
        if (n === null || !Number.isFinite(n)) return <MissingReason reason={row.reason || row.explanation} />;
        return t("rp_pct_cell", {
          pct: fmtNum(locale, n, { maximumFractionDigits: 0 }),
          n: fmtNum(locale, row.n_with_data),
        });
      },
    },
  ];
  return (
    <ResearchSection title={t("rp_pct_title")} lead={t("rp_pct_lead")}>
      <div className="rs-wrap-table">
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.metric_key}
          caption={t("rp_pct_caption")}
          loadingThing={t("rp_thing")}
          empty={<p className="empty">{t("rp_pct_empty")}</p>}
          hideDensityToggle
        />
      </div>
    </ResearchSection>
  );
}

/** Default peers and percentiles, read-only (R43 #10). The peer list is edited in Admin. */
export default function PeersTab({ companyId, ticker }: PeersTabProps) {
  const { t, locale } = useLang();
  const { data, isLoading, error, refetch } = useIndustrySnapshot(companyId);
  const { data: metrics } = useCompanyMetrics(companyId);
  const peerIds = data?.peers.items.map((p) => p.id) ?? [];
  const peerMetrics = usePeersMetrics(peerIds);

  if (isLoading) return <LoadingState thing={t("rp_thing")} />;
  if (error || !data) return <ErrorState thing={t("rp_thing")} onRetry={() => void refetch()} />;

  const label = ticker ?? data.company.ticker;
  const hasSector = !!(data.company.sector ?? data.company.egx_sector ?? data.company.gics);
  const hasPeers = data.peers.items.length > 0;
  const asOf = fmtDate(locale, data.as_of);

  return (
    <div className="page">
      {hasPeers ? (
        <BasisLine data={data} />
      ) : (
        <p className="rs-lead">{hasSector ? t("rp_no_peers", { ticker: label }) : t("rp_no_sector", { ticker: label })}</p>
      )}

      {hasPeers && (
        <PeersTable
          peers={data.peers.items}
          metricKeys={data.profile.metric_keys}
          metricsByPeer={peerMetrics.data}
          loading={peerMetrics.isLoading}
        />
      )}
      {hasPeers && <PercentilesTable rows={data.percentiles} metrics={latestByCode(metrics)} />}

      <footer className="rs-stack">
        <Link className="rs-text-link" to={`/admin/peers?ticker=${encodeURIComponent(label)}`}>
          {t("rp_admin_link")}
        </Link>
        <p className="rs-note">
          {t("rs_methodology", { version: data.methodology_version })}
          {asOf !== null && ` · ${t("rs_as_of", { date: asOf })}`}
        </p>
        <TechnicalDetails>
          <span>{`profile = ${data.profile.profile_id} (${data.profile.methodology_version})`}</span>
          <span>{`basis = ${data.peers.basis}`}</span>
          <span>{`metric_keys = ${data.profile.metric_keys.join(", ")}`}</span>
        </TechnicalDetails>
      </footer>
    </div>
  );
}
