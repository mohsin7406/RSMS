from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_SMSALERT_URL = "https://www.smsalert.co.in/api/push.json"


class SMSAlertError(RuntimeError):
    """Raised when SMSAlert cannot accept an SMS request."""


@dataclass(frozen=True)
class SMSResult:
    status_code: int
    body: str


def send_sms(*, api_key: str, sender: str, mobile: str, text: str,
             api_url: str | None = None, timeout: float = 10.0) -> SMSResult:
    if not api_key:
        raise SMSAlertError("SMSAlert API key is not configured")
    if not sender:
        raise SMSAlertError("SMSAlert sender ID is not configured")
    if not mobile:
        raise SMSAlertError("Mobile number is required")
    if not text:
        raise SMSAlertError("SMS text is required")

    url = api_url or DEFAULT_SMSALERT_URL
    params = urlencode({
        "apikey": api_key,
        "sender": sender,
        "mobileno": mobile,
        "text": text,
    })
    request = Request(f"{url}?{params}", method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            result = SMSResult(response.status, body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SMSAlertError(f"SMSAlert HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise SMSAlertError(f"SMSAlert connection failed: {exc.reason}") from exc

    if not 200 <= result.status_code < 300:
        raise SMSAlertError(f"SMSAlert HTTP {result.status_code}: {result.body}")
    return result
