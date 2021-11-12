import hashlib
import aiohttp
from typing import List, Optional

from ._base import ExternalBaseChecker
from .. import utils


class DiscordBadDomainsChecker(ExternalBaseChecker):
    def __init__(self):
        super().__init__(
            'discord_bad_domains.cache',
            'https://cdn.discordapp.com/bad-domains/hashes.json',
        )

    async def check_match(self, input: str) -> Optional[str]:
        hosts = utils.extract_hosts(input)
        for host in hosts:
            h = hashlib.sha256(host.lower().encode()).hexdigest()
            if h in self:
                return f'filtered host: `{host}` (bad-domains hash)'
        return None

    async def _process_update(self, res: aiohttp.ClientResponse) -> List[str]:
        return [x.lower() for x in await res.json()]
