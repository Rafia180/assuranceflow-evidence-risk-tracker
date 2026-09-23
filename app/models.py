"""Data model for the assurance workflow.

Requirement -> Control -> EvidenceItem / Assessment -> Finding -> RemediationAction
"""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


# ---------- Fixed value lists (enums) ----------
class ControlStatus(str, Enum):
    DRAFT = "Draft"
    ACTIVE = "Active"
    RETIRED = "Retired"


class AssessmentResult(str, Enum):
    EFFECTIVE = "Effective"
    PARTIALLY_EFFECTIVE = "Partially Effective"
    NOT_EFFECTIVE = "Not Effective"
    NOT_TESTED = "Not Tested"


class RiskRating(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class FindingStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    CLOSED = "Closed"
    RISK_ACCEPTED = "Risk Accepted"


class ActionStatus(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    VERIFIED = "Verified"


# ---------- Tables ----------
class Requirement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reference: str = Field(index=True, unique=True)  # e.g. REQ-AC-01
    title: str
    category: str  # e.g. Access Management
    description: str = ""
    owner: str
    review_frequency: str  # e.g. Quarterly

    controls: List["Control"] = Relationship(back_populates="requirement")


class Control(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: int = Field(foreign_key="requirement.id")
    name: str
    description: str = ""
    owner: str
    frequency: str
    status: ControlStatus = ControlStatus.ACTIVE

    requirement: Optional[Requirement] = Relationship(back_populates="controls")
    evidence_items: List["EvidenceItem"] = Relationship(back_populates="control")
    assessments: List["Assessment"] = Relationship(back_populates="control")
    findings: List["Finding"] = Relationship(back_populates="control")


class EvidenceItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    control_id: int = Field(foreign_key="control.id")
    title: str
    evidence_type: str  # e.g. Report, Screenshot, Ticket, Sign-off
    collection_date: date
    review_date: Optional[date] = None  # when the evidence must be refreshed
    owner: str
    reference_link: str  # a text reference only, never a real file

    control: Optional[Control] = Relationship(back_populates="evidence_items")


class Assessment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    control_id: int = Field(foreign_key="control.id")
    assessment_date: date
    result: AssessmentResult
    assessor: str
    notes: str = ""

    control: Optional[Control] = Relationship(back_populates="assessments")


class Finding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    control_id: int = Field(foreign_key="control.id")
    assessment_id: Optional[int] = Field(default=None, foreign_key="assessment.id")
    title: str
    description: str = ""
    risk_rating: RiskRating
    owner: str
    due_date: date
    status: FindingStatus = FindingStatus.OPEN

    control: Optional[Control] = Relationship(back_populates="findings")
    actions: List["RemediationAction"] = Relationship(back_populates="finding")


class RemediationAction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    finding_id: int = Field(foreign_key="finding.id")
    action: str
    owner: str
    target_date: date
    status: ActionStatus = ActionStatus.NOT_STARTED
    verification_notes: str = ""

    finding: Optional[Finding] = Relationship(back_populates="actions")


class AuditLog(SQLModel, table=True):
    """Simple record of who/what changed. Fictional, for learning only."""
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    entity: str
    entity_id: int
    action: str  # create / update
    detail: str = ""
