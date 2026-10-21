import { useState } from "react";
import type { ReactNode } from "react";
import { Icon } from "../ui/Icon";
import { formatDayMonth, formatMoney, formatWeekday, plural } from "../ui/format";
import { nightsOf, stayTotal, type DaySlot, type ItineraryDay } from "./build";
import type { CostedLine, Currency, Money, Stay } from "../engine/types";

/**
 * The trip as a planner: a block per day, in the order the day happens.
 *
 * A line the engine refused keeps its refusal here. It shows the engine's own
 * words in its place in the day, rather than a blank or a zero — a gap in an
 * itinerary reads as "included", which is the same silent mispricing in a
 * prettier format.
 */

const SLOT_LABEL: Record<DaySlot, string> = {
  AM: "Morning",
  PM: "Afternoon",
  EVENING: "Evening",
};

type EnterPrice = (lineId: string, amount: Money | null) => void;

export function DayPlanner({
  days,
  currency,
  ownPrices,
  onChoose,
  onEnterPrice,
}: {
  days: ItineraryDay[];
  currency: Currency;
  ownPrices: Record<string, Money>;
  onChoose?: (lineId: string) => void;
  onEnterPrice?: EnterPrice;
}) {
  const entryProps = (line: CostedLine) => ({
    line,
    currency,
    own: ownPrices[line.line.id],
    onChoose,
    onEnterPrice,
  });

  return (
    <div className="days">
      {days.map((day) => (
        <section className="day" key={day.date}>
          <header className="day__head">
            <span className="day__number">Day {day.number}</span>
            <span className="day__date">
              {formatWeekday(day.date)}, {formatDayMonth(day.date)}
            </span>
            {day.city && <span className="day__city">{day.city}</span>}
          </header>

          <div className="day__body">
            {day.checkOut && <StayRow stay={day.checkOut} arriving={false} />}
            {day.checkIn && <StayRow stay={day.checkIn} arriving />}

            {day.atLeisure && (
              <Row label="">
                <div className="entry entry--free">
                  <Icon name="free" size={17} color="#7A6A65" />
                  <span className="entry__free">
                    Day at leisure{day.city ? ` in ${day.city}` : ""}
                  </span>
                </div>
              </Row>
            )}

            {day.slots.map((block) => {
              if (block.lines.length === 0 && !block.free) return null;
              return (
                <Row key={block.slot} label={SLOT_LABEL[block.slot]}>
                  {block.free ? (
                    <div className="entry entry--free">
                      <Icon name="free" size={17} color="#7A6A65" />
                      <span className="entry__free">At leisure</span>
                    </div>
                  ) : (
                    block.lines.map((line) => (
                      <EntryRow key={line.line.id} {...entryProps(line)} />
                    ))
                  )}
                </Row>
              );
            })}

            {day.untimed.length > 0 && (
              <Row label="Time not stated">
                {day.untimed.map((line) => (
                  <EntryRow key={line.line.id} {...entryProps(line)} />
                ))}
              </Row>
            )}
          </div>
        </section>
      ))}
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="dayrow">
      <div className="dayrow__label">{label}</div>
      <div className="dayrow__entries">{children}</div>
    </div>
  );
}

function StayRow({ stay, arriving }: { stay: Stay; arriving: boolean }) {
  return (
    <Row label={arriving ? "Check in" : "Check out"}>
      <div className="entry entry--stay">
        <Icon name="hotel" size={17} color="#4A6E5F" />
        <div className="entry__body">
          <span className="entry__name">{stay.hotel}</span>
          <span className="entry__detail">
            {arriving
              ? `${stay.room} × ${stay.rooms} · ${plural(nightsOf(stay), "night")}`
              : `Departing · ${stay.city}`}
          </span>
        </div>
        {arriving && (
          <div className="entry__right">
            <span className="entry__amount mono">{formatMoney(stay.currency, stayTotal(stay))}</span>
            {/* Not a rate-sheet price, and never shown as one. */}
            <span className="entry__source">from your accommodation booking</span>
          </div>
        )}
      </div>
    </Row>
  );
}

