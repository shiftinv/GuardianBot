from typing import Optional

from ._base import CheckContext, CheckResult, ManualBaseChecker

__all__ = ["ListChecker"]


class ListChecker(ManualBaseChecker):
    def __init__(self):
        super().__init__("blocklist.json")

    async def check_match(self, context: CheckContext) -> Optional[CheckResult]:
        if match := next((s for s in self if s in context.string), None):
            return CheckResult(f"filtered string: `{match}`")
        return None
