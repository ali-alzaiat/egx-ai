import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { putPeerOverride, useIndustrySnapshot } from "../../api/client";
import { Tag } from "../../components/ui/Badges";
import CompanySearch from "../../components/ui/CompanySearch";
import { CloseIcon } from "../../components/ui/icons";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States";
import { useLang } from "../../i18n/useLang";
import type { Company, IndustryPeer } from "../../types";
import { describeError, type ErrorView } from "../shared/apiError";
import { FieldGroup } from "../shared/Field";
import { ErrorMessage, FormMessage } from "../shared/FormMessage";
import { addPeer, peersChanged, removePeer, type PeerIssue } from "./adminFormat";

const BASIS_KEY = {
  override: "adm_basis_override",
  egx_sector: "adm_basis_egx_sector",
  gics_sub_industry: "adm_basis_gics",
  none: "adm_basis_none",
} as const;

/** Peer override for one company: removable ticker chips, an "Add peer" picker, Save. Ids stay out of sight. */
export default function AdminPeers({ company }: { company: Company }) {
  const { t } = useLang();
  const queryClient = useQueryClient();
  const snapshot = useIndustrySnapshot(company.id);
  const [draft, setDraft] = useState<IndustryPeer[] | null>(null);
  const [issue, setIssue] = useState<PeerIssue | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);
  const [saved, setSaved] = useState(false);

  if (snapshot.isLoading) return <LoadingState thing={t("adm_things_peers")} />;
  if (snapshot.isError || !snapshot.data) {
    return <ErrorState thing={t("adm_things_peers")} onRetry={() => void snapshot.refetch()} />;
  }

  const current = snapshot.data.peers.items;
  const peers = draft ?? current;
  const dirty = draft !== null && peersChanged(current, draft);
  const basis = snapshot.data.peers.basis;
  const basisKey = basis in BASIS_KEY ? BASIS_KEY[basis as keyof typeof BASIS_KEY] : null;

  const add = (picked: Company): void => {
    const next = addPeer(peers, company.id, picked);
    setIssue(next.issue);
    setSaved(false);
    if (next.issue === null) setDraft(next.draft);
  };

  const remove = (id: string): void => {
    setIssue(null);
    setSaved(false);
    setDraft(removePeer(peers, id));
  };

  const save = async (): Promise<void> => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await putPeerOverride(company.id, peers.map((p) => p.id));
      await queryClient.invalidateQueries({ queryKey: ["industry", company.id] });
      setDraft(null);
      setSaved(true);
    } catch (err) {
      setError(describeError(err, t, "adm_peers_failed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="card panel" aria-label={t("admin_peers")}>
      <h2 className="section-title">{t("adm_peers_title", { ticker: company.ticker })}</h2>
      <p className="panel-lead">
        {t("adm_peers_basis")} {basisKey ? t(basisKey) : t("adm_basis_unknown")}
      </p>

      {peers.length === 0 ? (
        <EmptyState>{t("adm_peers_empty")}</EmptyState>
      ) : (
        <ul className="adm-chips" aria-label={t("adm_peers_list")}>
          {peers.map((peer) => (
            <li key={peer.id}>
              <Tag title={peer.name}>
                <bdi dir="ltr">{peer.ticker}</bdi>
                <button
                  type="button"
                  className="adm-chip-remove"
                  aria-label={t("adm_peer_remove", { ticker: peer.ticker })}
                  onClick={() => remove(peer.id)}
                >
                  <CloseIcon size={12} />
                </button>
              </Tag>
            </li>
          ))}
        </ul>
      )}

      <div className="adm-narrow">
        <FieldGroup label={t("adm_peer_add")}>
          <CompanySearch mode="picker" value={null} onSelect={add} onClear={() => undefined} />
        </FieldGroup>
      </div>
      {issue && <FormMessage kind="error" text={t(issue === "self" ? "adm_peer_self" : "adm_peer_duplicate")} />}
      {error && <ErrorMessage view={error} />}
      {saved && <FormMessage kind="success" text={t("adm_saved")} />}
      <div>
        <button type="button" className="btn btn-primary" disabled={saving || !dirty} onClick={() => void save()}>
          {saving ? t("adm_saving") : t("adm_peers_save")}
        </button>
      </div>
    </section>
  );
}
