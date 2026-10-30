import type { ReactNode } from "react";
import { useLang } from "../../i18n/useLang";

/** h1 at --fs-h1 (--fs-h2 on phone), optional one-sentence subtitle, optional actions at inline-end (spec 3.2). */
export function PageHeader({
  title,
  subtitle,
  actions,
  pricesAsOf,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  /** Already-formatted date of the latest stored prices; renders "Prices as of <date>" under the subtitle (R47 Q3). */
  pricesAsOf?: string | null;
}) {
  const { t } = useLang();
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
        {pricesAsOf && <p className="page-header-asof">{t("rx_prices_as_of", { date: pricesAsOf })}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  );
}
