"""Service container.

Constructs the shared ZohoClient and the domain API facades, and exposes a
single object passed into the tool-registration functions. This keeps tool
modules free of construction logic and makes testing (with a mocked client)
straightforward.
"""

from __future__ import annotations

from .config import Settings, get_settings
from .zoho.ai_helpers import AIHelpers
from .zoho.candidates import CandidatesAPI
from .zoho.client import ZohoClient
from .zoho.email import EmailAPI
from .zoho.interviews import InterviewsAPI
from .zoho.jobs import JobsAPI
from .zoho.reports import ReportsAPI


class Services:
    def __init__(self, settings: Settings | None = None, client: ZohoClient | None = None):
        self.settings = settings or get_settings()
        self.client = client or ZohoClient(self.settings)
        self.candidates = CandidatesAPI(self.client)
        self.jobs = JobsAPI(self.client)
        self.interviews = InterviewsAPI(self.client)
        self.reports = ReportsAPI(self.client)
        self.email = EmailAPI(self.client)
        self.ai = AIHelpers(self.client)

    async def aclose(self) -> None:
        await self.client.aclose()
