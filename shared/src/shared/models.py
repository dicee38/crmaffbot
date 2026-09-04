import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

from shared.enums import AuditAction, DepositSource, DepositStatus, GoalScope, Role, UserStatus


class Base(DeclarativeBase):
    pass


def _pg_enum(enum_cls: type, name: str) -> Enum:
    # str-Enum members default to sending .name ("ADMIN") instead of .value ("admin");
    # values_callable makes the DB enum values match shared.enums's lowercase values.
    return Enum(enum_cls, name=name, values_callable=lambda obj: [e.value for e in obj])


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str]
    role: Mapped[Role] = mapped_column(_pg_enum(Role, "role"))
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        _pg_enum(UserStatus, "user_status"), default=UserStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str]
    # use_alter breaks the users<->teams FK cycle at table-creation time.
    teamlead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", use_alter=True, name="fk_teams_teamlead_id"), nullable=True
    )


class Deposit(Base):
    __tablename__ = "deposits"
    __table_args__ = (
        UniqueConstraint("org_id", "external_id", name="uq_deposits_org_external_id"),
        Index("ix_deposits_org_manager_created", "org_id", "manager_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    manager_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    client_ref: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(default="USD")
    source: Mapped[DepositSource] = mapped_column(_pg_enum(DepositSource, "deposit_source"))
    external_id: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[DepositStatus] = mapped_column(
        _pg_enum(DepositStatus, "deposit_status"), default=DepositStatus.CONFIRMED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Soft-delete: keeps the row so deposit_audit_log's FK to it stays valid after "deletion".
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DepositEventRaw(Base):
    """Промежуточная таблица сырых событий партнёрки (спека §4.5, §6). Сопоставление с депозитом происходит асинхронно после приёма."""

    __tablename__ = "deposit_events_raw"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    provider: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSONB)
    matched_deposit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deposits.id"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DepositAuditLog(Base):
    __tablename__ = "deposit_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deposit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deposits.id"))
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(_pg_enum(AuditAction, "audit_action"))
    diff: Mapped[dict] = mapped_column(JSONB)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    scope: Mapped[GoalScope] = mapped_column(_pg_enum(GoalScope, "goal_scope"))
    scope_id: Mapped[uuid.UUID]
    period: Mapped[date] = mapped_column(Date)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
