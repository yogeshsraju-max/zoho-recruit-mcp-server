"""AI-assist helpers.

These tools return *structured, deterministic* output the recruiter (or Claude)
can reason over. They intentionally avoid calling external LLMs from inside the
server so the MCP server stays self-contained and predictable.

  * resume_parse        - extract text + heuristic fields from a resume PDF.
                          Optionally delegates to Zoho's Resume Parser API.
  * candidate_match     - skill/keyword overlap score vs a job description.
  * summarize_interview - structure a free-form transcript into sections.
"""

from __future__ import annotations

import base64
import io
import re
from typing import Any

from ..utils.error_handler import InvalidInputError, NotConfiguredError
from .client import ZohoClient

# Common technical keywords used for lightweight skill extraction. Extend as
# needed for your domain.
_COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "react", "react.js", "node",
    "node.js", "django", "fastapi", "flask", "spring", "go", "golang", "rust",
    "c++", "c#", ".net", "sql", "postgresql", "mysql", "mongodb", "redis",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "kafka",
    "graphql", "rest", "microservices", "ci/cd", "machine learning", "ml",
    "nlp", "pytorch", "tensorflow", "data analysis", "pandas", "numpy",
    "product management", "agile", "scrum", "jira",
]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:years|yrs)", re.IGNORECASE)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from a PDF using pypdf if available."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise NotConfiguredError(
            "pypdf is not installed; cannot extract PDF text locally. "
            "Install pypdf or configure the Zoho Resume Parser endpoint."
        ) from exc
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _heuristic_fields(text: str) -> dict[str, Any]:
    lower = text.lower()
    skills = sorted({s for s in _COMMON_SKILLS if s in lower})
    emails = _EMAIL_RE.findall(text)
    phones = _PHONE_RE.findall(text)
    years = [int(m) for m in _YEARS_RE.findall(text)]
    # Naive section splits.
    companies = _section(text, ["experience", "employment", "work history"])
    education = _section(text, ["education", "academics", "qualification"])
    projects = _section(text, ["projects", "key projects"])
    return {
        "skills": skills,
        "experience_years": max(years) if years else None,
        "emails": emails[:3],
        "phones": phones[:3],
        "companies": companies,
        "education": education,
        "projects": projects,
    }


def _section(text: str, headers: list[str]) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    capture = False
    out: list[str] = []
    stop_headers = {
        "experience", "education", "projects", "skills", "summary",
        "employment", "academics", "certifications",
    }
    for ln in lines:
        low = ln.lower()
        if any(low.startswith(h) for h in headers):
            capture = True
            continue
        if capture:
            if any(low.startswith(h) for h in stop_headers) and not any(
                low.startswith(h) for h in headers
            ):
                break
            out.append(ln)
        if len(out) >= 15:
            break
    return out


class AIHelpers:
    def __init__(self, client: ZohoClient | None = None):
        self._client = client

    async def resume_parse(
        self,
        *,
        resume_base64: str | None = None,
        resume_text: str | None = None,
        use_zoho_parser: bool = False,
    ) -> dict[str, Any]:
        """Parse a resume into structured fields.

        Provide either ``resume_base64`` (a base64-encoded PDF) or raw
        ``resume_text``. With ``use_zoho_parser=True`` and a client configured,
        delegates to Zoho's Resume Parser API instead of the local heuristic.
        """
        if not resume_base64 and not resume_text:
            raise InvalidInputError("Provide resume_base64 or resume_text")

        if use_zoho_parser:
            if not self._client:
                raise NotConfiguredError("Zoho client unavailable for parser.")
            # ENDPOINT (confirm): POST /Candidates/upload (multipart) or the
            # dedicated Resume Parser endpoint for your account/edition.
            raise NotConfiguredError(
                "Zoho Resume Parser endpoint must be configured for your "
                "account before enabling use_zoho_parser=True."
            )

        if resume_text is None and resume_base64 is not None:
            try:
                pdf_bytes = base64.b64decode(resume_base64)
            except Exception as exc:  # noqa: BLE001
                raise InvalidInputError("resume_base64 is not valid base64") from exc
            resume_text = _extract_pdf_text(pdf_bytes)

        fields = _heuristic_fields(resume_text or "")
        return {"parsed": fields, "text_length": len(resume_text or "")}

    @staticmethod
    def candidate_match(
        *, candidate_skills: Any, job_description: str, candidate_summary: str = ""
    ) -> dict[str, Any]:
        """Score a candidate against a job description by keyword overlap."""
        if not job_description:
            raise InvalidInputError("job_description is required")

        if isinstance(candidate_skills, str):
            cand_skills = {
                s.strip().lower() for s in re.split(r"[,;/]", candidate_skills) if s.strip()
            }
        else:
            cand_skills = {str(s).strip().lower() for s in (candidate_skills or [])}

        jd_lower = job_description.lower()
        jd_skills = {s for s in _COMMON_SKILLS if s in jd_lower}
        # Also pull capitalised/である tech tokens the static list misses.
        jd_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9.+#]{2,}", jd_lower))
        required = jd_skills or (jd_tokens & set(_COMMON_SKILLS))

        if not required:
            return {
                "match_percentage": 0.0,
                "strengths": sorted(cand_skills),
                "gaps": [],
                "recommendation": "Insufficient signal in job description to score.",
            }

        matched = sorted(cand_skills & required)
        gaps = sorted(required - cand_skills)
        score = round((len(matched) / len(required)) * 100, 1)

        if score >= 75:
            rec = "Strong match - recommend advancing."
        elif score >= 50:
            rec = "Partial match - consider with screening."
        else:
            rec = "Weak match - likely not a fit."

        return {
            "match_percentage": score,
            "strengths": matched,
            "gaps": gaps,
            "required_skills": sorted(required),
            "recommendation": rec,
        }

    @staticmethod
    def summarize_interview(*, transcript: str) -> dict[str, Any]:
        """Structure an interview transcript into review-ready sections."""
        if not transcript or not transcript.strip():
            raise InvalidInputError("transcript is required")

        sentences = re.split(r"(?<=[.!?])\s+", transcript.strip())
        positives = [
            s for s in sentences
            if re.search(r"\b(strong|good|excellent|impressive|clear|solid|great)\b", s, re.I)
        ]
        concerns = [
            s for s in sentences
            if re.search(r"\b(weak|concern|struggle|unclear|lacking|gap|but|however)\b", s, re.I)
        ]
        questions = [s for s in sentences if s.strip().endswith("?")]

        return {
            "summary": " ".join(sentences[:3]),
            "strengths": positives[:5],
            "concerns": concerns[:5],
            "questions_asked": questions[:5],
            "sentence_count": len(sentences),
            "note": "Heuristic extraction. Use Claude to refine the narrative.",
        }
