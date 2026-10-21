/**
 * All of the demo's state: which wordings the consultant has confirmed, which
 * lines she has sent for a supplier quote, any figures she typed in herself,
 * and the quotes she has finished this session.
 *
 * Everything lives in one namespaced localStorage key so "Reset demo" is a
 * single removal. That control is not decoration — the demo gets run
 * repeatedly in front of people, and a half-finished previous run makes it
 * look broken.
 */
import { useMemo } from "react";
import { create } from "zustand";
import { CATALOG } from "../data/catalog";
import { SAMPLE_TRIPS } from "../data/trips";
import { costTrip, resolveLine } from "../engine/cost";
import { Aliases, type AliasEntry } from "../engine/match";
import { tripMoney } from "../itinerary/build";
import type { CostedTrip, Currency, Money, Trip } from "../engine/types";

const STORAGE_KEY = "costing-demo.v1";

export type Screen = "price" | "preview" | "review" | "costed" | "quotes" | "admin";

export type SavedQuote = {
  id: string;
  tripId: string;
  title: string;
  client: string;
  fileName: string;
  savedAt: string;
  currency: Currency;
  total: Money;
  /** What the consultant typed in herself, kept apart from the rate-sheet total. */
  ownTotal: Money | null;
  lines: number;
  nights: number;
  /** Kept apart on purpose: one is a pick to make, the other is an email to send. */
  awaitingDecision: number;
  awaitingSupplier: number;
  seeded: boolean;
};

export type Session = {
  tripId: string;
  /** Lines the consultant answered "neither" to. */
  declined: string[];
  /**
   * lineId → an amount she entered herself, on any line. Never a rate-sheet
   * price: overriding one moves that money out of the rate sheet's total and
   * into hers, and the original stays visible so the change can be seen.
   */
  ownPrices: Record<string, Money>;
};

/** A few past quotes so "My quotes" is not empty on a first visit. */
const SEEDED: SavedQuote[] = [
  {
    id: "seed-1", tripId: "", title: "Ashworth party — Lisbon & Porto",
    client: "Ashworth party", fileName: "Trip_Ashworth_Portugal.xlsx",
    savedAt: "2026-04-22T09:41:00Z", currency: "EUR", total: "11480.00",
    ownTotal: null, lines: 14, nights: 8, awaitingDecision: 0, awaitingSupplier: 0, seeded: true,
  },
  {
    id: "seed-2", tripId: "", title: "Delacroix party — Paris",
    client: "Delacroix party", fileName: "Trip_Delacroix_Paris.xlsx",
    savedAt: "2026-03-14T14:08:00Z", currency: "EUR", total: "18240.00",
    ownTotal: "850.00", lines: 12, nights: 6, awaitingDecision: 0, awaitingSupplier: 1, seeded: true,
  },
  {
    id: "seed-3", tripId: "", title: "Ferreira party — Seville",
    client: "Ferreira party", fileName: "Trip_Ferreira_Seville.xlsx",
    savedAt: "2026-02-27T11:20:00Z", currency: "EUR", total: "7950.00",
    ownTotal: null, lines: 9, nights: 5, awaitingDecision: 0, awaitingSupplier: 0, seeded: true,
  },
];

type Persisted = {
  aliases: Record<string, AliasEntry>;
  quotes: SavedQuote[];
  session: Session | null;
};

function load(): Persisted {
  const empty: Persisted = { aliases: {}, quotes: SEEDED, session: null };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return empty;
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      aliases: Aliases.fromJSON(parsed.aliases).entries,
      quotes: Array.isArray(parsed.quotes) ? parsed.quotes : SEEDED,
      session: parsed.session ?? null,
    };
  } catch {
    // A corrupted key must not brick the demo mid-walkthrough.
    return empty;
  }
}

function save(state: Persisted) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Private browsing, quota, blocked storage — the demo still works, it
    // just forgets between reloads. Never worth an error in front of anyone.
  }
}

type Store = Persisted & {
  screen: Screen;
  resolving: string | null;
  go: (screen: Screen) => void;
  start: (tripId: string) => void;
  openResolve: (lineId: string) => void;
  closeResolve: () => void;
  confirmMatch: (lineId: string, itemId: string | null) => void;
  /** Pass null to drop an override and go back to the rate sheet's price. */
  enterOwnPrice: (lineId: string, amount: Money | null) => void;
  saveQuote: () => void;
  resetDemo: () => void;
};

