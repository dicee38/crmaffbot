import enum


class Role(str, enum.Enum):
    MANAGER = "manager"
    TEAMLEAD = "teamlead"
    ADMIN = "admin"
    OWNER = "owner"
    ANALYTIC = "analytic"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class ActionType(str, enum.Enum):
    REGISTRATION = "registration"
    FIRST_DEPOSIT = "first_deposit"
    REPEAT_DEPOSIT = "repeat_deposit"
    LEAD = "lead"


# Deposit-equivalent action types — what v0.1's rating/goals/commission logic counted.
DEPOSIT_ACTION_TYPES = (ActionType.FIRST_DEPOSIT, ActionType.REPEAT_DEPOSIT)


class ActionSource(str, enum.Enum):
    MANUAL = "manual"
    AFFILIATE_API = "affiliate_api"


class ActionStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    PENDING_REVIEW = "pending_review"


class GoalScope(str, enum.Enum):
    USER = "user"
    TEAM = "team"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ChangeRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
