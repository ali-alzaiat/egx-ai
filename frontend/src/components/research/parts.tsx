import "./research.css";

import type { ReactNode } from "react";
import { useLang } from "../../i18n/useLang";
import { Tag } from "../ui/Badges";
import { ExternalLinkIcon } from "../ui/icons";

/** "Provisional (vendor data)" tag, shown wherever a vendor line fed a number (R43 AC-4). */
export function ProvisionalTag() {
  const { t } = useLang();
  return <Tag title={t("rs_provisional_title")}>{t("rs_provisional")}</Tag>;
}

/** A titled block of a research tab. The heading is the section's accessible name. */
export function ResearchSection({
  id,
  title,
  lead,
  aside,
  children,
}: {
  id?: string;
  title: string;
  lead?: ReactNode;
  /** Small content at the heading's inline-end (tags, selectors). */
  aside?: ReactNode;
  children: ReactNode;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section id={id} className="rs-section" aria-labelledby={headingId}>
      <div className="rs-section-head">
        <h2 id={headingId} className="section-title">
          {title}
        </h2>
        {aside && <div className="rs-aside">{aside}</div>}
      </div>
      {lead && <p className="rs-lead">{lead}</p>}
      {children}
    </section>
  );
}

/** Raw keys, versions and assumption strings live here only (spec 3.10). Collapsed by default. */
export function TechnicalDetails({ children }: { children: ReactNode }) {
  const { t } = useLang();
  return (
    <details className="rs-details">
      <summary>{t("rs_technical_details")}</summary>
      <div className="rs-details-body" dir="ltr" lang="en">
        {children}
      </div>
    </details>
  );
}

/** http(s)-only URL guard: backend-supplied hrefs never become `javascript:` links. */
export function isHttpUrl(url: string | null | undefined): url is string {
  return !!url && /^https?:\/\//i.test(url);
}

/** External link with an icon; renders plain text when the URL is not http(s). */
export function ExternalLink({ href, children }: { href: string | null | undefined; children: ReactNode }) {
  if (!isHttpUrl(href)) return <>{children}</>;
  return (
    <a className="rs-link" href={href} target="_blank" rel="noreferrer noopener">
      {children}
      <ExternalLinkIcon size={14} />
    </a>
  );
}
