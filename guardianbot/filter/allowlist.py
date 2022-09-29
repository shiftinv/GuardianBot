from ._base import ManualBaseChecker

__all__ = ["AllowList"]


class AllowList(ManualBaseChecker):
    def __init__(self):
        super().__init__("allowlist.json")
