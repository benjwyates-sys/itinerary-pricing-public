import { CATALOG, CITIES } from "../data/catalog";
import { formatDate } from "../ui/format";

/**
 * Setup and mapping stay with one person. Consultants never see a rate sheet,
 * a mapping, or a setup step — which is the argument for hosting this centrally
 * rather than asking every consultant to pay the setup cost themselves.
 *
 * Read-only in the demo: nothing here does anything except navigate.
 */

/** Sample figures, fixed so the screen reads the same at every showing. */
const REVIEWED: Record<string, string> = {
  Athens: "2026-08-14", Barcelona: "2026-09-02", Dubrovnik: "2026-09-11",
  Florence: "2026-07-29", Lisbon: "2026-08-30", London: "2026-09-04",
  Paris: "2026-08-21", Porto: "2026-08-30", Prague: "2026-06-18",
  Rome: "2026-09-08", Santorini: "2026-07-16", Seville: "2026-05-22",
  Split: "2026-09-11", Venice: "2026-08-05",
};


export function Admin() {
  const onRequest = CATALOG.filter((item) => !item.pricing).length;

  return (
    <>
      <div className="pagehead">
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <h1>Rate sheets</h1>
          <span className="pagehead__meta">
            Mapped once, centrally. Consultants never see this screen.
          </span>
        </div>
      </div>

      <div className="body">
        <div className="stats stats--pair">
          <div className="stat">
            <span className="stat__label">Regions mapped</span>
            <span className="stat__value mono">{CITIES.length}</span>
            <span className="stat__note">All currently in season</span>
          </div>
          <div className="stat">
            <span className="stat__label">Experiences</span>
            <span className="stat__value mono">{CATALOG.length}</span>
            <span className="stat__note">{onRequest} priced on request</span>
          </div>
        </div>

        <div className="panel">
          <div className="panel__head">
            <span className="panel__title">Coverage by region</span>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>
              Every rate here is invented for the demo
            </span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Region</th>
                  <th>Country</th>
                  <th>Currency</th>
                  <th style={{ textAlign: "right" }}>Experiences</th>
                  <th>Rates mapped</th>
                  <th>Last reviewed</th>
                </tr>
              </thead>
              <tbody>
                {CITIES.map((city) => {
                  const items = CATALOG.filter((item) => item.city === city.name);
                  const mapped = items.filter((item) => item.pricing).length;
                  return (
                    <tr key={city.name}>
                      <td style={{ fontWeight: 500 }}>{city.name}</td>
                      <td style={{ color: "var(--muted)" }}>{city.country}</td>
                      <td className="mono" style={{ fontSize: 13 }}>{city.currency}</td>
                      <td className="num">{items.length}</td>
                      <td>
                        {mapped === items.length ? (
                          <span className="pill pill--ok">all {mapped}</span>
                        ) : (
                          <span className="pill pill--quote">
                            {mapped} of {items.length}
                          </span>
                        )}
                      </td>
                      <td className="nowrap" style={{ color: "var(--muted)", fontSize: 13 }}>
                        {formatDate(REVIEWED[city.name])}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </>
  );
}

