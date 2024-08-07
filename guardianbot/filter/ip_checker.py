import asyncio
import logging
import socket
from ipaddress import IPv4Address, IPv4Network
from typing import Dict, List, Optional, Set, Union, cast

import aiodns

from .. import utils
from ._base import CheckContext, CheckResult, ManualBaseChecker

__all__ = ["IPChecker"]

logger = logging.getLogger(__name__)


class IPChecker(ManualBaseChecker):
    def __init__(self):
        self._resolver: aiodns.DNSResolver = aiodns.DNSResolver(["1.1.1.1"])

        self._networks: Set[IPv4Network] = set()
        self._cache: Dict[str, List[str]] = {}

        super().__init__("blocklist_ips.json")

    async def resolve(self, host: str) -> List[str]:
        if host in self._cache:
            return self._cache[host]

        addrs: List[str] = []
        try:
            addrs = cast(
                "List[str]", (await self._resolver.gethostbyname(host, socket.AF_INET)).addresses
            )
        except Exception:
            pass

        self._cache[host] = addrs
        return addrs

    # overridden methods

    async def check_match(self, context: CheckContext) -> Optional[CheckResult]:
        hosts = utils.extract_hosts(context.string)
        if not hosts:
            return None
        logger.debug(f"extracted hosts: {hosts}")

        ip_groups: List[List[str]] = await asyncio.gather(*map(self.resolve, hosts))
        logger.debug(f"resolved IPs: {ip_groups}")

        for net in self._networks:
            for host, ips in zip(hosts, ip_groups):
                for ip in ips:
                    if IPv4Address(ip) in net:
                        return CheckResult(f"filtered IP: `{ip}` (matched `{net}`)", host=host)
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
