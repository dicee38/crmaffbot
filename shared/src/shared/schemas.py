import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from shared.enums import (
    AMOUNT_ACTION_TYPES,
    ActionSource,
    ActionStatus,
    ActionType,
    AuditAction,
    ChangeRequestStatus,
    GoalScope,
    Role,
    UserStatus,
)


class ActionCreate(BaseModel):
    action_type: ActionType
    mop_id: uuid.UUID | None = None
    channel_id: uuid.UUID | None = None
    player_id: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str = "USD"
    lead_count: int = Field(default=1, gt=0)

    @model_validator(mode="after")
    def _amount_required_for_deposits(self) -> "ActionCreate":
        if self.action_type in AMOUNT_ACTION_TYPES and self.amount is None:
            raise ValueError("amount is required for first_deposit/repeat_deposit/withdrawal")
        return self


class ActionUpdate(BaseModel):
    player_id: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    channel_id: uuid.UUID | None = None


class ActionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    action_type: ActionType
    mop_id: uuid.UUID
    channel_id: uuid.UUID | None
    player_id: str | None
    amount: Decimal | None
    currency: str | None
    lead_count: int
    source: ActionSource
    status: ActionStatus
    warnings: list | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangeRequestCreate(BaseModel):
    action: AuditAction  # only "update" or "delete" is valid here
    payload: ActionUpdate | None = None  # required when action == "update"


class ChangeRequestOut(BaseModel):
    id: uuid.UUID
    action_id: uuid.UUID
    requested_by: uuid.UUID
    action: AuditAction
    payload: dict | None
    status: ChangeRequestStatus
    reviewed_by: uuid.UUID | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: uuid.UUID
    action_id: uuid.UUID
    changed_by: uuid.UUID
    action: AuditAction
    diff: dict
    changed_at: datetime

    model_config = {"from_attributes": True}


class TopEntry(BaseModel):
    manager_id: uuid.UUID
    full_name: str
    total_amount: Decimal
    deposit_count: int
    rank: int


class MyStatsOut(BaseModel):
    total_amount: Decimal
    deposit_count: int
    rank: int | None
    team_size: int | None
    previous_period_amount: Decimal
    change_percent: float | None
    fd_amount: Decimal
    rd_amount: Decimal
    withdrawal_amount: Decimal
    cashbox: Decimal  # fd_amount + rd_amount - withdrawal_amount
    fd_commission_rate: Decimal
    rd_commission_rate: Decimal
    salary_amount: Decimal  # fd_amount*fd_rate/100 + rd_amount*rd_rate/100 — withdrawals don't claw back salary


class UserOut(BaseModel):
    id: uuid.UUID
    telegram_id: int
    full_name: str
    role: Role
    team_id: uuid.UUID | None
    status: UserStatus
    fd_commission_rate: Decimal
    rd_commission_rate: Decimal

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    telegram_id: int
    full_name: str
    role: Role
    team_id: uuid.UUID | None = None


class RoleUpdate(BaseModel):
    role: Role


class TeamAssignmentUpdate(BaseModel):
    team_id: uuid.UUID | None = None


class SalaryRatesUpdate(BaseModel):
    fd_commission_rate: Decimal = Field(ge=0, le=100)
    rd_commission_rate: Decimal = Field(ge=0, le=100)


class TeamCreate(BaseModel):
    name: str
    teamlead_id: uuid.UUID | None = None


class TeamUpdate(BaseModel):
    teamlead_id: uuid.UUID | None = None


class TeamOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    teamlead_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class PlatformCreate(BaseModel):
    slug: str
    name: str
    adapter_key: str
    webhook_secret: str


class PlatformUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class PlatformOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    slug: str
    name: str
    adapter_key: str
    is_active: bool

    model_config = {"from_attributes": True}


class ChannelGroupCreate(BaseModel):
    name: str


class ChannelGroupOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class ChannelCreate(BaseModel):
    platform_id: uuid.UUID
    channel_group_id: uuid.UUID | None = None
    name: str
    external_code: str | None = None


class ChannelOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    platform_id: uuid.UUID
    channel_group_id: uuid.UUID | None
    name: str
    external_code: str | None

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    scope: GoalScope
    scope_id: uuid.UUID
    period: date  # any day in the target month — normalized to that month's 1st
    target_amount: Decimal = Field(gt=0)


class GoalOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    scope: GoalScope
    scope_id: uuid.UUID
    period: date
    target_amount: Decimal
    created_by: uuid.UUID

    model_config = {"from_attributes": True}


class GoalProgressOut(BaseModel):
    goal: GoalOut
    current_amount: Decimal
    percent: float
    behind_pace: bool


class ApiKeyCreate(BaseModel):
    name: str
    user_id: uuid.UUID  # which user (and thus role/permissions) this key acts as


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    key: str  # returned once, at creation — never retrievable again
