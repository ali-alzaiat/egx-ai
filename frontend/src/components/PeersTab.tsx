import "./PeersTab.css";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { putPeerOverride, useIndustrySnapshot } from "../api/client";
import { formatAsOf } from "../lib/format";
import type { IndustryPercentile } from "../types";

interface PeersTabProps {
  companyId: string;
  ticker?: string;
}

const BASIS_LABELS: Record<string, string> = {
  override: "Custom override",
  egx_sector: "EGX sector",
  gics_sub_industry: "GICS sub-industry",
  none: "No peer basis found",
};

function PercentileRow({ row }: { row: IndustryPercentile }) {
  const insufficient =
    row.status === "INSUFFICIENT_DATA" || row.value === null;
  const pct = insufficient ? 0 : Math.min(100, Math.max(0, Number(row.value)));
  return (
    <div className="peers-metric" key={row.metric_key}>
      <div className="peers-metric-head">
        <span>{row.display_name}</span>
        {insufficient ? (
          <span className="status-badge unknown">Not enough data</span>
        ) : (
          <span>{Number(row.value).toFixed(2)}th percentile</span>
        )}
      </div>
      {insufficient ? (
        <p className="muted">{row.explanation}</p>
      ) : (
        <>
          <div
            className="peers-bar"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${row.display_name}: ${Number(row.value).toFixed(2)}th percentile among ${row.n_with_data} companies with data`}
          >
            <div className="peers-bar-fill" style={{ width: `${pct}%` }} />
          </div>
          <p className="muted">{row.explanation}</p>
        </>
      )}
    </div>
  );
}

export default function PeersTab({ companyId, ticker }: PeersTabProps) {
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useIndustrySnapshot(companyId);

  const [idsText, setIdsText] = useState("");
  const [edited, setEdited] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const peerIds = data ? data.peers.items.map((p) => p.id).join(", ") : "";
  useEffect(() => {
    if (!edited) setIdsText(peerIds);
  }, [edited, peerIds]);

  const handleSave = async (): Promise<void> => {
    if (!data) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const ids = idsText
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
      await putPeerOverride(companyId, ids);
      setEdited(false);
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: ["industry", companyId] });
      await refetch();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return <div className="loading">Loading industry peers...</div>;
  }

  if (error || !data) {
    return (
      <div className="alert alert-error">
        Couldn't load industry peers.{" "}
        <button className="link-btn" onClick={() => refetch()}>
          Retry
        </button>
      </div>
    );
  }

  const gicsName =
    data.company.gics?.sub_industry_name ??
    data.company.gics?.industry_name ??
    null;
  const basisLabel = BASIS_LABELS[data.peers.basis] ?? data.peers.basis;

  return (
    <div className="peers-tab">
      <div className="card">
        <h2>Industry</h2>
        <p>
          Sector: {data.company.sector ?? "—"}
          {" · "}EGX sector: {data.company.egx_sector ?? "—"}
          {gicsName ? ` · GICS: ${gicsName}` : ""}
        </p>
        <p className="muted">
          Peer basis: {basisLabel} · {data.n_peers}{" "}
          {data.n_peers === 1 ? "peer" : "peers"} · as of{" "}
          {formatAsOf(data.as_of)}
        </p>
      </div>

      <div className="card">
        <h2>Peers</h2>
        {data.peers.items.length === 0 ? (
          <p className="muted">
            No peers resolved for {ticker ?? data.company.ticker} under the
            current basis. Percentiles below will show as not enough data.
          </p>
        ) : (
          <ul className="peers-chips" aria-label="Peer companies">
            {data.peers.items.map((peer) => (
              <li className="peers-chip" key={peer.id} title={peer.name}>
                {peer.ticker}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card">
        <h2>Percentiles</h2>
        <p className="muted">
          Each metric is ranked against the peer set above — potentially
          informative under these assumptions, not advice.
        </p>
        {data.percentiles.length === 0 ? (
          <p className="muted">
            No metrics in profile '{data.profile.profile_id}' for this peer
            set.
          </p>
        ) : (
          data.percentiles.map((row) => (
            <PercentileRow row={row} key={row.metric_key} />
          ))
        )}
      </div>

      <div className="card">
        <h2>Edit peer list</h2>
        <p className="muted">
          Paste company IDs (comma-separated UUIDs). Saving persists the
          override and recomputes the percentiles above.
        </p>
        <label className="peers-editor-label" htmlFor="peers-ids">
          Peer company IDs
        </label>
        <textarea
          id="peers-ids"
          className="peers-editor"
          rows={3}
          value={idsText}
          onChange={(e) => {
            setIdsText(e.target.value);
            setEdited(true);
            setSaved(false);
          }}
        />
        {saveError ? (
          <div className="alert alert-error">
            {saveError}{" "}
            <button className="link-btn" onClick={handleSave}>
              Retry
            </button>
          </div>
        ) : null}
        {saved ? (
          <p className="peers-saved" role="status">
            Peer override saved — percentiles recomputed.
          </p>
        ) : null}
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save peer list"}
        </button>
      </div>

      <p className="muted">
        Methodology v{data.methodology_version} · profile{" "}
        {data.profile.profile_id} (v{data.profile.methodology_version}) · as of{" "}
        {formatAsOf(data.as_of)}
      </p>
    </div>
  );
}
