package org.jervis.companion.crypto

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class RelayFramingTest {
    @Test fun encryptedRoundTripAcrossTransportWrapper() {
        val instance = "a".repeat(32)
        val device = "b".repeat(32)
        val session = "c".repeat(32)
        val host = CompanionCrypto.newKeyPair()
        val phone = CompanionCrypto.newKeyPair()
        val sender = CompanionCrypto.deriveChannel(
            host, "host", instance, device, session,
            CompanionCrypto.publicDer(phone), CompanionCrypto.publicDer(host)
        )
        val receiver = CompanionCrypto.deriveChannel(
            phone, "phone", instance, device, session,
            CompanionCrypto.publicDer(phone), CompanionCrypto.publicDer(host)
        )
        val frame = RelayFraming.pack(sender.encrypt("hi".toByteArray()))
        assertEquals("ciphertext", frame.kind)
        assertArrayEquals("hi".toByteArray(),
                          receiver.decrypt(RelayFraming.unpack(frame)))
        assertThrows(IllegalArgumentException::class.java) {
            RelayFraming.unpack(frame.copy(seq = 9L))
        }
    }
}
