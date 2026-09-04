import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

from shared.enums import (
    ActionSource,
    ActionStatus,
    ActionType,
    AuditAction,
    ChangeRequestStatus,
    GoalScope,
    Role,
    UserStatus,
)


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
    # Percent, e.g. 10.00 = 10%. Only meaningful for role = manager; salary for a period is
    # fd_commission_rate% of their FD total + rd_commission_rate% of their RD total.
    fd_commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"))
    rd_commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("7.00"))
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


class Platform(Base):
    """Партнёрская платформа-провайдер (ТЗ §11.4) — по записи на каждую подключённую
    партнёрку (PocketOption, Binolla, ...). adapter_key выбирает реализацию
    AffiliateAdapter из реестра; своего провайдера код адаптеров не знает."""

    __tablename__ = "platforms"
    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_platforms_org_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    slug: Mapped[str]
    name: Mapped[str]
    adapter_key: Mapped[str]
    webhook_secret: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChannelGroup(Base):
    __tablename__ = "channel_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str]


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platforms.id"))
    channel_group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("channel_groups.id"), nullable=True
    )
    name: Mapped[str]
    external_code: Mapped[str | None] = mapped_column(nullable=True)


class MopAction(Base):
    """Заменяет Deposit (v0.1) — обобщённый лог действий воронки (ТЗ §6/§11):
    регистрация / первый депозит / повторный депозит / лид."""

    __tablename__ = "mop_actions"
    __table_args__ = (
        UniqueConstraint("org_id", "external_id", name="uq_mop_actions_org_external_id"),
        Index("ix_mop_actions_org_mop_created", "org_id", "mop_id", "created_at"),
        Index("ix_mop_actions_org_channel_created", "org_id", "channel_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    action_type: Mapped[ActionType] = mapped_column(_pg_enum(ActionType, "action_type"))
    mop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    player_id: Mapped[str | None] = mapped_column(nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(nullable=True)
    lead_count: Mapped[int] = mapped_column(default=1)
    source: Mapped[ActionSource] = mapped_column(_pg_enum(ActionSource, "action_source"))
    external_id: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[ActionStatus] = mapped_column(
        _pg_enum(ActionStatus, "action_status"), default=ActionStatus.CONFIRMED
    )
    warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Soft-delete: keeps the row so action_audit_log's FK to it stays valid after "deletion".
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActionEventRaw(Base):
    """Промежуточная таблица сырых событий партнёрских платформ (ТЗ §4.5, §6).
    Сопоставление с действием происходит асинхронно после приёма."""

    __tablename__ = "action_events_raw"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platforms.id"))
    payload: Mapped[dict] = mapped_column(JSONB)
    matched_action_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mop_actions.id"), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActionAuditLog(Base):
    __tablename__ = "action_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mop_actions.id"))
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(_pg_enum(AuditAction, "audit_action"))
    diff: Mapped[dict] = mapped_column(JSONB)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActionChangeRequest(Base):
    """ТЗ §4.8: правка или удаление ЛЮБОГО действия, включая своё, — только через
    запрос на согласование, применяется после подтверждения тимлидом/админом."""

    __tablename__ = "action_change_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mop_actions.id"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(_pg_enum(AuditAction, "audit_action"))
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ChangeRequestStatus] = mapped_column(
        _pg_enum(ChangeRequestStatus, "change_request_status"), default=ChangeRequestStatus.PENDING
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    scope: Mapped[GoalScope] = mapped_column(_pg_enum(GoalScope, "goal_scope"))
    scope_id: Mapped[uuid.UUID]
    period: Mapped[date] = mapped_column(Date)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class ApiKey(Base):
    """Токен для внешних интеграций (сайт, Chatterfy и т.п.) — запрос с заголовком
    Authorization: Bearer <ключ> аутентифицируется как user_id (сервисная учётная
    запись), без привязки к Telegram. Хранится только хэш ключа."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str]
    key_hash: Mapped[str] = mapped_column(unique=True, index=True)
    key_prefix: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
