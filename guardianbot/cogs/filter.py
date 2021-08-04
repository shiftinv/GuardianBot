import logging
import discord
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from discord.ext import commands

from ._base import BaseCog
from ..list_checker import ListChecker
from ..config import Config


logger = logging.getLogger(__name__)


@dataclass
class State:
    report_channel: Optional[int] = None
    muted_role: Optional[int] = None
    unfiltered_users: Set[int] = field(default_factory=set)

    muted_users: Dict[int, int] = field(default_factory=dict)


class FilterCog(BaseCog[State]):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

        self.blocklist = ListChecker()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not await self._should_check(message):
            logger.debug(f'not checking message {message.id}')
            return

        if self.blocklist.check_match(message.content):
            await self._handle_blocked(message)

    async def _should_check(self, message: discord.Message) -> bool:
        if not message.guild:
            return False  # don't check DMs
        assert message.guild.id == Config.guild_id
        if message.author.bot:
            return False  # don't check bots

        ctx = await self._bot.get_context(message)  # type: commands.Context
        if ctx.command:
            return False  # don't check commands

        # TODO: filter by role(s) and/or channel
        return True

    async def _handle_blocked(self, message: discord.Message) -> None:
        logger.info(f'blocked message {message.id}')
        # TODO

    @commands.group()
    async def filter(self, ctx: commands.Context) -> None:
        pass

    @filter.command(name='add')
    async def filter_add(self, ctx: commands.Context, input: str) -> None:
        logger.debug(f'adding {input} to list')
        if self.blocklist.entry_add(input):
            await ctx.send(f'Successfully added `{input}`')
        else:
            await ctx.send(f'List already contains `{input}`')

    @filter.command(name='remove')
    async def filter_remove(self, ctx: commands.Context, input: str) -> None:
        logger.debug(f'removing {input} from list')
        if self.blocklist.entry_remove(input):
            await ctx.send(f'Successfully removed `{input}`')
        else:
            await ctx.send(f'List does not contain `{input}`')

    @filter.command(name='list')
    async def filter_list(self, ctx: commands.Context) -> None:
        if len(self.blocklist) == 0:
            await ctx.send('List contains no elements.')
        s = f'List contains {len(self.blocklist)} element(s):\n'
        s += '```\n' + '\n'.join(self.blocklist) + '\n```'
        await ctx.send(s)

    @commands.group()
    async def filterconfig(self, ctx: commands.Context) -> None:
        pass

    @filterconfig.command(name='report_channel')
    async def filterconfig_report_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]) -> None:
        if channel:
            self.state.report_channel = channel.id
            self._write_state()
            await ctx.send(f'Set channel to {channel.id}')
        else:
            await ctx.send(f'```\nreport_channel = {self.state.report_channel}\n```')

    @filterconfig.command(name='muted_role')
    async def filterconfig_muted_role(self, ctx: commands.Context, role: Optional[discord.Role]) -> None:
        if role:
            self.state.muted_role = role.id
            self._write_state()
            await ctx.send(f'Set muted role to {role.id}')
        else:
            await ctx.send(f'```\nmuted_role = {self.state.muted_role}\n```')

    @filterconfig.command(name='unfiltered_users')
    async def filterconfig_unfiltered_users(self, ctx: commands.Context, user: Optional[discord.Member]) -> None:
        if user:
            if user.id in self.state.unfiltered_users:
                self.state.unfiltered_users.remove(user.id)
                self._write_state()
                await ctx.send(f'Removed {user.id}')
            else:
                self.state.unfiltered_users.add(user.id)
                self._write_state()
                await ctx.send(f'Added {user.id}')
        else:
            await ctx.send(f'```\nunfiltered_users = {self.state.unfiltered_users}\n```')
