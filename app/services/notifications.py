import logging

from flask import current_app

logger = logging.getLogger(__name__)


def send_sms(phone: str, message: str) -> bool:
    """Provider-agnostic SMS hook.

    Production providers should be implemented behind this interface. Until a
    provider is configured, messages are logged without exposing secrets or OTPs.
    """
    provider = current_app.config.get("SMS_PROVIDER", "none")
    if provider == "none":
        logger.info("SMS notification queued for provider=none phone_suffix=%s", phone[-4:])
        return False
    raise RuntimeError(f"Unsupported SMS provider: {provider}")


def send_whatsapp(phone: str, message: str) -> bool:
    """Provider-agnostic WhatsApp hook."""
    provider = current_app.config.get("WHATSAPP_PROVIDER", "none")
    if provider == "none":
        logger.info("WhatsApp notification queued for provider=none phone_suffix=%s", phone[-4:])
        return False
    raise RuntimeError(f"Unsupported WhatsApp provider: {provider}")


def notify_customer(phone: str, message: str) -> dict:
    return {
        "sms": send_sms(phone, message),
        "whatsapp": send_whatsapp(phone, message),
    }
