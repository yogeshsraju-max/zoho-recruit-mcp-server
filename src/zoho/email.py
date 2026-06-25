"""Candidate email automation.

Zoho Recruit can send templated email to a candidate record. The exact action
path varies by account/edition, so the endpoint is centralised here and clearly
marked for confirmation.

ENDPOINT (confirm for your account):
    POST /Candidates/{candidate_id}/actions/send_mail
    body: {"data": [{"from": {...}, "to": [...], "subject": ..., "content": ...,
                      "mail_template": {"id": "<template_id>"}}]}

Some accounts instead expose templated mail merge via the Mail Merge API or a
custom function. If your account uses a different mechanism, adjust
``_SEND_MAIL_PATH`` and the payload builder below.
"""

from __future__ import annotations

from typing import Any

from ..utils.error_handler import InvalidInputError
from .client import ZohoClient
from .common import MODULE_CANDIDATES

# Built-in template aliases -> readable subject lines used when no Zoho template
# id is supplied. These produce ad-hoc emails; for branded templates pass a
# template id from your Zoho account.
TEMPLATE_PRESETS = {
    "rejection": "Update on your application",
    "interview_invitation": "Interview invitation",
    "follow_up": "Following up on your application",
    "offer": "Your offer",
}

# --- ENDPOINT CONFIGURATION -------------------------------------------------
_SEND_MAIL_PATH = "/{module}/{candidate_id}/actions/send_mail"
# ---------------------------------------------------------------------------


class EmailAPI:
    def __init__(self, client: ZohoClient):
        self._client = client

    async def send(
        self,
        *,
        candidate_id: str,
        template: str | None = None,
        subject: str | None = None,
        message: str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        if not candidate_id:
            raise InvalidInputError("candidate_id is required")
        if not message and not template_id:
            raise InvalidInputError(
                "Provide either a message body or a Zoho template_id."
            )

        resolved_subject = subject or TEMPLATE_PRESETS.get(
            template or "", "A message regarding your application"
        )
        mail: dict[str, Any] = {
            "subject": resolved_subject,
        }
        if message:
            mail["content"] = message
        if template_id:
            mail["mail_template"] = {"id": template_id}

        path = _SEND_MAIL_PATH.format(
            module=MODULE_CANDIDATES, candidate_id=candidate_id
        )
        resp = await self._client.post(path, json={"data": [mail]})
        return {
            "status": "sent",
            "candidate_id": candidate_id,
            "template": template,
            "subject": resolved_subject,
            "raw": resp,
        }
