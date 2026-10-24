import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useLang } from "../../i18n/useLang";
import { readStored, writeStored } from "../../lib/storage";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { SortIcon } from "./icons";

export type SortDir = "asc" | "desc";
export type SortValue = number | string | null | undefined;

export interface Column<T> {
  id: string;
  header: string;
  /** "num" cells are right-aligned, LTR, tabular. Default "text". */
  type?: "text" | "num";
  sortable?: boolean;
  /** CSS width, e.g. "96px". */
  width?: string;
  /** Sticks to the inline-start edge on horizontal scroll. */
  sticky?: boolean;
  cell: (row: T) => ReactNode;
  /** Optional leaner content for the phone card (e.g. percent change only). Defaults to `cell`. */
  cardCell?: (row: T) => ReactNode;
  /** Value to sort by; required when `sortable`. Null/undefined sort last. */
  sortValue?: (row: T) => SortValue;
}

export interface DataTableProps<T> {
  columns: readonly Column<T>[];
  rows: readonly T[];
  rowKey: (row: T) => string;
  /** Accessible name of the table. */
  caption: string;
  loading?: boolean;
  /** What is loading, for "Loading {thing}…". */
  loadingThing: string;
  /** Meta line above the table, e.g. "50 stocks · prices as of 22 Oct 2026". */
  meta?: ReactNode;
  /** Methodology and version footnote below the table. */
  footnote?: ReactNode;
  /** Shown instead of the table when there are no rows (and not loading). */
  empty?: ReactNode;
  /**
   * Below 768px each row renders as a card: the first column is line 1, then
   * these exactly four column ids as two label/value pairs per line.
   */
  cardFields?: readonly [string, string, string, string];
  /** Makes the whole card a link on narrow screens. */
  rowHref?: (row: T) => string | undefined;
  /** Order used until the reader sorts. */
  defaultSort?: { id: string; dir: SortDir };
  hideDensityToggle?: boolean;
}

const DENSITY_KEY = "egx-density";
const SKELETON_ROWS = 8;

function compare(a: SortValue, b: SortValue, dir: SortDir): number {
  const aMissing = a === null || a === undefined;
  const bMissing = b === null || b === undefined;
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1; // missing always last
  if (bMissing) return -1;
  const result = typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b));
  return dir === "asc" ? result : -result;
}

/** Descending, then ascending, then back to the default order (spec 3.4). */
function nextSort(current: { id: string; dir: SortDir } | null, id: string): { id: string; dir: SortDir } | null {
  if (!current || current.id !== id) return { id, dir: "desc" };
  if (current.dir === "desc") return { id, dir: "asc" };
  return null;
}

