"""Document understanding via Claude (ARCHITECTURE.md: AI features behind interfaces).

Claude reads PDFs and images natively, so a single structured-output call does
OCR + classification + field extraction in one step. The extractor is sync —
the Celery worker calls it from a thread; tests inject a fake.
"""

import base64
from datetime import date
from typing import Any, Literal, Protocol

import anthropic
import structlog
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = structlog.get_logger("extraction")

# Media types Claude accepts natively. HEIC is uploadable but not extractable yet.
EXTRACTABLE_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}

MAX_FIELDS = 6

SYSTEM_PROMPT = """You are Vaultly's document analyzer. Vaultly is a vault for household \
documents: receipts, warranties, insurance policies, medical bills, IDs and legal papers, \
and home documents. Given one document, classify it and extract its key facts exactly as \
they appear. Use ISO dates (YYYY-MM-DD). If a value is absent or unreadable, leave it null \
rather than guessing. `fields` holds up to six short label/value facts a person would want \
at a glance (e.g. "Order #", "Provider", "Coverage")."""


class ExtractedField(BaseModel):
    label: str = Field(max_length=40)
    value: str = Field(max_length=120)


class DocumentExtraction(BaseModel):
    category: Literal[
        "receipts", "warranties", "insurance", "medical", "ids_legal", "home", "other"
    ]
    title: str = Field(description="Short human title, e.g. 'Samsung WF45 washer receipt'")
    vendor: str | None = Field(default=None, description="Merchant, insurer, provider, issuer")
    document_date: date | None = Field(default=None, description="Date on the document")
    expiry_date: date | None = Field(
        default=None, description="Warranty end, policy renewal, ID expiry, or payment due date"
    )
    amount: float | None = Field(default=None, description="Primary monetary amount")
    currency: str | None = Field(default=None, description="ISO currency code, e.g. USD")
    fields: list[ExtractedField] = Field(default_factory=list, max_length=MAX_FIELDS)


class Extractor(Protocol):
    def extract(
        self, file_bytes: bytes, content_type: str, file_name: str
    ) -> DocumentExtraction: ...


class ClaudeExtractor:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.extraction_model

    def extract(self, file_bytes: bytes, content_type: str, file_name: str) -> DocumentExtraction:
        data = base64.standard_b64encode(file_bytes).decode()
        media_block: Any
        if content_type == "application/pdf":
            media_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": data},
            }
        else:
            media_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": content_type, "data": data},
            }

        response = self._client.messages.parse(
            model=self._model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        media_block,
                        {"type": "text", "text": f"Analyze this document (file: {file_name})."},
                    ],
                }
            ],
            output_format=DocumentExtraction,
        )
        result = response.parsed_output
        if result is None:
            raise RuntimeError("Extraction returned no parseable output")
        logger.info("document_extracted", category=result.category, model=self._model)
        return result


def extraction_enabled() -> bool:
    return bool(get_settings().anthropic_api_key)


def get_extractor() -> Extractor:
    return ClaudeExtractor()
