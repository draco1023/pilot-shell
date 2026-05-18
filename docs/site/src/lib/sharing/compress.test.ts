import { describe, expect, it, beforeAll } from "vitest";

// Node 22's Uint8Array doesn't yet ship toBase64/fromBase64 (browser-only ES2025
// stage 4). The shipped compress.ts targets Chrome 128+/Safari 17.4+/Firefox 133+
// where those methods exist; we polyfill them here so the unit suite can run.
beforeAll(() => {
  const proto = Uint8Array.prototype as unknown as {
    toBase64?: (opts?: { alphabet?: string; omitPadding?: boolean }) => string;
  };
  if (typeof proto.toBase64 !== "function") {
    proto.toBase64 = function toBase64(this: Uint8Array, opts?: { alphabet?: string; omitPadding?: boolean }) {
      const b64 = Buffer.from(this).toString("base64");
      let url = b64.replace(/\+/g, "-").replace(/\//g, "_");
      if (opts?.omitPadding) url = url.replace(/=+$/, "");
      return opts?.alphabet === "base64url" ? url : b64;
    };
  }
  const ctor = Uint8Array as unknown as {
    fromBase64?: (s: string, opts?: { alphabet?: string }) => Uint8Array;
  };
  if (typeof ctor.fromBase64 !== "function") {
    ctor.fromBase64 = (s: string, opts?: { alphabet?: string }) => {
      const std = opts?.alphabet === "base64url"
        ? s.replace(/-/g, "+").replace(/_/g, "/")
        : s;
      return new Uint8Array(Buffer.from(std, "base64"));
    };
  }
});

import { compress, decompress, MAX_DECOMPRESSED_BYTES } from "./compress";

describe("compress / decompress — zip-bomb defense", () => {
  it("round-trips a normal-sized spec markdown", async () => {
    const original = "# Spec\n\nSome content with annotations.".repeat(100);
    const compressed = await compress(original);
    const back = await decompress(compressed);
    expect(back).toBe(original);
  });

  it("round-trips a highly compressible payload near but under the cap", async () => {
    // 1 MB of zeros compresses to ~1 KB. Decompression stays within the 2 MB cap.
    const original = "0".repeat(1024 * 1024);
    const compressed = await compress(original);
    const back = await decompress(compressed);
    expect(back.length).toBe(original.length);
  });

  it("throws when the decompressed output would exceed MAX_DECOMPRESSED_BYTES", async () => {
    // 3 MB of identical bytes compresses to a tiny payload (~3 KB), but
    // decompresses past the 2 MB cap — the streaming-cap guard MUST fire
    // before the recipient browser allocates the full output buffer.
    const bombSource = "x".repeat(3 * 1024 * 1024);
    const compressedBomb = await compress(bombSource);
    expect(compressedBomb.length).toBeLessThan(MAX_DECOMPRESSED_BYTES / 100);
    await expect(decompress(compressedBomb)).rejects.toThrow(
      /Decompressed payload exceeds maximum allowed size/,
    );
  });

  it("exposes MAX_DECOMPRESSED_BYTES as 2 MB for callers needing the constant", () => {
    expect(MAX_DECOMPRESSED_BYTES).toBe(2 * 1024 * 1024);
  });
});
