package org.jervis.companion.crypto

import java.nio.charset.StandardCharsets
import java.util.Base64
import java.util.UUID
import org.json.JSONObject

/** Strict transport wrapper: never replaces end-to-end channel authentication. */
object RelayFraming {
    data class Frame(
        val v: Int, val kind: String, val id: String, val seq: Long, val body: String
    )

    private val identifier = Regex("[0-9a-f]{32}")
    private val opaque = Regex("[A-Za-z0-9_-]{1,65536}")
    private const val MAX_SEQUENCE = 9_007_199_254_740_991L

    fun pack(message: CompanionCrypto.Envelope): Frame {
        require(message.v == 1 &&
                identifier.matches(message.session) &&
                message.direction in setOf("host", "phone") &&
                message.seq in 0..MAX_SEQUENCE &&
                message.body.matches(Regex("[A-Za-z0-9_-]{1,45000}"))) {
            "Invalid authenticated channel envelope"
        }
        val json = JSONObject()
            .put("v", 1)
            .put("session", message.session)
            .put("direction", message.direction)
            .put("seq", message.seq)
            .put("body", message.body)
            .toString()
            .toByteArray(StandardCharsets.US_ASCII)
        require(json.size <= 45500)
        val body = Base64.getUrlEncoder().withoutPadding().encodeToString(json)
        require(body.length <= 65536)
        return Frame(1, "ciphertext",
                     UUID.randomUUID().toString().replace("-", ""),
                     message.seq, body)
    }

    fun unpack(frame: Frame): CompanionCrypto.Envelope {
        require(frame.v == 1 && frame.kind == "ciphertext" &&
                identifier.matches(frame.id) && frame.seq in 0..MAX_SEQUENCE &&
                opaque.matches(frame.body)) {
            "Invalid relay frame"
        }
        val decoded = Base64.getUrlDecoder().decode(frame.body)
        require(decoded.size <= 45500)
        val obj = JSONObject(String(decoded, StandardCharsets.US_ASCII))
        val names = obj.keys().asSequence().toSet()
        require(names == setOf("v", "session", "direction", "seq", "body"))
        require(obj.get("seq") is Number && obj.get("seq") !is Double)
        val message = CompanionCrypto.Envelope(
            obj.getInt("v"), obj.getString("session"),
            obj.getString("direction"), obj.getLong("seq"), obj.getString("body")
        )
        require(message.v == 1 && identifier.matches(message.session) &&
                message.direction in setOf("host", "phone") &&
                message.seq == frame.seq &&
                message.body.matches(Regex("[A-Za-z0-9_-]{1,45000}"))) {
            "Untrusted relay frame does not match encrypted envelope"
        }
        return message
    }
}
