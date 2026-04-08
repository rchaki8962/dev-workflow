class DevWorkflowError(Exception):
    """Base exception for dev-workflow."""


class TaskNotFoundError(DevWorkflowError):
    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"Task '{slug}' not found. Run `task list` to see available tasks.")


class PrerequisiteError(DevWorkflowError):
    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"Stage '{stage}' prerequisite not met: {message}")


class PlanParseError(DevWorkflowError):
    def __init__(self, message: str):
        super().__init__(f"Failed to parse plan: {message}")
