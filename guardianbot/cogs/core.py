import humanize
from datetime import datetime
from discord.ext import commands
from typing import Optional

from ._base import BaseCog
from .. import utils


class CoreCog(BaseCog[None]):
    _start_time: Optional[datetime] = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self._start_time = utils.utcnow()

    @commands.command()
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send(f'pong! ({int(self._bot.latency * 1000)}ms)')

    @commands.command()
    async def uptime(self, ctx: commands.Context) -> None:
        assert self._start_time
        diff = utils.utcnow() - self._start_time
        await ctx.send(f'uptime: {humanize.naturaldelta(diff)}')

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx: commands.Context) -> None:
        await self._bot.close()
