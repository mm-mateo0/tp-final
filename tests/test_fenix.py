"""Pruebas de autenticación HMAC."""
import pytest
from fenix.utils.crypto import signature, verify
from fenix.utils.errors import ValidationError

@pytest.mark.base
def test_signature_authenticates_raw_bytes():
    secret = "clave-ficticia-solo-test"
    body = b'{"x":1}'
    digest = signature(secret, 1000, body)
    header = f"t=1000,v1={digest}"
    verify(secret, header, body, now=1000)
    with pytest.raises(ValidationError):
        verify(secret, header, b'{"x": 1}', now=1000)

@pytest.mark.base
def test_hmac_rejects_bad_header_and_stale_timestamp():
    secret = "clave-ficticia-solo-test"
    body = b'{}'
    digest = signature(secret, 1000, body)
    for header in ("", f"t=1000,t=1000,v1={digest}",
                   f"t=1000,v1={digest},extra=x", "t=x,v1=abc"):
        with pytest.raises(ValidationError):
            verify(secret, header, body, now=1000)
    with pytest.raises(ValidationError):
        verify(secret, f"t=1000,v1={digest}", body, now=4600)
