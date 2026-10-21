import { useMemo } from "react";
import { Icon } from "../ui/Icon";
import { formatDayMonth, formatRange, formatWeekday, plural } from "../ui/format";
import { nightsOf, previewItinerary } from "../itinerary/build";
import { tripById, useDemo } from "../store/demo";
import type { PreviewDay } from "../itinerary/build";
import type { Stay, TripLine } from "../engine/types";

/**
 * The itinerary exactly as it arrived, before anything has been priced.
 *
 * It shares its day layout with the costed view on purpose: what a visitor
 * sees here is demonstrably the same trip they see priced a moment later, so
 * the only thing that changed between the two screens is the money — which is
 * the entire claim the demo is making.
 *
 * There are no prices here, no matches, and no questions. Just the file.
 */
export function Preview() {
  const session = useDemo((state) => state.session);
  const go = useDemo((state) => state.go);

  const trip = session ? tripById(session.tripId) : undefined;
  const days = useMemo(() => (trip ? previewItinerary(trip) : []), [trip]);

  if (!trip) {
    return (
      <div className="body">
        <div className="empty">No trip open. Pick one from “Price a trip”.</div>
      </div>
    );
  }

  return (
    <>
      <div className="pagehead">
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <span className="pagehead__file mono">{trip.fileName}</span>
          <h1>{trip.title}</h1>
          <span className="pagehead__meta">
            {plural(days.length, "day")} · {formatRange(trip.from, trip.to)} ·{" "}
            {plural(trip.pax, "traveller")} · {plural(trip.lines.length, "item")}
          </span>
        </div>
        <div className="pagehead__totals">
          <span className="pagehead__unpriced">Not yet priced</span>
        </div>
      </div>

      <div className="body">
        <div className="days days--preview">
          {days.map((day) => (
            <PreviewDayBlock key={day.date} day={day} pax={trip.pax} />
          ))}
        </div>
      </div>

      <div className="pagefoot">
        <span className="pagefoot__note">
          {plural(trip.lines.length, "line")} to price. Costing writes to a copy, so this file is
          left as it is.
        </span>
        <div style={{ display: "flex", gap: 11 }}>
          <button type="button" className="btn btn--secondary" onClick={() => go("price")}>
            Pick a different trip
          </button>
          <button type="button" className="btn btn--primary" onClick={() => go("review")}>
            Cost this itinerary
            <Icon name="arrowRight" size={17} color="#FFFFFF" strokeWidth={2} />
          </button>
        </div>
      </div>
    </>
  );
}

const SLOT_LABEL = { AM: "Morning", PM: "Afternoon", EVENING: "Evening" } as const;

function PreviewDayBlock({ day, pax }: { day: PreviewDay; pax: number }) {
  return (
    <section className="day">
      <header className="day__head">
        <span className="day__number">Day {day.number}</span>
        <span className="day__date">
          {formatWeekday(day.date)}, {formatDayMonth(day.date)}
        </span>
        {day.city && <span className="day__city">{day.city}</span>}
      </header>

      <div className="day__body">
        {day.checkOut && <PreviewStay stay={day.checkOut} arriving={false} />}
        {day.checkIn && <PreviewStay stay={day.checkIn} arriving />}

        {day.atLeisure && (
          <PreviewRow label="">
            <div className="entry entry--free">
              <Icon name="free" size={17} color="#7A6A65" />
              <span className="entry__free">Day at leisure{day.city ? ` in ${day.city}` : ""}</span>
            </div>
          </PreviewRow>
        )}

        {day.slots.map((block) => {
          if (block.lines.length === 0 && !block.free) return null;
          return (
            <PreviewRow key={block.slot} label={SLOT_LABEL[block.slot]}>
              {block.free ? (
                <div className="entry entry--free">
                  <Icon name="free" size={17} color="#7A6A65" />
                  <span className="entry__free">At leisure</span>
                </div>
              ) : (
                block.lines.map((line) => <PreviewLine key={line.id} line={line} pax={pax} />)
              )}
            </PreviewRow>
          );
        })}

        {day.untimed.length > 0 && (
          <PreviewRow label="Time not stated">
            {day.untimed.map((line) => (
              <PreviewLine key={line.id} line={line} pax={pax} />
            ))}
          </PreviewRow>
        )}
      </div>
    </section>
  );
}

function PreviewRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="dayrow">
      <div className="dayrow__label">{label}</div>
      <div className="dayrow__entries">{children}</div>
    </div>
  );
}

function PreviewStay({ stay, arriving }: { stay: Stay; arriving: boolean }) {
  return (
    <PreviewRow label={arriving ? "Check in" : "Check out"}>
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
      </div>
    </PreviewRow>
  );
}

function PreviewLine({ line, pax }: { line: TripLine; pax: number }) {
  return (
    <div className="entry">
      <Icon name={kindOf(line.text)} size={17} color="#A2938E" />
      <div className="entry__body">
        {/* Her wording, exactly as typed. Nothing here has been matched yet. */}
        <span className="entry__name">{line.text}</span>
      </div>
      <div className="entry__right">
        {line.pax !== pax && (
          <span className="entry__detail">{plural(line.pax, "traveller")}</span>
        )}
        <span className="entry__blank" aria-label="No cost yet">
          –
        </span>
      </div>
    </div>
  );
}

/** Cosmetic only — it picks an icon and nothing else. */
function kindOf(text: string): "transfer" | "experience" {
  return /transfer|water taxi|airport|helicopter|private jet/i.test(text)
    ? "transfer"
    : "experience";
}
