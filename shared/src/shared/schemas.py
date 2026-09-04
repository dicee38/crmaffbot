import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from shared.enums import (
    AuditAction,
    ChangeRequestStatus,
    DepositSource,
    DepositStatus,
    GoalScope,
    Role,
    UserStatus,
)


class DepositCreate(BaseModel):
    client_ref: str
    amount: Decimal = Field(gt=0)
    currency: str = "USD"
    manager_id: uuid.UUID | None = None


class DepositUpdate(BaseModel):
    client_ref: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None


class DepositOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    manager_id: uuid.UUID
    client_ref: str
    amount: Decimal
    currency: str
    source: DepositSource
    status: DepositStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangeRequestCreate(BaseModel):
    action: AuditAction  # only "update" or "delete" is valid here
    payload: DepositUpdate | None = None  # required when action == "update"


class ChangeRequestOut(BaseModel):
    id: uuid.UUID
    deposit_id: uuid.UUID
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
    deposit_id: uuid.UUID
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


class UserOut(BaseModel):
    id: uuid.UUID
    telegram_id: int
    full_name: str
    role: Role
    team_id: uuid.UUID | None
    status: UserStatus

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    telegram_id: int
    full_name: str
    role: Role
    team_id: uuid.UUID | None = None


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
