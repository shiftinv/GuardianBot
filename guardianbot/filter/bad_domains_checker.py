import hashlib
from typing import List, Optional

import aiohttp
import disnake

from .. import utils
from ._base import CheckResult, ExternalBaseChecker


class DiscordBadDomainsChecker(ExternalBaseChecker):
    def __init__(self):
        super().__init__(
            'discord_bad_domains.cache',
            'https://cdn.discordapp.com/bad-domains/hashes.json',
        )

    async def check_match(self, msg: disnake.Message) -> Optional[CheckResult]:
        hosts = utils.extract_hosts(msg.content)
        for host in hosts:
            h = hashlib.sha256(host.lower().encode()).hexdigest()
            if h in self:
                return CheckResult(f'filtered host: `{host}` (bad-domains hash)', host=host)
        return None

    async def _process_update(self, res: aiohttp.ClientResponse) -> List[str]:
        return [x.lower() for x in await res.json()]
