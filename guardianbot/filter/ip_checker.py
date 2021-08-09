from ipaddress import IPv4Network
from typing import Optional, Set, Union

from ._base import BaseChecker
from .. import utils


class IPChecker(BaseChecker):
    def __init__(self):
        self._networks: Set[IPv4Network] = set()

        super().__init__('blocklist_ips.json')

    async def check_match(self, input: str) -> Optional[str]:
        # TODO
        hosts = utils.extract_hosts(input)
        if matched := next((s for s in self if s in input), None):
            return f'filtered IP: `{matched}`'
        return None

    def entry_add(self, input: str) -> Union[bool, str]:
        try:
            # try to parse input as IP/CIDR
            net = IPv4Network(input)
        except ValueError as e:
            return str(e)

        # add to _networks if not already in list
        if (r := super().entry_add(input)) is True:
            self._networks.add(net)
        return r

    def entry_remove(self, input: str) -> bool:
        # remove from _networks if previously in list
        if (r := super().entry_remove(input)) is True:
            self._networks.remove(IPv4Network(input))
        return r

    def _load_list(self) -> None:
        super()._load_list()

        # convert all read strings into network objects
        self._networks.update(map(IPv4Network, self))
