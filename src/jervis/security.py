import base64,hashlib,hmac,os
ALGORITHM="pbkdf2_sha256";ITERATIONS=310000
def hash_passphrase(passphrase):
    if len(passphrase)<8:raise ValueError("passphrase must contain at least 8 characters")
    salt=os.urandom(16);digest=hashlib.pbkdf2_hmac("sha256",passphrase.encode(),salt,ITERATIONS)
    return "$".join((ALGORITHM,str(ITERATIONS),base64.urlsafe_b64encode(salt).decode(),base64.urlsafe_b64encode(digest).decode()))
def verify_passphrase(passphrase,encoded):
    try:
        alg,it,salt,digest=encoded.split("$",3)
        if alg!=ALGORITHM:return False
        actual=hashlib.pbkdf2_hmac("sha256",passphrase.encode(),base64.urlsafe_b64decode(salt),int(it))
        return hmac.compare_digest(actual,base64.urlsafe_b64decode(digest))
    except Exception:return False
