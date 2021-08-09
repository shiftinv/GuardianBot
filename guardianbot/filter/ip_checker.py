import socket
import aiodns
import asyncio
import logging
from ipaddress import IPv4Address, IPv4Network
from typing import List, Optional, Set, Union

from ._base import BaseChecker
from .. import utils


logger = logging.getLogger(__name__)


class IPChecker(BaseChecker):
    def __init__(self):
        self._networks: Set[IPv4Network] = set()
        self._resolver = aiodns.DNSResolver(['1.1.1.1'])

        super().__init__('blocklist_ips.json')

    async def resolve(self, host: str) -> Optional[List[str]]:
        try:
            res = await self._resolver.gethostbyname(host, socket.AF_INET)
            return res.addresses
        except Exception:
            return None

    # overridden methods

    async def check_match(self, input: str) -> Optional[str]:
        hosts = utils.extract_hosts(input)
        if not hosts:
            return None
        logger.debug(f'extracted hosts: {hosts}')

        ips_opt: List[Optional[List[str]]] = await asyncio.gather(*map(self.resolve, hosts))
        logger.debug(f'resolved IPs: {ips_opt}')
        ips = [IPv4Address(ip) for ip_list in ips_opt for ip in (ip_list or [])]

        for net in self._networks:
            for ip in ips:
                if ip in net:
                    return f'filtered IP: `{ip}` (matched `{net}`)'
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
