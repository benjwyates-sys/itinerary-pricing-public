import { Icon } from "../ui/Icon";
import { formatMoney } from "../ui/format";
import { XLSX_TYPE, saveFile } from "../ui/download";
import { HEADERS, buildItineraryTemplate } from "../template/workbook";
import { useDemo } from "../store/demo";

/** The consultant's costed trips: this session's, plus a few earlier ones. */
export function Quotes() {
  const quotes = useDemo((state) => state.quotes);
  const go = useDemo((state) => state.go);

  return (
    <>
      <div className="pagehead">
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <h1>My quotes</h1>
          <span className="pagehead__meta">Trips you've costed, newest first.</span>
        </div>
        <button type="button" className="btn btn--primary" onClick={() => go("price")}>
          Price another trip
        </button>
      </div>

      <div className="body">
        {/*
          The blank a consultant starts from. Its shape is the point: the five
          columns the engine's profiler looks for, in row one, with nothing
          above them — so an itinerary built on it is read without anyone
          being asked where the headers are.
        */}
        <div className="templatebar">
          <Icon name="file" size={20} color="#B85042" strokeWidth={1.7} />
          <div className="templatebar__body">
            <span className="templatebar__title">Blank itinerary template</span>
            <span className="templatebar__note">
              {HEADERS.join(" · ")}, headers in row one. Times are AM, PM or EVENING. Notes in
              the name are read too: <span className="mono">(only 4 people)</span> or{" "}
              <span className="mono">(15% discount)</span>.
            </span>
          </div>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() =>
              saveFile("itinerary_template.xlsx", buildItineraryTemplate(), XLSX_TYPE)
            }
          >
            <Icon name="download" size={17} strokeWidth={2} />
            Download the template
          </button>
        </div>

        <div className="panel">
          {quotes.length === 0 ? (
            <div className="empty">Nothing costed yet.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Trip</th>
                  <th>File</th>
                  <th>Costed</th>
                  <th style={{ textAlign: "right" }}>Nights</th>
                  <th style={{ textAlign: "right" }}>Items</th>
                  <th style={{ textAlign: "right" }}>Total</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {quotes.map((quote) => (
                  <tr key={quote.id}>
                    <td>
                      {quote.title}
                      {quote.seeded && (
                        <span style={{ color: "var(--muted)", fontSize: 12 }}> · sample</span>
                      )}
                    </td>
                    <td className="mono" style={{ fontSize: 12.5, color: "var(--muted)" }}>
                      {quote.fileName}
                    </td>
                    <td className="mono nowrap" style={{ fontSize: 13 }}>
                      {quote.savedAt.slice(0, 10)}
                    </td>
                    <td className="num">{quote.nights}</td>
                    <td className="num">{quote.lines}</td>
                    <td className="num">
                      {formatMoney(quote.currency, quote.total)}
                      {quote.ownTotal && (
                        <div style={{ fontSize: 11.5, color: "var(--caution)" }}>
                          incl. {formatMoney(quote.currency, quote.ownTotal)} yours
                        </div>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {quote.awaitingDecision > 0 && (
                          <span className="pill pill--check">
                            {quote.awaitingDecision} to confirm
                          </span>
                        )}
                        {quote.awaitingSupplier > 0 && (
                          <span className="pill pill--quote">
                            {quote.awaitingSupplier} awaiting a supplier
                          </span>
                        )}
                        {quote.awaitingDecision === 0 && quote.awaitingSupplier === 0 && (
                          <span className="pill pill--ok">Complete</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
