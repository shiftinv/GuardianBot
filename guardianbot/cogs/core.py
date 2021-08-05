import humanize
from datetime import datetime
from discord.ext import commands
from typing import Optional

from ._base import BaseCog


class CoreCog(BaseCog[None]):
    _start_time: Optional[datetime] = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self._start_time = datetime.utcnow()

    @commands.command()
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send(f'pong! ({int(self._bot.latency * 1000)}ms)')

    @commands.command()
    async def uptime(self, ctx: commands.Context) -> None:
        assert self._start_time
        diff = datetime.utcnow() - self._start_time
        await ctx.send(f'uptime: {humanize.naturaldelta(diff)}')

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx: commands.Context) -> None:
        await self._bot.close()
