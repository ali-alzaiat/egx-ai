import { useParams } from "react-router-dom";
import { useCompanyByTicker } from "../api/client";
import PeersTab from "../components/PeersTab";
import { LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";

/** Peers tab: the hub header already names the company, so this renders the content only. */
export default function Peers() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data: company } = useCompanyByTicker(ticker);

  if (!company) return <LoadingState thing={t("loading_company")} />;
  return <PeersTab companyId={company.id} ticker={company.ticker} />;
}
