import re
from typing import Union

from ._base import ManualBaseChecker, CheckResult


class RegexChecker(ManualBaseChecker):
    def __init__(self):
        super().__init__('blocklist_regex.json')

    async def check_match(self, input: str) -> CheckResult:
        for r in self:
            if match := re.search(r, input, re.MULTILINE):
                return f'filtered string: `{match.group()}` (regex: `{r}`)'
        return None

    def entry_add(self, input: str) -> Union[bool, str]:
        try:
            re.compile(input)
        except re.error as e:
            return str(e)

        return super().entry_add(input)
