/**
 * An .xlsx is a zip of XML parts. This writes the smallest zip Excel accepts —
 * stored, uncompressed entries — rather than pulling in a library to do it,
 * because the template is one fixed sheet and the format subset is small
 * enough to own outright.
 */
import { describe, expect, test } from "vitest";
import { crc32, zip } from "./zip";

const bytes = (text: string) => new TextEncoder().encode(text);
const asText = (data: Uint8Array) => new TextDecoder("latin1").decode(data);

const SIGNATURE = { local: [0x50, 0x4b, 0x03, 0x04], eocd: "PK" };

describe("crc32", () => {
  test("matches the canonical check value", () => {
    // The published CRC-32 of the string "123456789".
    expect(crc32(bytes("123456789")).toString(16)).toBe("cbf43926");
  });

  test("is zero for nothing", () => {
    expect(crc32(new Uint8Array())).toBe(0);
  });
});

describe("zip", () => {
  const entries = [
    { name: "hello.txt", data: bytes("hello") },
    { name: "nested/world.txt", data: bytes("world") },
  ];
  const archive = zip(entries);

  test("starts with a local file header", () => {
    expect([...archive.slice(0, 4)]).toEqual(SIGNATURE.local);
  });

  test("names every entry, in the order given", () => {
    const text = asText(archive);
    expect(text.indexOf("hello.txt")).toBeLessThan(text.indexOf("nested/world.txt"));
  });

  test("stores content uncompressed, so it reads back as written", () => {
    const text = asText(archive);
    expect(text).toContain("hello");
    expect(text).toContain("world");
  });

  test("counts its entries in the end-of-central-directory record", () => {
    const text = asText(archive);
    const eocd = text.lastIndexOf(SIGNATURE.eocd);
    // The total-entries field sits ten bytes into the record.
    expect(archive[eocd + 10] | (archive[eocd + 11] << 8)).toBe(2);
  });

  test("is byte-for-byte identical every time, so a rebuild is not a change", () => {
    expect([...zip(entries)]).toEqual([...archive]);
  });
});

describe("the end-of-central-directory record", () => {
  /**
   * This is the invariant a real unzipper checks, and the one a test that only
   * looks for signatures will miss: the record says where the central
   * directory starts and how long it is, and those two have to land exactly on
   * the record itself. Python's zipfile derives a "prepended data" offset from
   * the difference and refuses the file when it is not zero.
   */
  const archive = zip([
    { name: "a.txt", data: bytes("one") },
    { name: "b/c.txt", data: bytes("two") },
    { name: "d.xml", data: bytes("<x/>") },
  ]);

  const eocd = archive.length - 22;
  const view = new DataView(archive.buffer, archive.byteOffset, archive.byteLength);
  const size = view.getUint32(eocd + 12, true);
  const offset = view.getUint32(eocd + 16, true);

  test("sits at the very end, with no trailing comment", () => {
    expect(view.getUint32(eocd, true)).toBe(0x06054b50);
    expect(view.getUint16(eocd + 20, true)).toBe(0);
  });

  test("points at a real central directory header", () => {
    expect([...archive.slice(offset, offset + 4)]).toEqual([0x50, 0x4b, 0x01, 0x02]);
  });

  test("gives a size and offset that meet exactly where the record begins", () => {
    expect(offset + size).toBe(eocd);
  });
});
