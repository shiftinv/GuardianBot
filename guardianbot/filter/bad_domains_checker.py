import hashlib
import aiohttp
import disnake
from typing import List

from ._base import ExternalBaseChecker, CheckResult
from .. import utils


class DiscordBadDomainsChecker(ExternalBaseChecker):
    def __init__(self):
        super().__init__(
            'discord_bad_domains.cache',
            'https://cdn.discordapp.com/bad-domains/hashes.json',
        )

    async def check_match(self, msg: disnake.Message) -> CheckResult:
        hosts = utils.extract_hosts(msg.content)
        for host in hosts:
            h = hashlib.sha256(host.lower().encode()).hexdigest()
            if h in self:
                return f'filtered host: `{host}` (bad-domains hash)', host
        return None

    async def _process_update(self, res: aiohttp.ClientResponse) -> List[str]:
        return [x.lower() for x in await res.json()]
