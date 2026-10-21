import { useMemo, useState } from "react";
import { Icon } from "../ui/Icon";
import { formatDate, formatMoney, formatRange, plural } from "../ui/format";
import { DayPlanner } from "../itinerary/DayPlanner";
import { buildItinerary, tripMoney } from "../itinerary/build";
import { Resolve } from "./Resolve";
import { useCostedTrip, useDemo } from "../store/demo";
import type { CostedLine, Currency, Money } from "../engine/types";

/** One shared empty map, so a selector fallback is never a new object. */
const EMPTY: Record<string, string> = {};

/**
 * The costed trip, read as an itinerary: day by day, hotel and transfers and
 * experiences in the order they happen.
 *
 * §8.5 is a non-negotiable — the two kinds of attention must never be merged
 * into one list — and a day planner is by nature one chronological list. So
 * the separation lives in the strip at the top: two counts that never combine,
 * each opening its own list. In the days below, a line needing a decision and
 * a line needing a supplier are different colours and never look alike.
 *
 * Neither is styled as a failure. A refusal is the tool working.
 */
export function Review() {
  const costed = useCostedTrip();
  const session = useDemo((state) => state.session);
  const go = useDemo((state) => state.go);
  const resolving = useDemo((state) => state.resolving);
  const openResolve = useDemo((state) => state.openResolve);
  const closeResolve = useDemo((state) => state.closeResolve);
  const enterOwnPrice = useDemo((state) => state.enterOwnPrice);

  const ownPrices = session?.ownPrices ?? EMPTY;
  const [open, setOpen] = useState<"check" | "quote" | null>(null);

  const days = useMemo(() => (costed ? buildItinerary(costed) : []), [costed]);

  if (!costed) {
    return (
      <div className="body">
        <div className="empty">No trip open. Pick one from “Price a trip”.</div>
      </div>
    );
  }

  const money = tripMoney(costed, ownPrices);
  const checks = costed.lines.filter((line) => line.status === "needs_check");
  const quotes = costed.lines.filter(
    (line) => line.status === "needs_quote" && !ownPrices[line.line.id],
  );
  const resolvingLine = checks.find((line) => line.line.id === resolving);

  return (
    <>
      <div className="pagehead">
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <span className="pagehead__file mono">{costed.trip.fileName}</span>
          <h1>{costed.trip.title}</h1>
          <span className="pagehead__meta">
            {plural(days.length, "day")} · {formatRange(costed.trip.from, costed.trip.to)} ·{" "}
            {plural(costed.trip.pax, "traveller")}
          </span>
        </div>
        <div className="pagehead__totals">
          <span className="pagehead__total mono">{formatMoney(money.currency, money.total)}</span>
          <span className="pagehead__split">{describeTotal(money)}</span>
        </div>
      </div>

      <div className="body">
        <div className="triage">
          <div className="triage__row">
            {checks.length > 0 && (
              <button
                type="button"
                className="triage__chip triage__chip--check"
                aria-expanded={open === "check"}
                onClick={() => setOpen(open === "check" ? null : "check")}
              >
                <Icon name="question" size={16} strokeWidth={2} />
                {plural(checks.length, "line")} to confirm
              </button>
            )}
            {quotes.length > 0 && (
              <button
                type="button"
                className="triage__chip triage__chip--quote"
                aria-expanded={open === "quote"}
                onClick={() => setOpen(open === "quote" ? null : "quote")}
              >
                <Icon name="quote" size={16} strokeWidth={2} />
                {plural(quotes.length, "line")} awaiting a supplier
              </button>
            )}
            {checks.length === 0 && quotes.length === 0 && (
              <span className="triage__chip triage__chip--ok">
                <Icon name="check" size={16} strokeWidth={2.4} />
                Everything that can be priced, is
              </span>
            )}
            <span className="triage__aside">
              {checks.length > 0
                ? "About ten seconds each."
                : quotes.length > 0
                  ? "You'll need to ask the supplier."
                  : "Nothing is waiting on you."}
            </span>
          </div>

          {open === "check" && (
            <div className="triage__panel">
              <div className="cards">
                {checks.map((line) => (
                  <article key={line.line.id} className="checkcard">
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <span className="checkcard__label">
                        Day {dayOf(days, line)} · your itinerary says
                      </span>
                      <span className="checkcard__said">“{line.line.text}”</span>
                    </div>
                    <span className="checkcard__why">
                      {line.candidates.length > 1
                        ? "More than one thing in the rate sheet could be this, and they price differently."
                        : "Close to one experience in the rate sheet, but not worded the same way."}
                    </span>
                    <button
                      type="button"
                      className="btn btn--primary"
                      onClick={() => openResolve(line.line.id)}
                    >
                      Choose which one
                    </button>
                  </article>
                ))}
              </div>
            </div>
          )}

          {open === "quote" && (
            <div className="triage__panel">
              {quotes.map((line) => (
                <QuoteRow
                  key={line.line.id}
                  line={line}
                  currency={money.currency}
                  onEnterPrice={enterOwnPrice}
                />
              ))}
            </div>
          )}
        </div>

        <DayPlanner
          days={days}
          currency={money.currency}
          ownPrices={ownPrices}
          onChoose={openResolve}
          onEnterPrice={enterOwnPrice}
        />
      </div>

      <div className="pagefoot">
        {/* §8.7 — true of the real engine, and the thing that makes people willing to try it. */}
        <span className="pagefoot__note">
          Your original file hasn't been touched. The costed copy is a new file.
        </span>
        <div style={{ display: "flex", gap: 11 }}>
          <button type="button" className="btn btn--secondary" onClick={() => go("costed")}>
            Download as is
          </button>
          {checks[0] ? (
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => openResolve(checks[0].line.id)}
            >
              Check the {plural(checks.length, "line")}
              <Icon name="arrowRight" size={17} color="#FFFFFF" strokeWidth={2} />
            </button>
          ) : (
            <button type="button" className="btn btn--primary" onClick={() => go("costed")}>
              Finish and download
              <Icon name="arrowRight" size={17} color="#FFFFFF" strokeWidth={2} />
            </button>
          )}
        </div>
      </div>

      {resolvingLine && (
        <Resolve
          key={resolvingLine.line.id}
          line={resolvingLine}
          position={checks.indexOf(resolvingLine) + 1}
          total={checks.length}
          onClose={closeResolve}
        />
      )}
    </>
  );
}

