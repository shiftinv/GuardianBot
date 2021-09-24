import re
from typing import Optional

from ._base import BaseChecker


class RegexChecker(BaseChecker):
    def __init__(self):
        super().__init__('blocklist_regex.json')

    async def check_match(self, input: str) -> Optional[str]:
        for r in self:
            if match := re.search(r, input, re.MULTILINE):
                return f'filtered string: `{match.group()}` (regex: `{r}`)'
        return None
