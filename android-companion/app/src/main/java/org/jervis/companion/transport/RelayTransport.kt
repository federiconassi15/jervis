package org.jervis.companion.transport

import java.net.URI
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import org.jervis.companion.crypto.RelayFraming

/**
 * Outbound-only WSS transport. This class does not pair devices, create identity,
 * decrypt data, grant permissions or execute commands. Nothing connects until
 * an authenticated caller explicitly invokes connect().
 */
class RelayTransport(
    endpoint: String,
    private val instanceId: String,
    private val bearer: String,
    private val eventListener: (Event) -> Unit,
    private val http: OkHttpClient = OkHttpClient.Builder()
        .pingInterval(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false)
        .build(),
) {
    sealed class Event {
        data object Connected : Event()
        data object Disconnected : Event()
        data class Ciphertext(val frame: RelayFraming.Frame) : Event()
        data object InvalidFrame : Event()
        data object TransportError : Event()
    }

    private val url: String
    @Volatile private var socket: WebSocket? = null
    @Volatile private var active = false
    @Volatile private var connected = false

    init {
        require(instanceId.matches(Regex("[0-9a-f]{32}"))) {
            "Invalid instance identifier"
        }
        require(bearer.matches(Regex("[0-9a-f]{64}"))) {
            "Invalid relay bearer token"
        }
        url = buildUrl(endpoint, instanceId)
    }

    @Synchronized
    fun connect() {
        check(!active) { "Relay transport is already active" }
        active = true
        connected = false
        // The credential is only in the authorization header, never URL/query.
        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $bearer")
            .build()
        try {
            socket = http.newWebSocket(request, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    connected = true
                    notifyEvent(Event.Connected)
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    if (text.length > 65536) {
                        notifyEvent(Event.InvalidFrame)
                        webSocket.close(1009, "Frame too large")
                        return
                    }
                    try {
                        val data = JSONObject(text)
                        require(data.keys().asSequence().toSet() == setOf(
                            "v", "kind", "id", "seq", "body"
                        ))
                        val frame = RelayFraming.Frame(
                            data.getInt("v"), data.getString("kind"),
                            data.getString("id"), data.getLong("seq"),
                            data.getString("body")
                        )
                        RelayFraming.unpack(frame) // reject malformed opaque data
                        notifyEvent(Event.Ciphertext(frame))
                    } catch (_: Exception) {
                        notifyEvent(Event.InvalidFrame)
                    }
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    connected = false
                    webSocket.close(1000, "Client closing")
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    active = false
                    connected = false
                    notifyEvent(Event.Disconnected)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    active = false
                    connected = false
                    // Never display exception strings; they may reveal endpoints.
                    notifyEvent(Event.TransportError)
                }
            })
        } catch (e: Exception) {
            active = false
            connected = false
            throw IllegalStateException("Unable to establish relay transport", e)
        }
    }

    @Synchronized
    fun sendCiphertext(frame: RelayFraming.Frame): Boolean {
        if (!active || !connected) return false
        // This is transport-only validation. SecureChannel.decrypt() at the
        // recipient must still authenticate the inner ciphertext and sequence.
        RelayFraming.unpack(frame)
        val obj = JSONObject()
            .put("v", frame.v)
            .put("kind", frame.kind)
            .put("id", frame.id)
            .put("seq", frame.seq)
            .put("body", frame.body)
        return socket?.send(obj.toString()) == true
    }

    @Synchronized
    fun disconnect() {
        active = false
        connected = false
        socket?.close(1000, "Client disconnected")
        socket = null
    }

    private fun notifyEvent(event: Event) {
        try {
            eventListener(event)
        } catch (_: Exception) {
            // Consumer errors cannot be allowed to crash the network loop.
        }
    }

    companion object {
        fun buildUrl(endpoint: String, instanceId: String): String {
            require(instanceId.matches(Regex("[0-9a-f]{32}")))
            val parsed = URI(endpoint)
            require(parsed.scheme == "wss" && !parsed.host.isNullOrBlank() &&
                    parsed.userInfo == null && parsed.rawQuery == null &&
                    parsed.rawFragment == null && parsed.rawPath in setOf("", "/")) {
                "Relay endpoint must be a clean WSS origin"
            }
            require(parsed.port in -1..65535 && parsed.port != 0)
            return parsed.toASCIIString().trimEnd('/') +
                "/v1/$instanceId/connect"
        }
    }
}
