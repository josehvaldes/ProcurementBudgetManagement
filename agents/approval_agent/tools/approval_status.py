

from typing import Optional

from pydantic import BaseModel


class ApprovalStatus:
    AUTO_APPROVED = "Auto-Approved"
    MANUAL_APPROVAL_REQUIRED = "Manual Approval Required"
    REJECTED = "Rejected"
    AI_WARNING = "AI Warning"
    AI_ALERT = "AI Alert"
    AI_PASSED = "AI Passed"


class ApprovalDecision (BaseModel):
    status: str
    reason: Optional[str] = None
    suggested_approver: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "suggested_approver": self.suggested_approver
        }