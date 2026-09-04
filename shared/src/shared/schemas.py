import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from shared.enums import DepositSource, DepositStatus, Role, UserStatus


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


class TeamOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    teamlead_id: uuid.UUID | None

    model_config = {"from_attributes": True}