/** Says what the headline number is made of, so no part of it passes as another. */
function describeTotal(money: ReturnType<typeof tripMoney>): string {
  const parts = [
    `${formatMoney(money.currency, money.experiences)} experiences`,
    `${formatMoney(money.currency, money.accommodation)} accommodation`,
  ];
  if (money.own) parts.push(`${formatMoney(money.currency, money.own)} entered by you`);
  return parts.join(" · ");
}

function dayOf(days: ReturnType<typeof buildItinerary>, line: CostedLine): number {
  return days.find((day) => day.date === line.line.date)?.number ?? 0;
}

function QuoteRow({
  line,
  currency,
  onEnterPrice,
}: {
  line: CostedLine;
  currency: Currency;
  onEnterPrice: (lineId: string, amount: Money) => void;
}) {
  const [entering, setEntering] = useState(false);
  const [draft, setDraft] = useState("");

  const subject = encodeURIComponent(`Rate enquiry: ${line.line.text}`);
  const body = encodeURIComponent(
    `Hello,\n\nCould you quote the following for ${line.line.pax} travellers on ${line.line.date}?\n\n` +
      `  ${line.line.text}\n\nMany thanks,`,
  );

  return (
    <div className="quoterow">
      <div className="quoterow__body">
        <span className="quoterow__what">
          {line.itemName ?? line.line.text}
          {line.line.date ? ` · ${formatDate(line.line.date)}` : ""}
        </span>
        {/* The engine's own words for why it stopped. Never paraphrased into an error. */}
        <span className="quoterow__why">{line.reason} Nothing was guessed for this line.</span>
      </div>

      {entering ? (
        <form
          className="inlineform"
          onSubmit={(event) => {
            event.preventDefault();
            if (/^\d+(\.\d{1,2})?$/.test(draft)) {
              onEnterPrice(line.line.id, Number(draft).toFixed(2));
              setEntering(false);
            }
          }}
        >
          <input
            className="input"
            autoFocus
            inputMode="decimal"
            placeholder={`0.00 ${currency}`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            aria-label="Price quoted by the supplier"
          />
          <button type="submit" className="btn btn--secondary">
            Save
          </button>
        </form>
      ) : (
        <div className="quoterow__actions">
          <a className="btn btn--secondary" href={`mailto:?subject=${subject}&body=${body}`}>
            Email supplier
          </a>
          <button type="button" className="btn btn--secondary" onClick={() => setEntering(true)}>
            Enter a price
          </button>
        </div>
      )}
    </div>
  );
}
