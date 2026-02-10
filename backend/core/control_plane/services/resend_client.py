import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings


class ResendError(Exception):
    pass


def send_email(*, to_email: str, subject: str, html: str, text: str) -> str:
    api_key = (getattr(settings, "RESEND_API_KEY", "") or "").strip()
    if not api_key:
        raise ResendError("RESEND_API_KEY is not configured.")

    from_email = (
        (getattr(settings, "RESEND_FROM_EMAIL", "") or "").strip()
        or getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost")
    )

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text,
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        "https://api.resend.com/emails",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:  # nosec B310
            response_payload = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, ValueError) as exc:
        raise ResendError("Failed to send email with Resend.") from exc

    message_id = response_payload.get("id")
    if not message_id:
        raise ResendError("Resend did not return a message id.")
    return message_id
