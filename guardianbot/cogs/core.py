import os
import sys
import discord
import humanize
from datetime import datetime
from discord.ext import commands
from typing import Optional

from ._base import BaseCog
from .. import utils, types
from ..config import Config


class CoreCog(BaseCog[None]):
    _start_time: Optional[datetime] = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self._start_time = utils.utcnow()

    @commands.command()
    async def info(self, ctx: types.Context) -> None:
        embed = discord.Embed()

        if Config.git_commit:
            embed.add_field(
                name='Commit',
                value=Config.git_commit,
            )
        embed.add_field(
            name='discord.py',
            value=discord.__version__
        )
        embed.add_field(
            name='Python',
            value='.'.join(map(str, sys.version_info[:3])),
        )

        assert self._start_time
        embed.add_field(
            name='Uptime',
            value=humanize.naturaldelta(utils.utcnow() - self._start_time),
            inline=False
        )
        embed.add_field(
            name='Ping',
            value=f'{int(self._bot.latency * 1000)}ms',
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(aliases=(['restart'] if os.path.exists('/.dockerenv') else []))
    @commands.is_owner()
    async def shutdown(self, ctx: types.Context) -> None:
        await self._bot.close()

    @commands.command()
    async def say(self, ctx: types.Context, channel: discord.TextChannel, *, text: str) -> None:
        await channel.send(text)
