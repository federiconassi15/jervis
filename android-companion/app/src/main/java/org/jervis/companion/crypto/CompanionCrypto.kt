package org.jervis.companion.crypto

import java.io.ByteArrayOutputStream
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.charset.StandardCharsets
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PublicKey
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Experimental, standalone wire crypto shared with the Python Jervis host.
 *
 * No network, pairing approval, data persistence, permissions or device commands
 * happen here. Identity keys must be provisioned securely, never hardcoded.
 */
object CompanionCrypto {
    private val context = "JERVIS-COMPANION-E2E-V1".toByteArray(StandardCharsets.US_ASCII)
    private const val MAX_SEQUENCE = 9_007_199_254_740_991L // Safe JS JSON integer
    private const val MAX_PLAINTEXT = 32768

    data class Envelope(
        val v: Int, val session: String, val direction: String,
        val seq: Long, val body: String
    )

    class Channel internal constructor(
        private val session: String,
        private val role: String,
        private val sendKey: ByteArray,
        private val receiveKey: ByteArray,
        private val sendPrefix: ByteArray,
        private val receivePrefix: ByteArray,
    ) {
        private var nextSend = 0L
        private var lastReceived = -1L

        private fun aad(direction: String, seq: Long): ByteArray =
            context + hexBytes(session) + direction.toByteArray(StandardCharsets.US_ASCII) +
                ByteBuffer.allocate(8).putLong(seq).array()

        @Synchronized
        fun encrypt(plaintext: ByteArray): Envelope {
            require(plaintext.size <= MAX_PLAINTEXT) { "Message exceeds size limit" }
            check(nextSend <= MAX_SEQUENCE) { "Rekey before sequence exhaustion" }
            val seq = nextSend
            val nonce = sendPrefix + ByteBuffer.allocate(8).putLong(seq).array()
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(sendKey, "AES"),
                        GCMParameterSpec(128, nonce))
            cipher.updateAAD(aad(role, seq))
            val ciphertext = cipher.doFinal(plaintext)
            nextSend++
            return Envelope(
                1, session, role, seq,
                Base64.getUrlEncoder().withoutPadding().encodeToString(ciphertext)
            )
        }

