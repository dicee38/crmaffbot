from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class AffiliateEvent:
    external_id: str
    sub_id: str
    client_ref: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    raw: dict[str, Any]


class AffiliateAdapter(ABC):
    """Единый интерфейс адаптера партнёрки (ТЗ §4.5) — провайдер ещё не выбран, см. §9."""

    provider_name: str

    @abstractmethod
    def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool: ...

    @abstractmethod
    def parse_event(self, payload: dict[str, Any]) -> AffiliateEvent: ...

    @abstractmethod
    async def fetch_stats(self, since: datetime) -> list[AffiliateEvent]: ...
