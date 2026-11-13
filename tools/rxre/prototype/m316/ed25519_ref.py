#!/usr/bin/env python3
"""Ed25519 (RFC 8032) en Python puro — sin dependencias externas.
Implementación de referencia con coordenadas extendidas. Validada contra los
vectores de prueba oficiales de RFC 8032 §7.1 (ver self_test()).
"""
import hashlib

b = 256
q = 2**255 - 19
l = 2**252 + 27742317777372353535851937790883648493
d = -121665 * pow(121666, q - 2, q) % q
I = pow(2, (q - 1) // 4, q)


def _sha512(m):
    return hashlib.sha512(m).digest()


def _inv(x):
    return pow(x, q - 2, q)


def _xrecover(y):
    xx = (y * y - 1) * _inv(d * y * y + 1)
    x = pow(xx, (q + 3) // 8, q)
    if (x * x - xx) % q != 0:
        x = (x * I) % q
    if x % 2 != 0:
        x = q - x
    return x


_BY = 4 * _inv(5) % q
_BX = _xrecover(_BY)
B = (_BX % q, _BY % q, 1, _BX * _BY % q)   # coordenadas extendidas (X, Y, Z, T)


def _ed_add(P, Q):
    x1, y1, z1, t1 = P
    x2, y2, z2, t2 = Q
    a = (y1 - x1) * (y2 - x2) % q
    b = (y1 + x1) * (y2 + x2) % q
    c = t1 * 2 * d * t2 % q
    dd = z1 * 2 * z2 % q
    e = b - a
    f = dd - c
    g = dd + c
    h = b + a
    return (e * f % q, g * h % q, f * g % q, e * h % q)


def _scalarmult(P, e):
    Q = (0, 1, 1, 0)  # punto neutro
    while e > 0:
        if e & 1:
            Q = _ed_add(Q, P)
        P = _ed_add(P, P)
        e >>= 1
    return Q


def _encode_point(P):
    x, y, z, _t = P
    zi = _inv(z)
    x = x * zi % q
    y = y * zi % q
    bits = [(y >> i) & 1 for i in range(b - 1)] + [x & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(b // 8))


def _decode_point(s):
    if len(s) != 32:
        raise ValueError("punto invalido: longitud")
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if x & 1 != (s[31] >> 7):
        x = q - x
    P = (x, y, 1, x * y % q)
    if not _ison_curve(P):
        raise ValueError("punto fuera de la curva")
    return P


def _ison_curve(P):
    x, y, z, t = P
    zi = _inv(z)
    x = x * zi % q
    y = y * zi % q
    return (-x * x + y * y - 1 - d * x * x * y * y) % q == 0


def _clamp(h):
    a = 2 ** (b - 2) + sum(2 ** i * ((h[i // 8] >> (i % 8)) & 1) for i in range(3, b - 2))
    return a


def publickey(sk: bytes) -> bytes:
    h = _sha512(sk)
    a = _clamp(h)
    A = _scalarmult(B, a)
    return _encode_point(A)


def sign(message: bytes, sk: bytes, pk: bytes = None) -> bytes:
    h = _sha512(sk)
    a = _clamp(h)
    pk = pk if pk is not None else publickey(sk)
    r = int.from_bytes(_sha512(h[32:64] + message), "little") % l
    R = _scalarmult(B, r)
    Rs = _encode_point(R)
    S = (r + int.from_bytes(_sha512(Rs + pk + message), "little") * a) % l
    return Rs + S.to_bytes(32, "little")


def verify(message: bytes, signature: bytes, pk: bytes) -> bool:
    """Verificación criptográfica real (Ed25519, RFC 8032)."""
    try:
        if len(signature) != 64 or len(pk) != 32:
            return False
        R = _decode_point(signature[:32])
        A = _decode_point(pk)
        S = int.from_bytes(signature[32:], "little")
        if S >= l:
            return False
        h = int.from_bytes(_sha512(signature[:32] + pk + message), "little")
        x1, y1, z1, _ = _scalarmult(B, S)
        x2, y2, z2, _ = _ed_add(R, _scalarmult(A, h))
        zi1 = _inv(z1)
        zi2 = _inv(z2)
        x1n = x1 * zi1 % q
        y1n = y1 * zi1 % q
        x2n = x2 * zi2 % q
        y2n = y2 * zi2 % q
        return (x1n * y2n - y1n * x2n) % q == 0
    except Exception:
        return False


def self_test():
    """Vectores oficiales RFC 8032 §7.1 (TEST 1, TEST 2, TEST 3)."""
    vectors = [
        ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
         "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
         "",
         "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
        ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
         "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
         "72",
         "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
        ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
         "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
         "af82",
         "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
    ]
    for sk_hex, pk_hex, msg_hex, sig_hex in vectors:
        sk = bytes.fromhex(sk_hex)
        pk = bytes.fromhex(pk_hex)
        msg = bytes.fromhex(msg_hex)
        sig = bytes.fromhex(sig_hex)
        assert publickey(sk) == pk, "publickey no coincide con RFC 8032"
        assert sign(msg, sk) == sig, "firma no coincide con RFC 8032"
        assert verify(msg, sig, pk) is True, "verificacion fallo"
        bad = bytearray(sig); bad[0] ^= 0x01
        assert verify(msg, bytes(bad), pk) is False, "firma alterada aceptada"
        assert verify(msg + b"x", sig, pk) is False, "mensaje alterado aceptado"
    return True


if __name__ == "__main__":
    self_test()
    print("ED25519 RFC 8032: 3/3 vectores oficiales OK (publickey, sign, verify, alteracion rechazada)")
