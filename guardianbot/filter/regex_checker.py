import re
from typing import Optional, Union

import disnake

from ._base import CheckResult, ManualBaseChecker

__all__ = ["RegexChecker"]


class RegexChecker(ManualBaseChecker):
    def __init__(self):
        super().__init__("blocklist_regex.json")

    async def check_match(self, msg: disnake.Message) -> Optional[CheckResult]:
        for r in self:
            if match := re.search(r, msg.content, re.MULTILINE):
                return CheckResult(f"filtered string: `{match.group()}` (regex: `{r}`)")
        return None

    def entry_add(self, input: str) -> Union[bool, str]:
        try:
            re.compile(input)
        except re.error as e:
            return str(e)

        return super().entry_add(input)