export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  loading = false,
  loadingThing,
  meta,
  footnote,
  empty,
  cardFields,
  rowHref,
  defaultSort,
  hideDensityToggle = false,
}: DataTableProps<T>) {
  const { t } = useLang();
  const [params, setParams] = useSearchParams();
  const narrow = useMediaQuery("(max-width: 767px)");
  const [compact, setCompact] = useState<boolean>(() => readStored(DENSITY_KEY) === "compact");

  const sortParam = params.get("sort");
  const dirParam = params.get("dir");
  const userSort =
    sortParam && columns.some((c) => c.id === sortParam && c.sortable)
      ? { id: sortParam, dir: (dirParam === "asc" ? "asc" : "desc") as SortDir }
      : null;
  const activeSort = userSort ?? defaultSort ?? null;
  const sortId = activeSort?.id;
  const sortDirection = activeSort?.dir;

  const sorted = useMemo(() => {
    if (!sortId || !sortDirection) return rows;
    const valueOf = columns.find((c) => c.id === sortId)?.sortValue;
    if (!valueOf) return rows;
    return [...rows].sort((a, b) => compare(valueOf(a), valueOf(b), sortDirection));
  }, [rows, columns, sortId, sortDirection]);

  const onSort = (id: string): void => {
    const next = nextSort(userSort, id);
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (next) {
          p.set("sort", next.id);
          p.set("dir", next.dir);
        } else {
          p.delete("sort");
          p.delete("dir");
        }
        return p;
      },
      { replace: true },
    );
  };

  const toggleDensity = (): void => {
    const next = !compact;
    setCompact(next);
    writeStored(DENSITY_KEY, next ? "compact" : "comfortable");
  };

  const cards = narrow && cardFields !== undefined;
  const showEmpty = !loading && rows.length === 0 && empty !== undefined;

  const toolbar = (
    <div className="table-toolbar">
      <div className="table-meta">{meta}</div>
      {!hideDensityToggle && !cards && (
        <button type="button" className="link-btn text-note" onClick={toggleDensity}>
          {compact ? t("table_density_comfortable") : t("table_density_compact")}
        </button>
      )}
    </div>
  );

  if (showEmpty) {
    return (
      <div>
        {toolbar}
        {empty}
      </div>
    );
  }

  if (cards && cardFields) {
    const lead = columns[0];
    const pairs = cardFields
      .map((id) => columns.find((c) => c.id === id))
      .filter((c): c is Column<T> => c !== undefined);
    return (
      <div aria-busy={loading}>
        {toolbar}
        {loading ? (
          <p className="loading" role="status">
            {t("loading_thing", { thing: loadingThing })}
          </p>
        ) : (
          <ul className="card-list" aria-label={caption}>
            {sorted.map((row) => {
              const href = rowHref?.(row);
              const body = (
                <Fragment>
                  {lead && <div>{lead.cell(row)}</div>}
                  <div className="card-pairs">
                    {pairs.map((col) => (
                      <div key={col.id} className="card-pair">
                        <span className="card-pair-label">{col.header}</span>
                        <span className="card-pair-value" {...(col.type === "num" ? { dir: "ltr" } : {})}>
                          {(col.cardCell ?? col.cell)(row)}
                        </span>
                      </div>
                    ))}
                  </div>
                </Fragment>
              );
              return (
                <li key={rowKey(row)} className="card-row">
                  {href ? (
                    <Link to={href} className="card-row-link">
                      {body}
                    </Link>
                  ) : (
                    body
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {footnote && <p className="table-footnote">{footnote}</p>}
      </div>
    );
  }

  return (
    <div aria-busy={loading}>
      {toolbar}
      <div className="table-wrap" data-density={compact ? "compact" : "comfortable"}>
        <table aria-label={caption}>
          <thead>
            <tr>
              {columns.map((col) => {
                const isNum = col.type === "num";
                const sortDir = activeSort?.id === col.id ? activeSort.dir : null;
                const className = [isNum ? "num" : "", col.sticky ? "col-sticky" : ""].filter(Boolean).join(" ");
                return (
                  <th
                    key={col.id}
                    scope="col"
                    className={className || undefined}
                    style={col.width ? { width: col.width } : undefined}
                    aria-sort={col.sortable ? (sortDir === "asc" ? "ascending" : sortDir === "desc" ? "descending" : "none") : undefined}
                    {...(isNum ? { dir: "ltr" } : {})}
                  >
                    {col.sortable ? (
                      <button
                        type="button"
                        className="th-sort"
                        onClick={() => onSort(col.id)}
                        title={t("table_sort_by", { col: col.header })}
                      >
                        <span>{col.header}</span>
                        <SortIcon size={12} sort={sortDir} />
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: SKELETON_ROWS }, (_, i) => (
                  <tr key={`sk-${i}`}>
                    {columns.map((col) => (
                      <td key={col.id} className={col.sticky ? "col-sticky" : undefined}>
                        <span className="skeleton-bar" />
                      </td>
                    ))}
                  </tr>
                ))
              : sorted.map((row) => (
                  <tr key={rowKey(row)}>
                    {columns.map((col) => {
                      const isNum = col.type === "num";
                      const className = [isNum ? "num" : "text-cell", col.sticky ? "col-sticky" : ""].filter(Boolean).join(" ");
                      return (
                        <td key={col.id} className={className} {...(isNum ? { dir: "ltr" } : {})}>
                          {col.cell(row)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
      {loading && (
        <p className="sr-only" role="status">
          {t("loading_thing", { thing: loadingThing })}
        </p>
      )}
      {footnote && <p className="table-footnote">{footnote}</p>}
    </div>
  );
}

/** Stock cell: "TICKER" with the name stacked beneath it, linking to the hub (spec 3.4, friendly look). */
export function StockCell({ ticker, name, href }: { ticker: string; name: ReactNode; href?: string }) {
  return (
    <span className="stock-cell">
      {href ? (
        <Link to={href} className="stock-ticker" dir="ltr">
          {ticker}
        </Link>
      ) : (
        <span className="stock-ticker" dir="ltr">
          {ticker}
        </span>
      )}
      <span className="stock-name">{name}</span>
    </span>
  );
}
