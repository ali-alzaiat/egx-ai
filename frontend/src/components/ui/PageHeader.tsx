import type { ReactNode } from "react";

/** h1 at --fs-h1 (--fs-h2 on phone), optional one-sentence subtitle, optional actions at inline-end (spec 3.2). */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  );
}