function EntryRow({
  line,
  currency,
  own,
  onChoose,
  onEnterPrice,
}: {
  line: CostedLine;
  currency: Currency;
  own?: Money;
  onChoose?: (lineId: string) => void;
  onEnterPrice?: EnterPrice;
}) {
  return (
    <div className={`entry entry--${own ? "own" : line.status}`}>
      <Icon
        name={kindOf(line)}
        size={17}
        color={line.status === "priced" || own ? "#7A6A65" : tintOf(line.status)}
      />
      <div className="entry__body">
        <span className="entry__name">{line.itemName ?? line.line.text}</span>
        {line.status === "priced" ? (
          <span className="entry__detail">{howPriced(line, currency)}</span>
        ) : line.status === "needs_check" ? (
          <span className="entry__detail">
            Your itinerary says “{line.line.text}”. More than one rate could be this.
            {line.unreadNotes.length > 0 && (
              /* Say why the bracket did nothing, rather than letting it look
                 like the tool read it and chose to ignore it. */
              <> A note in brackets is only read as a party size or a percentage.</>
            )}
          </span>
        ) : (
          <span className="entry__detail">{line.reason}</span>
        )}
      </div>
      <PriceCell
        line={line}
        currency={currency}
        own={own}
        onChoose={onChoose}
        onEnterPrice={onEnterPrice}
      />
    </div>
  );
}

/**
 * What a line costs, and how it came to cost that.
 *
 * A figure the consultant typed is always shown as hers, and where it
 * replaces one the rate sheet produced, the rate sheet's figure stays on
 * screen beside it. An override you cannot see is an override nobody checks.
 */
function PriceCell({
  line,
  currency,
  own,
  onChoose,
  onEnterPrice,
}: {
  line: CostedLine;
  currency: Currency;
  own?: Money;
  onChoose?: (lineId: string) => void;
  onEnterPrice?: EnterPrice;
}) {
  const [editing, setEditing] = useState(false);

  if (editing && onEnterPrice) {
    return (
      <div className="entry__right">
        <PriceInput
          initial={own ?? line.total ?? ""}
          currency={currency}
          onCancel={() => setEditing(false)}
          onSave={(amount) => {
            onEnterPrice(line.line.id, amount);
            setEditing(false);
          }}
        />
      </div>
    );
  }

  if (own) {
    return (
      <div className="entry__right">
        <span className="entry__amount mono">{formatMoney(currency, own)}</span>
        <span className="entry__source">your figure, not the rate sheet</span>
        {line.status === "priced" && line.total && (
          <span className="entry__was">
            rate sheet said{" "}
            <span className="mono">{formatMoney(line.currency ?? currency, line.total)}</span>
          </span>
        )}
        {onEnterPrice && (
          <div className="entry__actions">
            <button type="button" className="entry__action" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button
              type="button"
              className="entry__action"
              onClick={() => onEnterPrice(line.line.id, null)}
            >
              {line.status === "priced" ? "Use the rate sheet" : "Clear"}
            </button>
          </div>
        )}
      </div>
    );
  }

  if (line.status === "priced") {
    return (
      <div className="entry__right">
        <span className="entry__amount mono">{formatMoney(line.currency!, line.total!)}</span>
        {onEnterPrice && (
          <button
            type="button"
            className="entry__edit"
            onClick={() => setEditing(true)}
            aria-label={`Change the price of ${line.itemName ?? line.line.text}`}
          >
            Change this price
          </button>
        )}
      </div>
    );
  }

  if (line.status === "needs_check") {
    return (
      <div className="entry__right">
        <button
          type="button"
          className="entry__action entry__action--check"
          disabled={!onChoose}
          onClick={() => onChoose?.(line.line.id)}
        >
          Choose which one
        </button>
      </div>
    );
  }

  return (
    <div className="entry__right">
      <QuoteActions line={line} currency={currency} onEnterPrice={onEnterPrice} />
    </div>
  );
}

