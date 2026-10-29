package org.jervis.companion.crypto

import java.math.BigInteger
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.KeyPair
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECPrivateKeySpec
import java.security.spec.ECParameterSpec
import java.security.spec.X509EncodedKeySpec
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class CompanionCryptoTest {
    private val instance = "a".repeat(32)
    private val device = "b".repeat(32)
    private val session = "c".repeat(32)

    private fun fromHex(value: String): ByteArray =
        value.chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    private fun fixedKey(scalar: String, publicKey: String): KeyPair {
        val parameters = AlgorithmParameters.getInstance("EC")
        parameters.init(ECGenParameterSpec("secp256r1"))
        val spec = parameters.getParameterSpec(ECParameterSpec::class.java)
        val factory = KeyFactory.getInstance("EC")
        val private = factory.generatePrivate(ECPrivateKeySpec(BigInteger(scalar), spec))
        val public = factory.generatePublic(X509EncodedKeySpec(fromHex(publicKey)))
        return KeyPair(public, private)
    }

    @Test fun matchesPythonKnownAnswer() {
        val phoneDer = "3059301306072a8648ce3d020106082a8648ce3d030107034200040e4496255826838387e43d5b362325626dd8d5c307ffb7f12031591ba610798bcdcc5c57979635cf7319ebc721f4395a8e4224e897ee4425989cb8dd69559d53"
        val hostDer = "3059301306072a8648ce3d020106082a8648ce3d0301070342000438f278494e162c539a5f6519649d3cd48b7f715ffaeda8381545bd8b61040747f87819bfca19fb9f22c87fc087bf9b5b6ffd325546ccf53da7f1ab53dbea5530"
        val host = fixedKey("987654321098765432109876543210987654321", hostDer)
        val phone = fixedKey("123456789012345678901234567890123456789", phoneDer)
        val hostChannel = CompanionCrypto.deriveChannel(
            host, "host", instance, device, session, fromHex(phoneDer), fromHex(hostDer)
        )
        val phoneChannel = CompanionCrypto.deriveChannel(
            phone, "phone", instance, device, session, fromHex(phoneDer), fromHex(hostDer)
        )
        val message = hostChannel.encrypt("hello".toByteArray())
        assertEquals("QujQy5pq4dQVN5iMFpw_wmjynu3W", message.body)
        assertArrayEquals("hello".toByteArray(), phoneChannel.decrypt(message))
        assertThrows(IllegalArgumentException::class.java) {
            phoneChannel.decrypt(message)
        }
    }

    @Test fun forgedHostSignatureFails() {
        val identity = CompanionCrypto.newKeyPair()
        val otherIdentity = CompanionCrypto.newKeyPair()
        val phone = CompanionCrypto.newKeyPair()
        val host = CompanionCrypto.newKeyPair()
        val sig = CompanionCrypto.hostSignature(
            identity, instance, device, session,
            CompanionCrypto.publicDer(phone), CompanionCrypto.publicDer(host)
        )
        assertThrows(IllegalArgumentException::class.java) {
            CompanionCrypto.verifyHost(
                CompanionCrypto.publicDer(otherIdentity), sig,
                instance, device, session,
                CompanionCrypto.publicDer(phone), CompanionCrypto.publicDer(host)
            )
        }
    }
}
