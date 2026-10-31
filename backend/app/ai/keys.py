"""Provider API keys (R49 A7): Fernet at rest, write-only, UI key wins over the .env key.

``AI_SECRETS_KEY`` lives only in ``.env``. Without a valid one, saving a key fails closed
(``SecretsKeyMissing`` -> 503) while keys from ``.env`` keep working. A saved key that can no
longer be decrypted (the secrets key changed) is treated as absent, never as an error.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import ENV_KEY_SETTING, PROVIDERS
from app.core.config import settings
from app.models.assistant import AiProviderKey

logger = logging.getLogger(__name__)

KeySource = Literal["ui", "env"]


class SecretsKeyMissing(Exception):
    """AI_SECRETS_KEY is unset or not a valid Fernet key: keys cannot be saved."""


@dataclass(frozen=True)
class ResolvedKey:
    """The key to use for a provider. Never log or serialize ``api_key``."""

    provider: str
    api_key: str
    source: KeySource

    def __repr__(self) -> str:
        return f"ResolvedKey(provider={self.provider!r}, source={self.source!r})"


def _fernet() -> Fernet | None:
    raw = settings.AI_SECRETS_KEY.strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return None


def secrets_key_set() -> bool:
    """True when ``AI_SECRETS_KEY`` is present and a valid Fernet key."""
    return _fernet() is not None


def encrypt_secret(plain: str) -> str:
    fernet = _fernet()
    if fernet is None:
        raise SecretsKeyMissing("AI_SECRETS_KEY is not set (or not a valid Fernet key)")
    return fernet.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str | None:
    """Plain text, or None when the secrets key is missing or does not match."""
    fernet = _fernet()
    if fernet is None:
        return None
    try:
        return fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def env_key(provider: str) -> str | None:
    name = ENV_KEY_SETTING.get(provider)
    value = getattr(settings, name, "") if name else ""
    return value.strip() or None


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    configured: bool
    source: KeySource | None
    last4: str | None
    set_at: datetime | None


class KeyStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _row(self, provider: str) -> AiProviderKey | None:
        return await self.session.get(AiProviderKey, provider)

    async def save(self, provider: str, api_key: str) -> None:
        """Encrypt and store ``api_key`` (raises SecretsKeyMissing without AI_SECRETS_KEY)."""
        ciphertext = encrypt_secret(api_key)
        row = await self._row(provider)
        if row is None:
            self.session.add(
                AiProviderKey(
                    provider=provider,
                    ciphertext=ciphertext,
                    last4=api_key[-4:],
                    set_at=datetime.now(UTC),
                )
            )
        else:
            row.ciphertext = ciphertext
            row.last4 = api_key[-4:]
            row.set_at = datetime.now(UTC)
        await self.session.flush()

    async def delete(self, provider: str) -> None:
        await self.session.execute(delete(AiProviderKey).where(AiProviderKey.provider == provider))

    async def resolve(self, provider: str) -> ResolvedKey | None:
        """UI-saved key, else the .env key, else None."""
        row = await self._row(provider)
        if row is not None:
            plain = decrypt_secret(row.ciphertext)
            if plain is not None:
                return ResolvedKey(provider, plain, "ui")
            logger.warning("saved key for %s cannot be decrypted; falling back to .env", provider)
        fallback = env_key(provider)
        if fallback is not None:
            return ResolvedKey(provider, fallback, "env")
        return None

    async def status(self, provider: str) -> ProviderStatus:
        """What the settings page shows: which source is active, masked tail and date."""
        row = await self._row(provider)
        if row is not None and decrypt_secret(row.ciphertext) is not None:
            return ProviderStatus(provider, True, "ui", row.last4, row.set_at)
        fallback = env_key(provider)
        if fallback is not None:
            return ProviderStatus(provider, True, "env", fallback[-4:], None)
        return ProviderStatus(provider, False, None, None, None)

    async def available_providers(self) -> set[str]:
        return {p for p in PROVIDERS if (await self.resolve(p)) is not None}


__all__ = [
    "KeySource",
    "KeyStore",
    "ProviderStatus",
    "ResolvedKey",
    "SecretsKeyMissing",
    "decrypt_secret",
    "encrypt_secret",
    "env_key",
    "secrets_key_set",
]
