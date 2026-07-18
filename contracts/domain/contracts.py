
"""
Domain classes for contract repository
These classes define the data structures independent of Django models
"""
from dataclasses import dataclass, asdict, field
from typing import List, Optional
from enum import Enum

class ContractStatus(Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE" 
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"

@dataclass
class ListParams:
    """Parameters for contract listing"""
    q: str = ""
    status: Optional[List[str]] = None
    contract_type: Optional[List[str]] = None
    owner: Optional[List[str]] = None
    counterparty: Optional[List[str]] = None
    risk_level: Optional[List[str]] = None
    approval_state: Optional[List[str]] = None
    sort: str = "updated_desc"
    page: int = 1
    page_size: int = 25
    # Backs the Repository saved-view rail's "30d attention" view — active
    # contracts whose end_date falls within the next N days. Separate from
    # `status` since it's a date-window filter, not a status filter, and the
    # UI never needs to combine it with an explicit status choice.
    expiring_within_days: Optional[int] = None

    def __post_init__(self):
        if self.status is None:
            self.status = []
        if self.contract_type is None:
            self.contract_type = []
        if self.owner is None:
            self.owner = []
        if self.counterparty is None:
            self.counterparty = []
        if self.risk_level is None:
            self.risk_level = []
        if self.approval_state is None:
            self.approval_state = []

@dataclass
class ContractData:
    """Contract data transfer object"""
    id: str
    title: str
    status: str
    status_display: str = ""
    counterparty: str = ""
    value: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    owner: str = ""
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    content: str = ""

    # WorkQueue-aligned fields (Repository consolidation) — reuse the same
    # StageDots/AssigneeChip/ActivityLine visual contract as the Dashboard
    # queue, computed server-side so the JS-rendered table never invents its
    # own status colors, stage ordering, or activity phrasing.
    status_badge_tone: str = ""
    stage_badge_tone: str = ""
    stage_steps: list = field(default_factory=list)
    assignee_name: Optional[str] = None
    assignee_initial: Optional[str] = None
    latest_activity_text: Optional[str] = None
    latest_activity_time: Optional[str] = None
    latest_activity_initial: Optional[str] = None
    value_display: str = ""
    end_date_display: Optional[str] = None
    due_overdue: bool = False
    contract_type_display: str = ""
    stage_display: str = ""

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class CareCaseData(ContractData):
    """Backward-compatible care case DTO used by legacy API views."""
    preferred_provider: str = ""

@dataclass
class ListResult:
    """Result of contract listing operation"""
    contracts: List[ContractData]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'contracts': [c.to_dict() for c in self.contracts],
            'total_count': self.total_count,
            'page': self.page,
            'page_size': self.page_size,
            'total_pages': self.total_pages
        }
