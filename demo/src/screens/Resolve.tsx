import { useState } from "react";
import { Icon } from "../ui/Icon";
import { formatMoney } from "../ui/format";
import { CATALOG } from "../data/catalog";
import { evaluate } from "../engine/patterns";
import type { CostedLine } from "../engine/types";
import { useDemo } from "../store/demo";

/**
 * Confirm a match.
 *
 * The single most important thing on this screen is that each option shows
 * what it would cost *this party* (§8.6). The consultant is choosing between
 * €180 and €225, not between two catalog entries.
 *
 * A candidate the engine would refuse says so in place of a price. Offering
 * it silently and letting the refusal appear afterwards would waste the pick.
 */
export function Resolve({
  line,
  position,
  total,
  onClose,
}: {
  line: CostedLine;
  position: number;
  total: number;
  onClose: () => void;
}) {
  const confirmMatch = useDemo((state) => state.confirmMatch);
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);

  const priced = line.candidates.map((candidate) => {
    const item = CATALOG.find((entry) => entry.id === candidate.itemId)!;
    const result = evaluate(item, {
      pax: line.line.pax,
      date: line.line.date,
      dayPart: line.line.dayPart,
    });
    return { candidate, item, result };
  });

  // A selection is only valid for the line it was made on. Confirming an item
  // the consultant is not currently looking at would attach a price she never
  // chose — the exact shape of every silent mispricing in this project's history.
  const valid =
    chosen === null || (chosen !== undefined && priced.some(({ item }) => item.id === chosen));

  return (
    <div className="scrim" role="dialog" aria-modal="true" aria-label="Confirm a match">
      <div className="modal">
        <div className="modal__head">
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <span className="modal__step">
              {position} of {total} · line {line.line.id.replace(/\D/g, "")}
            </span>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={{ fontSize: 13.5, color: "var(--muted)" }}>Your itinerary says</span>
              <span className="modal__said">“{line.line.text}”</span>
            </div>
          </div>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Close">
            <Icon name="close" size={17} color="#7A6A65" strokeWidth={2} />
          </button>
        </div>

        <div className="modal__body">
          <span className="modal__lead">
            {priced.length === 1
              ? "Is this the one you meant? It's the closest match in your rate sheet."
              : "Which of these did you mean? They all exist in your rate sheet."}
          </span>

          <div className="options">
            {priced.map(({ candidate, item, result }) => {
              const isChosen = chosen === candidate.itemId;
              return (
                <button
                  key={candidate.itemId}
                  type="button"
                  className={`option${isChosen ? " option--chosen" : ""}`}
                  onClick={() => setChosen(candidate.itemId)}
                >
                  <span className={`radio${isChosen ? " radio--on" : ""}`}>
                    {isChosen && <Icon name="check" size={13} color="#FFFFFF" strokeWidth={3} />}
                  </span>
                  <span className="option__body">
                    <span className="option__name">{item.name}</span>
                    <span className="option__how">{describe(item)}</span>
                  </span>
                  <span className="option__money">
                    {result.ok ? (
                      <>
                        <span className="option__amount mono">
                          {formatMoney(result.currency, result.total)}
                        </span>
                        <span className="option__for">
                          {item.unit === "per_group"
                            ? `for your ${line.line.pax} travellers`
                            : `${billedFor(item, line)} × ${formatMoney(item.currency, unitOf(result.breakdown))}`}
                        </span>
                      </>
                    ) : (
                      <span className="option__refused">Can't be priced for this line</span>
                    )}
                  </span>
                </button>
              );
            })}

            <button
              type="button"
              className={`option option--neither${chosen === null ? " option--chosen" : ""}`}
              onClick={() => setChosen(null)}
            >
              <span className={`radio${chosen === null ? " radio--on" : ""}`}>
                {chosen === null && <Icon name="check" size={13} color="#FFFFFF" strokeWidth={3} />}
              </span>
              <span style={{ fontSize: 15, color: "var(--muted)", flexGrow: 1, textAlign: "left" }}>
                Neither: it's something else, or it needs a supplier quote
              </span>
            </button>
          </div>

          <div className="reassure">
            <Icon name="again" color="#4A6E5F" strokeWidth={1.9} />
            <span>
              You'll only be asked this once. From now on, “{line.line.text}” prices itself on every
              trip.
            </span>
          </div>
        </div>

        <div className="modal__foot">
          <span style={{ fontSize: 13, color: "var(--muted)" }}>
            Skip for now. It'll stay marked in the sheet.
          </span>
          <div style={{ display: "flex", gap: 10 }}>
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              Skip
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={!valid}
              onClick={() => valid && confirmMatch(line.line.id, chosen as string | null)}
            >
              Confirm and continue
              <Icon name="arrowRight" size={17} color="#FFFFFF" strokeWidth={2} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function describe(item: (typeof CATALOG)[number]): string {
  const parts: string[] = [];
  parts.push(item.unit === "per_group" ? "Charged once for the group" : "Charged per person");
  if (item.pricing?.pattern === "tiered_by_pax") {
    const bands = item.pricing.tiers.map((tier) => `up to ${tier.maxPax}`).join(", ");
    parts.push(`bands ${bands}`);
  }
  if (item.minBillablePax) parts.push(`billed for ${item.minBillablePax} minimum`);
  return parts.join(" · ");
}

function billedFor(item: (typeof CATALOG)[number], line: CostedLine): number {
  return Math.max(line.line.pax, item.minBillablePax ?? 0);
}

/** Pull the unit rate back out of the engine's own breakdown, rather than recomputing it. */
function unitOf(breakdown: string[]): string {
  const step = breakdown.find((entry) => entry.startsWith("="));
  return step ? step.split(" ")[1] : "0.00";
}
