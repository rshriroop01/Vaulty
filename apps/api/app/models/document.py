import enum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DocumentCategory(enum.StrEnum):
    """The six vault categories from the approved dashboard (1a), plus other."""

    receipts = "receipts"
    warranties = "warranties"
    insurance = "insurance"
    medical = "medical"
    ids_legal = "ids_legal"
    home = "home"
    other = "other"


class DocumentStatus(enum.StrEnum):
    pending_upload = "pending_upload"  # presigned URL issued, object not confirmed
    uploaded = "uploaded"
    # M3 pipeline states (screen 2b queue): queued → processing → extracted | failed
    queued = "queued"
    processing = "processing"
    extracted = "extracted"
    failed = "failed"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vault_id: Mapped[UUID] = mapped_column(ForeignKey("vaults.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    file_name: Mapped[str] = mapped_column(String(300))
    file_key: Mapped[str] = mapped_column(String(500), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    category: Mapped[DocumentCategory] = mapped_column(
        Enum(DocumentCategory, name="document_category", native_enum=False, length=20),
        default=DocumentCategory.other,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False, length=20),
        default=DocumentStatus.pending_upload,
    )
