"""Bounded, temporary browser sessions for a single hosted worker."""
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

COOKIE = '__Host-everymind-session'
TTL = 20 * 60
MAX_SESSIONS = 4


@dataclass
class Session:
    touched: float
    service: object = None


class Sessions:
    def __init__(self):
        self.secret = secrets.token_bytes(32)
        self.items = {}

    def signature(self, identifier):
        return hmac.new(self.secret, identifier.encode(), hashlib.sha256).hexdigest()

    def acquire(self, cookie):
        now = time.monotonic()
        self.items = {key: value for key, value in self.items.items() if now - value.touched < TTL}
        identifier, separator, signature = (cookie or '').partition('.')
        valid = separator and hmac.compare_digest(signature, self.signature(identifier))
        if not valid or identifier not in self.items:
            if len(self.items) >= MAX_SESSIONS:
                return None, None
            identifier = secrets.token_urlsafe(32)
            self.items[identifier] = Session(now)
        session = self.items[identifier]
        session.touched = now
        return session, identifier + '.' + self.signature(identifier)