export const useDemo = create<Store>((set, get) => {
  const initial = load();

  const persist = () => {
    const { aliases, quotes, session } = get();
    save({ aliases, quotes, session });
  };

  return {
    ...initial,
    screen: "price",
    resolving: null,

    go: (screen) => set({ screen }),

    start: (tripId) => {
      // The trip opens unpriced, so the costed version has something to be
      // compared against a moment later.
      set({ session: { tripId, declined: [], ownPrices: {} }, screen: "preview", resolving: null });
      persist();
    },

    openResolve: (lineId) => set({ resolving: lineId }),
    closeResolve: () => set({ resolving: null }),

    confirmMatch: (lineId, itemId) => {
      const { session, aliases } = get();
      if (!session) return;

      const trip = tripById(session.tripId);
      const line = trip?.lines.find((l) => l.id === lineId);

      let next: Partial<Store>;
      if (itemId === null) {
        next = { session: { ...session, declined: [...new Set([...session.declined, lineId])] } };
      } else {
        // Remembering the wording is what makes the second run ask nothing.
        const store = new Aliases(aliases);
        if (line) store.add(line.text, itemId);
        next = {
          aliases: store.entries,
          session: { ...session, declined: session.declined.filter((id) => id !== lineId) },
        };
      }

      // Walk straight on to the next line that still needs a decision, rather
      // than dropping back to the list between every ten-second pick.
      const after = costedFrom(next.session ?? session, next.aliases ?? aliases);
      const remaining = after?.lines.find(
        (costedLine) => costedLine.status === "needs_check" && costedLine.line.id !== lineId,
      );

      set({ ...next, resolving: remaining?.line.id ?? null });
      persist();
    },

    enterOwnPrice: (lineId, amount) => {
      const { session } = get();
      if (!session) return;
      const ownPrices = { ...session.ownPrices };
      if (amount === null) delete ownPrices[lineId];
      else ownPrices[lineId] = amount;
      set({ session: { ...session, ownPrices } });
      persist();
    },

    saveQuote: () => {
      const costed = costedFrom(get().session, get().aliases);
      if (!costed) return;
      const { session, quotes } = get();
      const ownTotal = sumOwn(session?.ownPrices ?? {});
      const money = tripMoney(costed, session?.ownPrices ?? {});

      const quote: SavedQuote = {
        id: `q-${Date.now()}`,
        tripId: costed.trip.id,
        title: costed.trip.title,
        client: costed.trip.client,
        fileName: costed.trip.fileName.replace(/\.xlsx$/, "_COSTED.csv"),
        savedAt: new Date().toISOString(),
        currency: money.currency,
        total: money.total,
        ownTotal,
        lines: costed.trip.lines.length,
        nights: costed.trip.stays.reduce(
          (total, stay) =>
            total +
            (Date.parse(`${stay.checkOut}T00:00:00Z`) - Date.parse(`${stay.checkIn}T00:00:00Z`)) /
              86_400_000,
          0,
        ),
        awaitingDecision: costed.counts.needsCheck,
        awaitingSupplier: Math.max(
          0,
          costed.counts.needsQuote - Object.keys(session?.ownPrices ?? {}).length,
        ),
        seeded: false,
      };

      set({ quotes: [quote, ...quotes.filter((q) => q.tripId !== quote.tripId || q.seeded)] });
      persist();
    },

    resetDemo: () => {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        // Nothing to clear; the in-memory reset below is what matters.
      }
      set({ aliases: {}, quotes: SEEDED, session: null, screen: "price", resolving: null });
    },
  };
});

export function tripById(id: string): Trip | undefined {
  return SAMPLE_TRIPS.find((trip) => trip.id === id);
}

/**
 * Derive the costed trip from stored decisions rather than storing it.
 *
 * Confirmed wordings are already in the alias store, so re-costing picks them
 * up on its own; only the "neither" answers need replaying.
 */
export function costedFrom(
  session: Session | null,
  aliasEntries: Record<string, AliasEntry>,
): CostedTrip | null {
  if (!session) return null;
  const trip = tripById(session.tripId);
  if (!trip) return null;

  const aliases = new Aliases(aliasEntries);
  let costed = costTrip(trip, CATALOG, aliases);
  for (const lineId of session.declined) {
    costed = resolveLine(costed, lineId, null, CATALOG, aliases);
  }
  return costed;
}

export function sumOwn(ownPrices: Record<string, Money>): Money | null {
  const amounts = Object.values(ownPrices);
  if (amounts.length === 0) return null;
  let total = 0;
  for (const amount of amounts) total += Number(amount) * 100;
  return (Math.round(total) / 100).toFixed(2);
}

/**
 * Costing runs over ~180 catalog items on every call, and returns a fresh
 * object each time — so it is memoised against the two store values it
 * actually depends on rather than recomputed inside the selector.
 */
export function useCostedTrip(): CostedTrip | null {
  const session = useDemo((state) => state.session);
  const aliases = useDemo((state) => state.aliases);
  return useMemo(() => costedFrom(session, aliases), [session, aliases]);
}
