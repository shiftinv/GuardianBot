import logging
import discord
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Tuple, cast
from dataclasses import dataclass, field
from discord.ext import commands, tasks

from ._base import BaseCog, loop_error_handled
from .. import error_handler, utils
from ..list_checker import ListChecker
from ..config import Config


logger = logging.getLogger(__name__)


@dataclass
class State:
    report_channel: Optional[int] = None
    muted_role: Optional[int] = None
    mute_minutes: int = 10
    unfiltered_roles: Set[int] = field(default_factory=set)

    # using str instead of int since json only supports string keys
    _muted_users: Dict[str, datetime] = field(default_factory=dict)


class FilterCog(BaseCog[State]):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

        self.blocklist = ListChecker()

        self._unmute_expired.start()

    def cog_unload(self) -> None:
        self._unmute_expired.stop()

    @loop_error_handled(minutes=1)
    async def _unmute_expired(self) -> None:
        if not self._guild:  # task may run before socket is initialized
            return
        if not self.state.muted_role:
            return

        logger.debug('checking expired mutes')
        role = self._guild.get_role(self.state.muted_role)
        assert role

        for user_id, expiry in self.state._muted_users.copy().items():
            if expiry < utils.utcnow():
                logger.info(f'unmuting {user_id}')

                member = self._guild.get_member(int(user_id))
                if member:
                    await member.remove_roles(role, reason='mute expired')
                else:
                    logger.info('user left guild')
                self.state._muted_users.pop(user_id)
                self._write_state()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        check, reason = await self._should_check(message)
        if not check:
            logger.info(f'ignoring message {message.id} by {message.author}, {reason}')
            return

        if self.blocklist.check_match(message.content):
            await self._handle_blocked(message)

    async def _should_check(self, message: discord.Message) -> Tuple[bool, str]:
        if not message.guild:
            return False, 'not checking DMs'
        assert message.guild.id == Config.guild_id
        if message.author.bot:
            return False, 'not checking bots'

        ctx = await self._bot.get_context(message)  # type: commands.Context
        if ctx.command:
            return False, 'not checking commands'

        if any(
            discord.utils.get(cast(discord.Member, message.author).roles, id=role_id)
            for role_id in self.state.unfiltered_roles
        ):
            return False, 'not checking user with unfiltered role'

        return True, ''

    async def _handle_blocked(self, message: discord.Message) -> None:
        logger.info(f'blocking message {message.id} (\'{message.content}\')')

        # delete message
        await message.delete()

        # mute user
        author = cast(discord.Member, message.author)
        mute = self.state.muted_role is not None
        if mute:
            assert self.state.muted_role  # satisfy the linter
            role = cast(discord.Guild, message.guild).get_role(self.state.muted_role)
            assert role
            await author.add_roles(role, reason='blocked word/phrase')
            self.state._muted_users[str(author.id)] = utils.utcnow() + timedelta(minutes=self.state.mute_minutes)
            self._write_state()

        # send notification to channel
        if self.state.report_channel:
            prefix = 'Muted' if mute else 'Blocked message by'
            embed = discord.Embed(
                color=0x992e22,
                description=f'**{prefix} {author.mention}**'
            ).set_author(
                name=f'{prefix} {str(author)} ({author.id})',
                icon_url=author.avatar.url  # type: ignore  # discord.py-stubs is not updated for 2.0 yet
            )

            if mute:
                embed.add_field(name='Duration', value=f'{self.state.mute_minutes}m')

            embed.add_field(
                name='Text',
                value=f'```\n{message.clean_content}\n```',
                inline=False
            )
            embed.add_field(
                name='Channel',
                value=cast(discord.TextChannel, message.channel).mention,
                inline=False
            )

            await self._bot.get_channel(self.state.report_channel).send(embed=embed)

        logger.info(f'successfully blocked message {message.id}')

    @commands.group()
    async def filter(self, ctx: commands.Context) -> None:
        pass

    @filter.command(name='muted')
    async def filter_muted(self, ctx: commands.Context) -> None:
        if self.state._muted_users:
            desc = '`[name]: [expiry]`\n'
            desc += '\n'.join(
                f'<@!{id}>: {discord.utils.format_dt(expiry)}'  # type: ignore  # discord.py-stubs isn't updated yet
                for id, expiry in self.state._muted_users.items()
            )
        else:
            desc = 'none'

        embed = discord.Embed(
            title='Currently muted users',
            description=desc
        )
        await ctx.send(embed=embed)

    # filter list stuff

    @filter.command(name='add')
    async def filter_add(self, ctx: commands.Context, input: str) -> None:
        logger.info(f'adding {input} to list')
        if self.blocklist.entry_add(input):
            await ctx.send(f'Successfully added `{input}`')
        else:
            await ctx.send(f'List already contains `{input}`')

    @filter.command(name='remove')
    async def filter_remove(self, ctx: commands.Context, input: str) -> None:
        logger.info(f'removing {input} from list')
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

    # config stuff

    @filter.group(name='config')
    async def filter_config(self, ctx: commands.Context) -> None:
        pass

    @filter_config.command(name='report_channel')
    async def filter_config_report_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]) -> None:
        if channel:
            self.state.report_channel = channel.id
            self._write_state()
            await ctx.send(f'Set channel to {channel.id}')
        else:
            await ctx.send(f'```\nreport_channel = {self.state.report_channel}\n```')

    @filter_config.command(name='muted_role')
    async def filter_config_muted_role(self, ctx: commands.Context, role: Optional[discord.Role]) -> None:
        if role:
            self.state.muted_role = role.id
            self._write_state()
            await ctx.send(f'Set muted role to {role.id}')
        else:
            await ctx.send(f'```\nmuted_role = {self.state.muted_role}\n```')

    @filter_config.command(name='mute_minutes')
    async def filter_config_mute_minutes(self, ctx: commands.Context, minutes: Optional[int]) -> None:
        if minutes:
            self.state.mute_minutes = minutes
            self._write_state()
            await ctx.send(f'Set mute duration to {minutes}m')
        else:
            await ctx.send(f'```\nmute_minutes = {self.state.mute_minutes}\n```')

    @filter_config.command(name='unfiltered_roles')
    async def filter_config_unfiltered_roles(self, ctx: commands.Context, role: Optional[discord.Role]) -> None:
        if role:
            if role.id in self.state.unfiltered_roles:
                self.state.unfiltered_roles.remove(role.id)
                self._write_state()
                await ctx.send(f'Removed {role.id}')
            else:
                self.state.unfiltered_roles.add(role.id)
                self._write_state()
                await ctx.send(f'Added {role.id}')
        else:
            roles = ', '.join(
                f'{role_id} ({self._guild.get_role(role_id) or "<unknown>"})'
                for role_id in self.state.unfiltered_roles
            )
            await ctx.send(f'```\nunfiltered_roles = {{{roles}}}\n```')
