"""Exception hierarchy for dev-workflow.

All user-facing errors inherit from DevWorkflowError.
CLI catches DevWorkflowError -> stderr + exit 1.
Unexpected exceptions -> stderr + exit 2.
"""


class DevWorkflowError(Exception):
    """Base exception. Carries a human-readable message."""


class TaskNotFoundError(DevWorkflowError):
    """Raised when a task slug doesn't exist in the active space."""


class SpaceNotFoundError(DevWorkflowError):
    """Raised when a space name doesn't exist."""


class SpaceNotEmptyError(DevWorkflowError):
    """Raised when trying to remove a space that still has tasks."""


class PayloadError(DevWorkflowError):
    """Raised when a checkpoint payload fails validation."""


class SlugCollisionError(DevWorkflowError):
    """Raised when slug generation exhausts collision attempts."""


class StoreError(DevWorkflowError):
    """Raised when a SQLite operation fails unexpectedly."""
