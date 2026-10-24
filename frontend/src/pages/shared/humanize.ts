/** "net_profit_margin" -> "Net profit margin". For backend codes with no localized label yet. */
export function humanizeCode(code: string): string {
  const spaced = code.replace(/[_.-]+/g, " ").trim();
  return spaced === "" ? code : spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
