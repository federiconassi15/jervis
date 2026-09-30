from jervis.security import hash_passphrase, verify_passphrase


def test_passphrase_roundtrip():
    secret = "correct horse battery staple"
    encoded = hash_passphrase(secret)
    assert verify_passphrase(secret, encoded)
    assert not verify_passphrase("wrong password", encoded)
    assert secret not in encoded


def test_malformed_hash_fails_closed():
    assert not verify_passphrase("anything", "not-a-valid-hash")
