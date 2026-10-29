import test from "node:test";
import assert from "node:assert/strict";
import {
  digest, sameHash, readSmallJson, safeBearer,
  validateFrame, validInstance, validSecret,
} from "../src/validate.mjs";

test("opaque routing identifiers and bearer tokens are strict", () => {
  assert.equal(validInstance("f".repeat(32)), true);
  assert.equal(validInstance("f".repeat(31)), false);
  assert.equal(validSecret("a".repeat(64)), true);
  assert.equal(validSecret("a".repeat(63)), false);
  assert.equal(safeBearer(new Request("https://example.com", {
    headers: { Authorization: "Bearer " + "a".repeat(64) },
  })), "a".repeat(64));
  assert.equal(safeBearer(new Request("https://example.com", {
    headers: { Authorization: "Bearer secret" },
  })), null);
});

test("hashing and fixed-length digest comparison", async () => {
  const first = await digest("a".repeat(64));
  const second = await digest("b".repeat(64));
  assert.equal(first.length, 64);
  assert.equal(sameHash(first, first), true);
  assert.equal(sameHash(first, second), false);
  assert.equal(sameHash(first, null), false);
});

test("cannot relay arbitrary plaintext JSON structures", () => {
  const ok = {
    v: 1, kind: "ciphertext", id: "1".repeat(32),
    seq: 0, body: "A-_b",
  };
  assert.equal(validateFrame(ok), true);
  assert.equal(validateFrame({ ...ok, plaintext: "private chat" }), false);
  assert.equal(validateFrame({ ...ok, seq: -1 }), false);
  assert.equal(validateFrame({ ...ok, body: "plain text here" }), false);
  assert.equal(validateFrame({ ...ok, kind: "command" }), false);
  assert.equal(validateFrame({ ...ok, id: "../../etc" }), false);
});

test("JSON body is bounded and content type checked", async () => {
  const valid = new Request("https://example.com", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: "a".repeat(32) }),
  });
  assert.equal((await readSmallJson(valid)).device_id, "a".repeat(32));
  const tooBig = new Request("https://example.com", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value: "x".repeat(9000) }),
  });
  await assert.rejects(() => readSmallJson(tooBig), /Body too large/);
});