/** A price the consultant types. Strict: digits and at most two decimals. */
function PriceInput({
  initial,
  currency,
  onSave,
  onCancel,
}: {
  initial: string;
  currency: Currency;
  onSave: (amount: Money) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const valid = /^\d+(\.\d{1,2})?$/.test(draft.trim());

  return (
    <form
      className="inlineform"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) onSave(Number(draft).toFixed(2));
      }}
    >
      <input
        className="input input--small"
        autoFocus
        inputMode="decimal"
        placeholder={`0.00 ${currency}`}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") onCancel();
        }}
        aria-label="Price"
      />
      <button type="submit" className="entry__action" disabled={!valid}>
        Save
      </button>
      <button type="button" className="entry__action" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}

function QuoteActions({
  line,
  currency,
  onEnterPrice,
}: {
  line: CostedLine;
  currency: Currency;
  onEnterPrice?: EnterPrice;
}) {
  const [entering, setEntering] = useState(false);

  if (!onEnterPrice) return <span className="pill pill--quote">Needs a supplier quote</span>;

  if (entering) {
    return (
      <PriceInput
        initial=""
        currency={currency}
        onCancel={() => setEntering(false)}
        onSave={(amount) => {
          onEnterPrice(line.line.id, amount);
          setEntering(false);
        }}
      />
    );
  }

  const subject = encodeURIComponent(`Rate enquiry: ${line.line.text}`);
  const body = encodeURIComponent(
    `Hello,\n\nCould you quote the following for ${line.line.pax} travellers on ${line.line.date}?\n\n` +
      `  ${line.line.text}\n\nMany thanks,`,
  );

  return (
    <div className="entry__actions">
      <a className="entry__action" href={`mailto:?subject=${subject}&body=${body}`}>
        Email supplier
      </a>
      <button type="button" className="entry__action" onClick={() => setEntering(true)}>
        Enter a price
      </button>
    </div>
  );
}

function tintOf(status: CostedLine["status"]): string {
  return status === "needs_check" ? "#B85042" : "#8A6D3B";
}

/** Cosmetic only — it picks an icon and nothing else. */
function kindOf(line: CostedLine): "transfer" | "experience" {
  const text = (line.itemName ?? line.line.text).toLowerCase();
  return /transfer|water taxi|airport|helicopter|private jet/.test(text)
    ? "transfer"
    : "experience";
}

const SUPPLEMENT: Record<string, string> = {
  day_part: "time-of-day supplement",
  seasonal: "seasonal supplement",
  day_of_week: "day-of-week rate",
};

/** Describe the arithmetic from the engine's own breakdown, never by redoing it. */
export function howPriced(line: CostedLine, currency: Currency): string {
  const step = line.breakdown.find((entry) => entry.startsWith("="));
  const parts: string[] = [];

  if (line.unit === "per_group") {
    parts.push("charged once for the group");
  } else if (step) {
    const [, unitRate, , units] = step.split(" ");
    parts.push(`${units} × ${formatMoney(line.currency ?? currency, Number(unitRate).toFixed(2))}`);
    if (line.minBillablePax && line.minBillablePax > line.line.pax) {
      parts.push(`billed for ${line.minBillablePax}`);
    }
  }

  for (const entry of line.breakdown) {
    if (!entry.startsWith("+")) continue;
    const kind = /\((\w+)\)/.exec(entry)?.[1] ?? "";
    const label = SUPPLEMENT[kind];
    if (label && !parts.includes(label)) parts.push(label);
  }

  // Notes the consultant wrote are named, so a changed number is never silent.
  for (const adjustment of line.adjustments) {
    parts.push(`your note: ${adjustment.note}`);
  }

  return parts.join(" · ");
}
