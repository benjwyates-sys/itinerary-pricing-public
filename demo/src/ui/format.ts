import type { Currency, Money } from "../engine/types";
import { MONTHS, formatDate } from "../shared/dates";

export { formatDate, formatDayMonth, formatWeekday } from "../shared/dates";

const SYMBOL: Record<Currency, string> = { EUR: "€", GBP: "£", CHF: "CHF ", CZK: "" };

/**
 * Format from the exact decimal string rather than a number, so a total can
 * never drift between what was calculated and what is shown.
 */
export function formatMoney(currency: Currency, amount: Money): string {
  const negative = amount.startsWith("-");
  const [whole, cents = "00"] = amount.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const body = `${negative ? "-" : ""}${grouped}.${cents}`;
  return currency === "CZK" ? `${body} Kč` : `${SYMBOL[currency]}${body}`;
}

export function formatRange(from: string, to: string): string {
  const [fy, fm, fd] = from.split("-").map(Number);
  const [ty, tm, td] = to.split("-").map(Number);
  if (fy === ty && fm === tm) return `${fd}–${td} ${MONTHS[fm - 1]} ${fy}`;
  if (fy === ty) return `${fd} ${MONTHS[fm - 1]} – ${td} ${MONTHS[tm - 1]} ${fy}`;
  return `${formatDate(from)} – ${formatDate(to)}`;
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}


