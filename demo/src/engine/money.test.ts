import { describe, expect, test } from "vitest";
import { Decimal, money, roundMoney } from "./money";

describe("roundMoney", () => {
  test("rounds to two decimal places", () => {
    expect(roundMoney(new Decimal("100.489950"))).toBe("100.49");
  });

  test("rounds a half up, not to even", () => {
    // Banker's rounding would give 2.34 here. The Python engine uses
    // ROUND_HALF_UP and the quoted number has to agree with it.
    expect(roundMoney(new Decimal("2.345"))).toBe("2.35");
    expect(roundMoney(new Decimal("2.355"))).toBe("2.36");
  });

  test("rounds a negative half away from zero", () => {
    expect(roundMoney(new Decimal("-2.345"))).toBe("-2.35");
  });

  test("keeps trailing zeroes so a total never reads as an integer", () => {
    expect(roundMoney(new Decimal("180"))).toBe("180.00");
  });
});

describe("money", () => {
  test("builds an exact decimal from a string rate", () => {
    expect(money("0.1").plus(money("0.2")).toString()).toBe("0.3");
  });

  test("refuses a rate that is not a number", () => {
    expect(() => money("on request")).toThrow(/not a rate/i);
  });
});
