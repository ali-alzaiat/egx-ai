import { useMemo } from "react";
import { useCompanies } from "../../api/client";
import type { Company } from "../../types";

/**
 * Every company keyed by id, so alerts, events and entries can show a ticker
 * and name instead of an id. Two pages of 200 cover the ~200-company universe;
 * the queries are the same ones other pages already cache.
 */
export function useCompanyIndex(): { byId: ReadonlyMap<string, Company>; loading: boolean } {
  const page1 = useCompanies({ page_size: 200 });
  const page2 = useCompanies({ page_size: 200, page: 2 });
  const first = page1.data;
  const second = page2.data;
  const byId = useMemo(() => {
    const map = new Map<string, Company>();
    for (const page of [first, second]) {
      for (const c of page?.items ?? []) if (!map.has(c.id)) map.set(c.id, c);
    }
    return map;
  }, [first, second]);
  return { byId, loading: first === undefined && second === undefined };
}
