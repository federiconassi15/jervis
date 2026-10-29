package org.jervis.companion.transport

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class RelayTransportTest {
    private val id = "a".repeat(32)
    private val token = "b".repeat(64)

    @Test fun enforcesOutboundWssWithNoEmbeddedSecrets() {
        assertEquals(
            "wss://relay.example/v1/$id/connect",
            RelayTransport.buildUrl("wss://relay.example/", id)
        )
        for (candidate in listOf(
            "ws://relay.example", "https://relay.example",
            "wss://alice:secret@relay.example",
            "wss://relay.example/?token=secret",
            "wss://relay.example/other",
            "wss://relay.example/#fragment"
        )) {
            assertThrows(IllegalArgumentException::class.java) {
                RelayTransport.buildUrl(candidate, id)
            }
        }
    }

    @Test fun transportCannotConnectWithoutValidDeviceIdentityOrToken() {
        assertThrows(IllegalArgumentException::class.java) {
            RelayTransport("wss://relay.example", "invalid", token, {})
        }
        assertThrows(IllegalArgumentException::class.java) {
            RelayTransport("wss://relay.example", id, "short", {})
        }
        val transport = RelayTransport(
            "wss://relay.example", id, token, {}
        )
        // No connection occurs in the constructor; sends are disabled.
        assertEquals(false, transport.sendCiphertext(
            org.jervis.companion.crypto.RelayFraming.Frame(
                1, "ciphertext", "c".repeat(32), 0L, "YQ"
            )
        ))
        transport.disconnect()
    }
}
