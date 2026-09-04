import enum


class Role(str, enum.Enum):
    MANAGER = "manager"
    TEAMLEAD = "teamlead"
    ADMIN = "admin"
    OWNER = "owner"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class DepositSource(str, enum.Enum):
    MANUAL = "manual"
    AFFILIATE_API = "affiliate_api"


class DepositStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    PENDING_REVIEW = "pending_review"


class GoalScope(str, enum.Enum):
    USER = "user"
    TEAM = "team"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
