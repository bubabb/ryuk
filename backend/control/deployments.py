from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DeploymentState(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    READY = "ready"
    ACTIVE = "active"
    DRAINING = "draining"
    RETIRED = "retired"
    FAILED = "failed"


_TRANSITIONS = {
    DeploymentState.DRAFT: {DeploymentState.VALIDATING},
    DeploymentState.VALIDATING: {DeploymentState.READY, DeploymentState.FAILED},
    DeploymentState.READY: {DeploymentState.ACTIVE, DeploymentState.RETIRED},
    DeploymentState.ACTIVE: {DeploymentState.DRAINING, DeploymentState.FAILED},
    DeploymentState.DRAINING: {DeploymentState.RETIRED, DeploymentState.FAILED},
    DeploymentState.FAILED: {DeploymentState.VALIDATING, DeploymentState.RETIRED},
    DeploymentState.RETIRED: set(),
}


@dataclass(frozen=True, slots=True)
class DeploymentLifecycle:
    deployment_id: str
    tenant_id: str
    state: DeploymentState = DeploymentState.DRAFT

    def transition(self, target: DeploymentState) -> DeploymentLifecycle:
        if target not in _TRANSITIONS[self.state]:
            raise ValueError(f"Invalid deployment transition: {self.state} -> {target}")
        return DeploymentLifecycle(self.deployment_id, self.tenant_id, target)
