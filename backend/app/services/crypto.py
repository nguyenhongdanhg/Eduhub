import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
  secret = (os.getenv("EDUAI_SECRET_KEY") or "").strip()
  if not secret:
    raise RuntimeError("Missing EDUAI_SECRET_KEY")
  digest = hashlib.sha256(secret.encode("utf-8")).digest()
  key = base64.urlsafe_b64encode(digest)
  return Fernet(key)


def encrypt_text(value: str) -> str:
  token = _fernet().encrypt((value or "").encode("utf-8"))
  return token.decode("utf-8")


def decrypt_text(token: str) -> str:
  out = _fernet().decrypt((token or "").encode("utf-8"))
  return out.decode("utf-8")

