import test from "node:test";
import assert from "node:assert/strict";
import { readJsonLimited } from "../src/lib/request-body";

function chunkedRequest(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Request("https://studio.example/api/test", {
    method: "POST",
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
    // Suppress the automatic content-length set by ordinary string bodies.
    duplex: "half",
  } as RequestInit);
}

test("bounded JSON reader accepts valid input without Content-Length", async () => {
  const result = await readJsonLimited(chunkedRequest(['{"a":', '1}']), 16);
  assert.deepEqual(result, { ok: true, value: { a: 1 } });
});

test("bounded JSON reader rejects chunked bodies as soon as their byte limit is exceeded", async () => {
  const result = await readJsonLimited(chunkedRequest(["1234", "5678", "9"]), 8);
  assert.deepEqual(result, { ok: false, status: 413 });
});

test("bounded JSON reader validates declared lengths and malformed JSON", async () => {
  const oversized = new Request("https://studio.example/api/test", {
    method: "POST",
    headers: { "content-length": "100" },
    body: "{}",
  });
  assert.deepEqual(await readJsonLimited(oversized, 10), { ok: false, status: 413 });

  const malformed = await readJsonLimited(
    new Request("https://studio.example/api/test", { method: "POST", body: "{" }),
    10,
  );
  assert.deepEqual(malformed, { ok: false, status: 400 });
});
