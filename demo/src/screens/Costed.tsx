import { useMemo } from "react";
import { Icon } from "../ui/Icon";
import { formatMoney, formatRange, plural } from "../ui/format";
import { DayPlanner } from "../itinerary/DayPlanner";
import { buildItinerary, tripMoney } from "../itinerary/build";
import { toCsv, toCsvRows } from "../itinerary/csv";
import { CSV_TYPE, saveFile } from "../ui/download";
import { useCostedTrip, useDemo } from "../store/demo";
import type { CostedTrip, Money } from "../engine/types";

/** One shared empty map, so a selector fallback is never a new object. */
const EMPTY: Record<string, string> = {};

/**
 * The finished itinerary: the same day-by-day view the consultant worked in,
 * so what she sees is what the client receives.
 *
 * The three kinds of money are totalled apart before they are totalled
 * together. Folding them into one figure would let a rate she typed, or a
 * hotel rate from another system, read as something the rate sheet produced.
 */
export function Costed() {
  const costed = useCostedTrip();
  const session = useDemo((state) => state.session);
  const go = useDemo((state) => state.go);
  const saveQuote = useDemo((state) => state.saveQuote);

  const ownPrices = session?.ownPrices ?? EMPTY;
  const days = useMemo(() => (costed ? buildItinerary(costed) : []), [costed]);

  if (!costed) {
    return (
      <div className="body">
        <div className="empty">No trip open. Pick one from “Price a trip”.</div>
      </div>
    );
  }

  const money = tripMoney(costed, ownPrices);
  const awaitingDecision = costed.counts.needsCheck;
  const awaitingSupplier = Math.max(
    0,
    costed.counts.needsQuote - Object.keys(ownPrices).length,
  );

  return (
    <>
      <div className="pagehead">
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <span className="pagehead__file mono">
            {costed.trip.fileName.replace(/\.xlsx$/, "_COSTED.csv")}
          </span>
          <h1>{costed.trip.title}</h1>
          <span className="pagehead__meta">
            {plural(days.length, "day")} · {formatRange(costed.trip.from, costed.trip.to)} ·{" "}
            {plural(costed.trip.pax, "traveller")}
          </span>
        </div>
        <div className="pagehead__totals">
          <span className="pagehead__total mono">{formatMoney(money.currency, money.total)}</span>
          <span className="pagehead__split">Trip total</span>
        </div>
      </div>

      <div className="body">
        <div className="stats">
          <div className="stat">
            <span className="stat__label">Experiences</span>
            <span className="stat__value mono">
              {formatMoney(money.currency, money.experiences)}
            </span>
            <span className="stat__note">
              Priced from the rate sheet · {plural(costed.counts.priced, "line")}
            </span>
          </div>
          <div className="stat">
            <span className="stat__label">Accommodation</span>
            <span className="stat__value mono">
              {formatMoney(money.currency, money.accommodation)}
            </span>
            <span className="stat__note">
              From your accommodation booking, not the rate sheet
            </span>
          </div>
          {money.own && (
            <div className="stat">
              <span className="stat__label">Entered by you</span>
              <span className="stat__value mono">{formatMoney(money.currency, money.own)}</span>
              <span className="stat__note">Supplier figures you typed in</span>
            </div>
          )}
          <div className="stat">
            <span className="stat__label">Still open</span>
            <span className="stat__value mono">{awaitingDecision + awaitingSupplier}</span>
            <span className="stat__note">
              {awaitingDecision + awaitingSupplier === 0
                ? "Nothing outstanding"
                : `${awaitingDecision} to confirm · ${awaitingSupplier} awaiting a supplier`}
            </span>
          </div>
        </div>

        <DayPlanner days={days} currency={money.currency} ownPrices={ownPrices} />
      </div>

      <div className="pagefoot">
        <span className="pagefoot__note">
          Your original file was never touched. This is a new file alongside it.
        </span>
        <div style={{ display: "flex", gap: 11 }}>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => {
              saveQuote();
              go("quotes");
            }}
          >
            Save to my quotes
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => download(costed, ownPrices)}
          >
            <Icon name="download" size={17} color="#FFFFFF" strokeWidth={2} />
            Download the costed copy
          </button>
        </div>
      </div>
    </>
  );
}

function download(costed: CostedTrip, ownPrices: Record<string, Money>) {
  const csv = toCsv(toCsvRows(costed, ownPrices));
  // A BOM, so Excel opens the accented names correctly.
  saveFile(
    costed.trip.fileName.replace(/\.xlsx$/, "_COSTED.csv"),
    `\ufeff${csv}`,
    CSV_TYPE,
  );
}
