from ._base import ManualBaseChecker, CheckResult


class ListChecker(ManualBaseChecker):
    def __init__(self):
        super().__init__('blocklist.json')

    async def check_match(self, input: str) -> CheckResult:
        if match := next((s for s in self if s in input), None):
            return f'filtered string: `{match}`'
        return None
