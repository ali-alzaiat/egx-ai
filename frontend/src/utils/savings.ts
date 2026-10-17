export function projectSavings(
  monthlyEgp: number,
  months: number,
  annualRatePct: number,
): { month: number; balance: number }[] {
  const monthlyRate = annualRatePct / 12 / 100;
  const out: { month: number; balance: number }[] = [];
  let balance = 0;
  for (let m = 1; m <= months; m++) {
    balance = balance * (1 + monthlyRate) + monthlyEgp;
    out.push({ month: m, balance: Number(balance.toFixed(2)) });
  }
  return out;
}
