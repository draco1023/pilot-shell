/**
 * Deflate-raw compression with base64url encoding for URL-safe sharing.
 *
 * Uses CompressionStream('deflate-raw') — available in Chrome 80+, Firefox 113+, Safari 16.4+.
 * Uses Uint8Array.toBase64/fromBase64 (Chrome 128+, Safari 17.4+, Firefox 133+).
 *
 * SECURITY: /api/share caps the COMPRESSED data at 256 KB but deflate ratios
 * can exceed 1000:1 for adversarial payloads (a "zip bomb"). The reader
 * decompresses on the client, so an unguarded decompression of a maliciously
 * crafted share can exhaust the recipient's browser memory. The decompress()
 * function below streams the output chunk-by-chunk and aborts as soon as the
 * accumulated size exceeds MAX_DECOMPRESSED_BYTES.
 */

/**
 * Hard cap on decompressed share-payload size. The largest legitimate spec we
 * see in practice is ~50 KB markdown plus a handful of annotations — call it
 * 200 KB. 2 MB leaves comfortable headroom while keeping a worst-case
 * adversarial decompress well below browser-memory pressure.
 */
export const MAX_DECOMPRESSED_BYTES = 2 * 1024 * 1024;

export async function compress(data: string): Promise<string> {
  const byteArray = new TextEncoder().encode(data);
  const stream = new CompressionStream("deflate-raw");
  const writer = stream.writable.getWriter();
  writer.write(byteArray);
  writer.close();
  const buffer = await new Response(stream.readable).arrayBuffer();
  return new Uint8Array(buffer).toBase64({ alphabet: "base64url", omitPadding: true });
}

export async function decompress(b64: string): Promise<string> {
  // Uint8Array.fromBase64 is typed as Uint8Array<ArrayBufferLike> which TS 5.7+
  // refuses to pass to writer.write(BufferSource) because ArrayBufferLike includes
  // SharedArrayBuffer. Copy into a fresh ArrayBuffer-backed view to satisfy the type.
  const decoded = Uint8Array.fromBase64(b64, { alphabet: "base64url" });
  const byteArray = new Uint8Array(decoded.byteLength);
  byteArray.set(decoded);
  const stream = new DecompressionStream("deflate-raw");
  const writer = stream.writable.getWriter();
  // Swallow rejections on the write/close side. When we cancel the reader on
  // a too-big decompression, the writable side's pending promises reject —
  // surface the size-cap error to the caller, not an AbortError.
  const writePromise = writer.write(byteArray).catch(() => undefined);
  const closePromise = writer.close().catch(() => undefined);

  // Stream the output and abort if it grows past MAX_DECOMPRESSED_BYTES.
  // Accumulating the buffer first via `new Response(stream.readable)`
  // would happily fill RAM before our size check runs.
  const reader = stream.readable.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_DECOMPRESSED_BYTES) {
        // Free the rest of the stream and surface a deterministic error so
        // Shared.tsx can show the "Failed to load" path instead of OOMing.
        await reader.cancel();
        throw new Error(
          `Decompressed payload exceeds maximum allowed size (${MAX_DECOMPRESSED_BYTES} bytes)`,
        );
      }
      chunks.push(value);
    }
  } finally {
    // Drain the swallowed write/close promises so no dangling rejection escapes.
    await writePromise;
    await closePromise;
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(out);
}
