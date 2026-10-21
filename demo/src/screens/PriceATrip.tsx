import { Icon } from "../ui/Icon";
import { formatRange, plural } from "../ui/format";
import { SAMPLE_TRIPS } from "../data/trips";
import { nightsOf } from "../itinerary/build";
import type { Trip } from "../engine/types";
import { useDemo } from "../store/demo";

/**
 * The landing screen. The mockup's drop zone stays as the visual centrepiece,
 * but a demo visitor has no Excel file to drop — so the sample trips sit
 * directly beneath it, and the sample path is the demo path.
 */
const STORY: Record<string, string> = {
  "hartley-rome": "Every line matches the rate sheet. Prices in one pass, no questions.",
  "novak-dalmatia":
    "Worded the way people actually type. Three lines need a check, one needs a supplier.",
  "whitaker-italy": "A big group in August. Shows what happens when a price can't be worked out.",
};

export function PriceATrip() {
  const start = useDemo((state) => state.start);

  return (
    <>
      <div className="pagehead">
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <h1>Price a trip</h1>
          <span className="pagehead__meta">
            Attach an itinerary and get back a copy with the cost column filled in.
          </span>
        </div>
      </div>

      <div className="body">
        <div className="dropzone">
          <Icon name="file" size={30} color="#B85042" strokeWidth={1.6} />
          <div className="dropzone__title">Drop an itinerary here</div>
          <div className="dropzone__sub">
            This demo runs on sample trips. Pick one below.
          </div>
        </div>

        <div className="group">
          <div className="group__head">
            <span className="group__title">Try one of these</span>
          </div>

          <div className="triplist">
            {SAMPLE_TRIPS.map((trip) => (
              <button
                key={trip.id}
                type="button"
                className="tripcard"
                onClick={() => start(trip.id)}
              >
                <span className="tripcard__file mono">{trip.fileName}</span>
                <span className="tripcard__title">{trip.title}</span>
                <span className="tripcard__meta">
                  {plural(nightsIn(trip), "night")} · {formatRange(trip.from, trip.to)} ·{" "}
                  {plural(trip.pax, "traveller")} · {plural(trip.lines.length, "item")}
                </span>
                <span className="tripcard__story">{STORY[trip.id]}</span>
                <span className="tripcard__go">
                  See this itinerary <Icon name="arrowRight" size={15} color="#B85042" strokeWidth={2} />
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function nightsIn(trip: Trip): number {
  return trip.stays.reduce((total, stay) => total + nightsOf(stay), 0);
}
