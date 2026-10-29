/** Small, independently testable validation helpers for the Jervis relay. */
const HEX_ID = /^[0-9a-f]{32}$/;
const HEX_KEY = /^[0-9a-f]{64}$/;
const BASE64URL = /^[A-Za-z0-9_-]{1,65536}$/;

export function validInstance(id) {
  return typeof id === "string" && HEX_ID.test(id);
}
export function validSecret(value) {
  return typeof value === "string" && HEX_KEY.test(value);
}
export function safeBearer(request) {
  const authorization = request.headers.get("Authorization") || "";
  const match = /^Bearer ([0-9a-f]{64})$/.exec(authorization);
  return match ? match[1] : null;
}
export async function digest(secret) {
  if (!validSecret(secret)) throw new Error("Invalid bearer format");
  const bytes = new TextEncoder().encode(secret);
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(hash, b => b.toString(16).padStart(2, "0")).join("");
}
export function sameHash(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== 64 || b.length !== 64) return false;
  // Fixed-length comparison without bailing out on first mismatch.
  let difference = 0;
  for (let i = 0; i < 64; i++) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
}
export async function readSmallJson(request, bytes = 2048) {
  if (request.headers.get("Content-Type")?.split(";")[0] !== "application/json") {
    throw new Error("Expected JSON content type");
  }
  if (!request.body) throw new Error("Missing request body");
  const reader = request.body.getReader();
  const pieces = [];
  let total = 0;
  try {
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      total += result.value.byteLength;
      if (total > bytes) throw new Error("Body too large");
      pieces.push(result.value);
    }
  } finally {
    reader.releaseLock();
  }
  const raw = new Uint8Array(total);
  let offset = 0;
  for (const piece of pieces) { raw.set(piece, offset); offset += piece.byteLength; }
  const data = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("Expected a JSON object");
  }
  return data;
}
export function validateFrame(frame) {
  if (!frame || typeof frame !== "object" || Array.isArray(frame)) return false;
  const fields = Object.keys(frame).sort();
  if (fields.join(",") !== "body,id,kind,seq,v") return false;
  if (frame.v !== 1 || !["handshake", "ciphertext"].includes(frame.kind)) return false;
  if (!validInstance(frame.id)) return false;
  if (!Number.isSafeInteger(frame.seq) || frame.seq < 0) return false;
  return typeof frame.body === "string" && BASE64URL.test(frame.body);
}
