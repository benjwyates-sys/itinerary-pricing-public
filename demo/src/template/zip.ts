/**
 * A minimal zip writer, enough for an .xlsx.
 *
 * An .xlsx is a zip of XML parts, and Excel accepts entries stored
 * uncompressed — so this needs a CRC and some little-endian headers, and no
 * compressor at all. That is a small enough surface to own outright, which
 * beats adding a dependency for one fixed template file.
 *
 * Output is deterministic: entries carry a fixed timestamp, so rebuilding the
 * template produces the same bytes and a rebuild is never mistaken for a
 * change.
 */

export type ZipEntry = { name: string; data: Uint8Array };

const LOCAL_HEADER = 0x04034b50;
const CENTRAL_HEADER = 0x02014b50;
const END_OF_CENTRAL_DIR = 0x06054b50;

/** 1 January 2026, 00:00, in DOS date/time. Fixed, so output stays stable. */
const DOS_DATE = ((2026 - 1980) << 9) | (1 << 5) | 1;
const DOS_TIME = 0;

const CRC_TABLE = buildCrcTable();

function buildCrcTable(): Uint32Array {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let value = i;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[i] = value >>> 0;
  }
  return table;
}

export function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of data) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

export function zip(entries: ZipEntry[]): Uint8Array<ArrayBuffer> {
  const encoder = new TextEncoder();
  const prepared = entries.map((entry) => ({
    name: encoder.encode(entry.name),
    data: entry.data,
    crc: crc32(entry.data),
  }));

  const localSize = prepared.reduce((size, e) => size + 30 + e.name.length + e.data.length, 0);
  const centralSize = prepared.reduce((size, e) => size + 46 + e.name.length, 0);

  const out = new Uint8Array(localSize + centralSize + 22);
  const view = new DataView(out.buffer);
  let at = 0;

  const u32 = (value: number) => {
    view.setUint32(at, value, true);
    at += 4;
  };
  const u16 = (value: number) => {
    view.setUint16(at, value, true);
    at += 2;
  };
  const raw = (value: Uint8Array) => {
    out.set(value, at);
    at += value.length;
  };

  const offsets: number[] = [];

  for (const entry of prepared) {
    offsets.push(at);
    u32(LOCAL_HEADER);
    u16(20); // version needed
    u16(0); // flags
    u16(0); // method: stored
    u16(DOS_TIME);
    u16(DOS_DATE);
    u32(entry.crc);
    u32(entry.data.length); // compressed size — the same, stored
    u32(entry.data.length);
    u16(entry.name.length);
    u16(0); // extra field length
    raw(entry.name);
    raw(entry.data);
  }

  const centralStart = at;

  for (const [index, entry] of prepared.entries()) {
    u32(CENTRAL_HEADER);
    u16(20); // version made by
    u16(20); // version needed
    u16(0); // flags
    u16(0); // method: stored
    u16(DOS_TIME);
    u16(DOS_DATE);
    u32(entry.crc);
    u32(entry.data.length);
    u32(entry.data.length);
    u16(entry.name.length);
    u16(0); // extra
    u16(0); // comment
    u16(0); // disk number
    u16(0); // internal attributes
    u32(0); // external attributes
    u32(offsets[index]);
    raw(entry.name);
  }

  // Measure the central directory before writing the record that describes
  // it — the writers below advance `at` as they go, so reading it inline
  // would report a directory twelve bytes longer than the one on disk, and an
  // unzipper reads that difference as data prepended to the archive.
  const centralBytes = at - centralStart;

  u32(END_OF_CENTRAL_DIR);
  u16(0); // this disk
  u16(0); // disk with the central directory
  u16(prepared.length);
  u16(prepared.length);
  u32(centralBytes);
  u32(centralStart);
  u16(0); // comment length

  return out;
}
