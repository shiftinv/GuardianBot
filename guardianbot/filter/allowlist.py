from ._base import ManualBaseChecker


class AllowList(ManualBaseChecker):
    def __init__(self):
        super().__init__("allowlist.json")