        @Synchronized
        fun decrypt(message: Envelope): ByteArray {
            val direction = if (role == "host") "phone" else "host"
            require(message.v == 1 && message.session == session &&
                    message.direction == direction &&
                    message.seq > lastReceived && message.seq <= MAX_SEQUENCE) {
                "Unexpected session, direction or replayed sequence"
            }
            require(message.body.matches(Regex("[A-Za-z0-9_-]{1,45000}"))) {
                "Invalid encrypted payload encoding"
            }
            val bytes = Base64.getUrlDecoder().decode(message.body)
            require(bytes.size in 16..(MAX_PLAINTEXT + 16)) { "Invalid cipher size" }
            val nonce = receivePrefix + ByteBuffer.allocate(8).putLong(message.seq).array()
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(receiveKey, "AES"),
                        GCMParameterSpec(128, nonce))
            cipher.updateAAD(aad(direction, message.seq))
            val result = cipher.doFinal(bytes)
            lastReceived = message.seq
            return result
        }
    }

    fun newKeyPair(): KeyPair = KeyPairGenerator.getInstance("EC").apply {
        initialize(ECGenParameterSpec("secp256r1"))
    }.generateKeyPair()

    fun publicDer(pair: KeyPair): ByteArray = pair.public.encoded

    private fun hexBytes(value: String): ByteArray {
        require(value.matches(Regex("[0-9a-f]{32}"))) { "Expected 128-bit hex identifier" }
        return ByteArray(16) { index ->
            value.substring(index * 2, index * 2 + 2).toInt(16).toByte()
        }
    }

    private fun checkedPublic(encoded: ByteArray): PublicKey {
        require(encoded.size <= 256) { "Invalid key size" }
        val key = KeyFactory.getInstance("EC")
            .generatePublic(X509EncodedKeySpec(encoded)) as ECPublicKey
        // Accept only P-256: its order is a standardized 256-bit prime.
        val expected = BigInteger(
            "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551", 16
        )
        require(key.params.order == expected && key.encoded.contentEquals(encoded)) {
            "Expected canonical P-256 key"
        }
        return key
    }

    private fun transcript(
        kind: String, instance: String, device: String, session: String,
        phoneEphemeral: ByteArray, hostEphemeral: ByteArray = byteArrayOf(),
    ): ByteArray {
        val items = listOf(
            context, kind.toByteArray(StandardCharsets.US_ASCII),
            hexBytes(instance), hexBytes(device), hexBytes(session),
            phoneEphemeral, hostEphemeral
        )
        val out = ByteArrayOutputStream()
        for (item in items) {
            require(item.size <= 65535)
            out.write((item.size shr 8) and 0xff)
            out.write(item.size and 0xff)
            out.write(item)
        }
        return out.toByteArray()
    }

    fun phoneSignature(
        signingIdentity: KeyPair, instance: String, device: String,
        session: String, phoneEphemeral: ByteArray,
    ): ByteArray {
        checkedPublic(phoneEphemeral)
        return Signature.getInstance("SHA256withECDSA").run {
            initSign(signingIdentity.private)
            update(transcript("phone", instance, device, session, phoneEphemeral))
            sign()
        }
    }

    fun verifyPhone(
        pinnedPhoneIdentity: ByteArray, signature: ByteArray,
        instance: String, device: String, session: String,
        phoneEphemeral: ByteArray,
    ) {
        checkedPublic(phoneEphemeral)
        val verifier = Signature.getInstance("SHA256withECDSA")
        verifier.initVerify(checkedPublic(pinnedPhoneIdentity))
        verifier.update(transcript("phone", instance, device, session, phoneEphemeral))
        require(verifier.verify(signature)) { "Phone identity handshake failed" }
    }

    fun hostSignature(
        signingIdentity: KeyPair, instance: String, device: String,
        session: String, phoneEphemeral: ByteArray, hostEphemeral: ByteArray,
    ): ByteArray {
        checkedPublic(phoneEphemeral)
        checkedPublic(hostEphemeral)
        return Signature.getInstance("SHA256withECDSA").run {
            initSign(signingIdentity.private)
            update(transcript("host", instance, device, session,
                              phoneEphemeral, hostEphemeral))
            sign()
        }
    }

    fun verifyHost(
        pinnedHostIdentity: ByteArray, signature: ByteArray,
        instance: String, device: String, session: String,
        phoneEphemeral: ByteArray, hostEphemeral: ByteArray,
    ) {
        checkedPublic(phoneEphemeral)
        checkedPublic(hostEphemeral)
        val verifier = Signature.getInstance("SHA256withECDSA")
        verifier.initVerify(checkedPublic(pinnedHostIdentity))
        verifier.update(transcript("host", instance, device, session,
                                   phoneEphemeral, hostEphemeral))
        require(verifier.verify(signature)) { "Host identity handshake failed" }
    }

    private fun hmac(key: ByteArray, data: ByteArray): ByteArray =
        Mac.getInstance("HmacSHA256").run {
            init(SecretKeySpec(key, "HmacSHA256"))
            doFinal(data)
        }

    private fun expandHkdf(shared: ByteArray, salt: ByteArray, info: ByteArray): ByteArray {
        val prk = hmac(salt, shared)
        val output = ByteArrayOutputStream()
        var previous = byteArrayOf()
        for (counter in 1..3) {
            previous = hmac(prk, previous + info + byteArrayOf(counter.toByte()))
            output.write(previous)
        }
        return output.toByteArray().copyOf(72)
    }

    fun deriveChannel(
        ephemeral: KeyPair, role: String,
        instance: String, device: String, session: String,
        phoneEphemeral: ByteArray, hostEphemeral: ByteArray,
    ): Channel {
        require(role == "host" || role == "phone")
        require(publicDer(ephemeral).contentEquals(
            if (role == "host") hostEphemeral else phoneEphemeral
        )) { "Local key does not match handshake transcript" }
        val peer = checkedPublic(if (role == "host") phoneEphemeral else hostEphemeral)
        val agreement = KeyAgreement.getInstance("ECDH")
        agreement.init(ephemeral.private)
        agreement.doPhase(peer, true)
        val shared = agreement.generateSecret()
        val salt = MessageDigest.getInstance("SHA-256").digest(
            transcript("keys", instance, device, session,
                       phoneEphemeral, hostEphemeral)
        )
        val material = expandHkdf(
            shared, salt,
            context + "/aes-gcm-key-material".toByteArray(StandardCharsets.US_ASCII)
        )
        val h2p = material.copyOfRange(0, 32)
        val p2h = material.copyOfRange(32, 64)
        val hostPrefix = material.copyOfRange(64, 68)
        val phonePrefix = material.copyOfRange(68, 72)
        return if (role == "host") {
            Channel(session, role, h2p, p2h, hostPrefix, phonePrefix)
        } else {
            Channel(session, role, p2h, h2p, phonePrefix, hostPrefix)
        }
    }
}
