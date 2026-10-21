/**
 * The blank itinerary a consultant downloads, fills in, and drops back.
 *
 * "Optimised for this application" is a shape, not a decoration: the five
 * columns `pricing/itinerary_profile.py` looks for, in row one, on a single
 * sheet, with nothing above them. The sample workbook in
 * `samples/build_samples.py` deliberately carries a title block and a merged
 * category band because those are what break parsers — this file is the
 * opposite of that one, so the profiler never has to guess a header row.
 *
 * The cost column is left empty on purpose. That is the column the tool fills
 * in, in a copy, and the original comes back untouched.
 */
import { zip } from "./zip";

/** Matched against ROLE_WORDS in `pricing/itinerary_profile.py`. */
export const HEADERS = ["Experience", "Date", "Pax", "Time", "Net Cost"];

/** Wide enough for a real experience name; the rest sized to their content. */
const COLUMN_WIDTHS = [52, 13, 8, 10, 14];

const COLUMNS = ["A", "B", "C", "D", "E"];

/**
 * Empty rows below the header, and they are load-bearing.
 *
 * `find_header_candidates` in `pricing/profile.py` skips any row with
 * nothing beneath it (`row >= max_row`), so a sheet holding only headers
 * cannot be profiled at all — the tool would reject its own template. These
 * rows carry no content; they just give the header row something to be above.
 */
const BLANK_ROWS = 60;

const XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
const MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
const RELS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const PACKAGE_RELS = "http://schemas.openxmlformats.org/package/2006/relationships";

export function templateParts(): Record<string, string> {
  return {
    "[Content_Types].xml": contentTypes(),
    "_rels/.rels": rootRels(),
    "xl/workbook.xml": workbook(),
    "xl/_rels/workbook.xml.rels": workbookRels(),
    "xl/styles.xml": styles(),
    "xl/worksheets/sheet1.xml": sheet(),
  };
}

export function buildItineraryTemplate(): Uint8Array<ArrayBuffer> {
  const encoder = new TextEncoder();
  return zip(
    Object.entries(templateParts()).map(([name, xml]) => ({
      name,
      data: encoder.encode(xml),
    })),
  );
}

function contentTypes(): string {
  const type = (part: string, kind: string) =>
    `<Override PartName="${part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.${kind}+xml"/>`;

  return (
    `${XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
    `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
    `<Default Extension="xml" ContentType="application/xml"/>` +
    type("/xl/workbook.xml", "sheet.main") +
    type("/xl/worksheets/sheet1.xml", "worksheet") +
    type("/xl/styles.xml", "styles") +
    `</Types>`
  );
}

function rootRels(): string {
  return (
    `${XML}<Relationships xmlns="${PACKAGE_RELS}">` +
    `<Relationship Id="rId1" Type="${RELS}/officeDocument" Target="xl/workbook.xml"/>` +
    `</Relationships>`
  );
}

function workbook(): string {
  return (
    `${XML}<workbook xmlns="${MAIN}" xmlns:r="${RELS}">` +
    `<sheets><sheet name="Itinerary" sheetId="1" r:id="rId1"/></sheets>` +
    `</workbook>`
  );
}

function workbookRels(): string {
  return (
    `${XML}<Relationships xmlns="${PACKAGE_RELS}">` +
    `<Relationship Id="rId1" Type="${RELS}/worksheet" Target="worksheets/sheet1.xml"/>` +
    `<Relationship Id="rId2" Type="${RELS}/styles" Target="styles.xml"/>` +
    `</Relationships>`
  );
}

/** Two cell formats: plain, and the bold one the header row uses. */
function styles(): string {
  return (
    `${XML}<styleSheet xmlns="${MAIN}">` +
    `<fonts count="2">` +
    `<font><sz val="11"/><name val="Calibri"/></font>` +
    `<font><b/><sz val="11"/><name val="Calibri"/></font>` +
    `</fonts>` +
    `<fills count="2"><fill><patternFill patternType="none"/></fill>` +
    `<fill><patternFill patternType="gray125"/></fill></fills>` +
    `<borders count="1"><border/></borders>` +
    `<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>` +
    `<cellXfs count="2">` +
    `<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>` +
    `<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>` +
    `</cellXfs>` +
    // Without a named default style, openpyxl warns when it opens the file —
    // and openpyxl is what the real engine reads an itinerary with.
    `<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>` +
    `</styleSheet>`
  );
}

function sheet(): string {
  const cols = COLUMN_WIDTHS.map(
    (width, index) =>
      `<col min="${index + 1}" max="${index + 1}" width="${width}" customWidth="1"/>`,
  ).join("");

  // Inline strings rather than a shared-strings part: one fewer part to keep
  // consistent, and openpyxl and Excel both read them.
  const cells = HEADERS.map(
    (header, index) =>
      `<c r="${COLUMNS[index]}1" s="1" t="inlineStr"><is><t>${escape(header)}</t></is></c>`,
  ).join("");

  const blanks = Array.from({ length: BLANK_ROWS }, (_, index) => {
    const row = index + 2;
    const empty = COLUMNS.map((column) => `<c r="${column}${row}"/>`).join("");
    return `<row r="${row}">${empty}</row>`;
  }).join("");

  return (
    `${XML}<worksheet xmlns="${MAIN}">` +
    `<sheetViews><sheetView workbookViewId="0">` +
    `<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>` +
    `</sheetView></sheetViews>` +
    `<sheetFormatPr defaultRowHeight="15"/>` +
    `<cols>${cols}</cols>` +
    `<sheetData><row r="1">${cells}</row>${blanks}</sheetData>` +
    `</worksheet>`
  );
}

function escape(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
