/**
 * Money for the demo, mirroring `pricing/money.py`.
 *
 * The real engine parses rates out of Excel cells, which is where its
 * ambiguity rules live ("1.250" is refused, not guessed). The demo's rates
 * are literal strings authored by hand, so none of that parsing applies —
 * what carries over is the part that protects the arithmetic: every rate
 * becomes an exact Decimal, calculations run at full precision, and the
 * result is rounded exactly once, half-up, at the very end.
 *
 * A JavaScript number never touches a rate.
 */
import Decimal from "decimal.js";

Decimal.set({ precision: 40, rounding: Decimal.ROUND_HALF_UP });

export { Decimal };

export class RateError extends Error {}

/** Turn an authored rate string into an exact Decimal. */
export function money(rate: string): Decimal {
  let value: Decimal;
  try {
    value = new Decimal(rate);
  } catch {
    throw new RateError(`not a rate: ${JSON.stringify(rate)}`);
  }
  if (!value.isFinite()) {
    throw new RateError(`not a rate: ${JSON.stringify(rate)}`);
  }
  return value;
}

/** Round to cents. Called once, at the end of a calculation. */
export function roundMoney(value: Decimal): string {
  return value.toFixed(2, Decimal.ROUND_HALF_UP);
}
