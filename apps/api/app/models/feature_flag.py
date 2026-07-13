from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FeatureFlag(Base, TimestampMixin):
    """DB-backed feature flags — every new feature ships behind one (PRD engineering principle)."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str] = mapped_column(String(500), default="")
