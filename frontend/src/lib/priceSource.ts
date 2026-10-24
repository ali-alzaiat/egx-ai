/** Display name for a price data source (`DataSource.name` is an internal code like YAHOO_FINANCE_EGX). */
export function priceSourceLabel(name: string | null | undefined): string | null {
  if (!name) return null;
  if (/^YAHOO/i.test(name)) return "Yahoo Finance";
  const words = name.replace(/_/g, " ").trim().toLowerCase();
  return words === "" ? null : words.replace(/(^|\s)\S/g, (c) => c.toUpperCase());
}
