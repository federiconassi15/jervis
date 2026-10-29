/** Jervis relay: authenticated opaque outbound-only WebSockets.

No chat content is interpreted or stored. The *host* is solely responsible for
pairing consent, end-to-end encryption, device permissions and action checks.
This is an experimental deployment component, not a complete Jervis Companion.
*/
import {
  digest, sameHash, readSmallJson, safeBearer,
  validInstance, validSecret, validateFrame,
} from "./validate.mjs";

const MAX_DEVICES = 8;
const MAX_CONNECTIONS = 12;
const MAX_FRAME_BYTES = 64 * 1024;
const RATE_WINDOW_MS = 1000;
const RATE_MESSAGES = 40;

function response(status, message) {
  return new Response(JSON.stringify({ error: message }), {
    status, headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
function constantTimeString(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const route = /^\/v1\/([0-9a-f]{32})\/(init|grant|revoke|connect)$/.exec(url.pathname);
    if (!route) return response(404, "Not found");
    if (url.search || url.hash) return response(400, "Queries are not permitted");
    if (route[2] === "init") {
      if (request.method !== "POST" ||
          !constantTimeString(request.headers.get("X-Relay-Admin"),
                              env.RELAY_ADMIN_SECRET)) {
        return response(403, "Initialization denied");
      }
    }
    if (route[2] === "connect" && request.headers.get("Origin")) {
      // Browser-origin WebSocket clients are intentionally unsupported;
      // native Android and the Python host use Authorization headers.
      return response(403, "Browser-origin connections disabled");
    }
    const id = env.ROOMS.idFromName(route[1]);
    const room = env.ROOMS.get(id);
    const headers = new Headers(request.headers);
    headers.delete("X-Relay-Admin");
    return room.fetch(new Request(request, { headers }));
  },
};

/** One Durable Object per independent Jervis instance. */
export class RelayRoom {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
  }

  async _authorized(request) {
    const token = safeBearer(request);
    if (!token) return null;
    const hashed = await digest(token);
    const hostHash = await this.ctx.storage.get("host_hash");
    if (sameHash(hashed, hostHash)) return { role: "host", id: "host" };
    const devices = await this.ctx.storage.list({ prefix: "device:" });
    for (const [id, value] of devices) {
      if (sameHash(hashed, value)) return { role: "device", id: id.slice(7) };
    }
    return null;
  }

  async fetch(request) {
    const path = new URL(request.url).pathname.split("/").at(-1);
    if (path === "init") {
      if (request.method !== "POST") return response(405, "Method not allowed");
      let data;
      try { data = await readSmallJson(request); }
      catch { return response(400, "Invalid initialization payload"); }
      if (!validSecret(data.host_token)) return response(400, "Invalid host token");
      const hashed = await digest(data.host_token);
      let created = false;
      await this.ctx.storage.transaction(async tx => {
        if (await tx.get("host_hash")) return;
        await tx.put("host_hash", hashed);
        created = true;
      });
      return created ? new Response(null, { status: 204 }) :
                       response(409, "Instance already initialized");
    }

    const actor = await this._authorized(request);
    if (!actor) return response(401, "Invalid or revoked credentials");

    if (path === "grant") {
      if (request.method !== "POST" || actor.role !== "host")
        return response(403, "Host-only operation");
      let data;
      try { data = await readSmallJson(request); }
      catch { return response(400, "Invalid grant payload"); }
      if (!validInstance(data.device_id) || !validSecret(data.token))
        return response(400, "Invalid device grant");
      const tokenHash = await digest(data.token);
      let added = false, full = false;
      await this.ctx.storage.transaction(async tx => {
        const devices = await tx.list({ prefix: "device:" });
        if (devices.has("device:" + data.device_id)) return;
        if (devices.size >= MAX_DEVICES) { full = true; return; }
        await tx.put("device:" + data.device_id, tokenHash);
        added = true;
      });
      return added ? new Response(null, { status: 204 }) :
             full ? response(429, "Paired device limit reached") :
                    response(409, "Device already registered");
    }

    if (path === "revoke") {
      if (request.method !== "POST" || actor.role !== "host")
        return response(403, "Host-only operation");
      let data;
      try { data = await readSmallJson(request); }
      catch { return response(400, "Invalid revocation payload"); }
      if (!validInstance(data.device_id)) return response(400, "Invalid device id");
      await this.ctx.storage.delete("device:" + data.device_id);
      for (const socket of this.ctx.getWebSockets()) {
        const identity = socket.deserializeAttachment();
        if (identity?.id === data.device_id) socket.close(4003, "Device revoked");
      }
      return new Response(null, { status: 204 });
    }

    if (path !== "connect") return response(404, "Not found");
    if (request.method !== "GET" || request.headers.get("Upgrade")?.toLowerCase() !== "websocket")
      return response(426, "WebSocket upgrade required");
    const sockets = this.ctx.getWebSockets();
    if (sockets.length >= MAX_CONNECTIONS)
      return response(429, "Connection limit reached");
    if (actor.role === "host" && sockets.some(s => s.deserializeAttachment()?.role === "host"))
      return response(409, "Host already connected");
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    this.ctx.acceptWebSocket(server);
    server.serializeAttachment({ ...actor, window: 0, count: 0 });
    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(socket, message) {
    const actor = socket.deserializeAttachment();
    if (!actor || typeof message !== "string" ||
        new TextEncoder().encode(message).byteLength > MAX_FRAME_BYTES) {
      socket.close(1009, "Invalid frame");
      return;
    }
    // Recheck device registration at the message boundary, not just at connect.
    if (actor.role === "device" && !(await this.ctx.storage.get("device:" + actor.id))) {
      socket.close(4003, "Device revoked");
      return;
    }
    const now = Date.now();
    const count = now - actor.window < RATE_WINDOW_MS ? actor.count + 1 : 1;
    if (count > RATE_MESSAGES) {
      socket.close(1013, "Rate limit");
      return;
    }
    actor.count = count;
    actor.window = count === 1 ? now : actor.window;
    socket.serializeAttachment(actor);
    let frame;
    try { frame = JSON.parse(message); }
    catch { socket.close(1003, "Invalid JSON"); return; }
    if (!validateFrame(frame)) {
      socket.close(1003, "Invalid envelope");
      return;
    }
    for (const target of this.ctx.getWebSockets()) {
      if (target === socket) continue;
      const peer = target.deserializeAttachment();
      // No device-to-device forwarding, and no arbitrary target selection.
      if (actor.role === "host" && peer?.role === "device" ||
          actor.role === "device" && peer?.role === "host") {
        target.send(message);
      }
    }
  }

  webSocketClose(socket) {
    try { socket.close(1000, "Closed"); } catch {}
  }

  webSocketError(socket) {
    try { socket.close(1011, "Transport error"); } catch {}
  }
}
