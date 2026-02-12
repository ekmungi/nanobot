"""Plan tool for structured task decomposition."""

from nanobot.agent.tools.base import Tool


class PlanTool(Tool):
    """Create a step-by-step plan before executing complex tasks."""

    name = "plan"
    description = (
        "Create a step-by-step plan for complex tasks. "
        "Use this when a task requires 3+ steps. "
        "Input: task description and list of steps. "
        "Output: formatted plan for reference."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "What you are trying to accomplish",
            },
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of steps to complete the task",
            },
        },
        "required": ["task", "steps"],
    }

    async def execute(self, **kwargs) -> str:
        task = kwargs.get("task", "")
        steps = kwargs.get("steps", [])

        lines = [f"Plan: {task}", ""]
        for i, step in enumerate(steps, 1):
            lines.append(f"  {i}. {step}")
        lines.append("")
        lines.append("Execute each step in order. Mark steps complete as you go.")
        return "\n".join(lines)
