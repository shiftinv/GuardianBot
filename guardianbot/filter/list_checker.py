from typing import Optional

import disnake

from ._base import CheckResult, ManualBaseChecker


class ListChecker(ManualBaseChecker):
    def __init__(self):
        super().__init__('blocklist.json')

    async def check_match(self, msg: disnake.Message) -> Optional[CheckResult]:
        if match := next((s for s in self if s in msg.content), None):
            return CheckResult(f'filtered string: `{match}`')
        return None
