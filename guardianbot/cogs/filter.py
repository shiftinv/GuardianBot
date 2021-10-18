import io
import logging
import discord
from datetime import datetime, timedelta
from typing import Dict, Literal, Optional, Set, Tuple, cast
from dataclasses import dataclass, field
from discord.ext import commands

from ._base import BaseCog, loop_error_handled
from .. import checks, utils, types
from ..filter import BaseChecker, IPChecker, ListChecker, RegexChecker
from ..config import Config


logger = logging.getLogger(__name__)


class FilterChecker(BaseChecker):
    @classmethod
    async def convert(self, ctx: types.Context, arg: str) -> BaseChecker:
        cog = ctx.cog
        assert isinstance(cog, FilterCog)
        if arg not in cog.checkers:
            err = f'Invalid argument. Valid choices: {list(cog.checkers.keys())}'
            await ctx.send(err)
            raise utils.suppress_help(commands.BadArgument(err))
        return cog.checkers[arg]


@dataclass
class State:
    report_channel: Optional[int] = None
    mute_minutes: int = 10
    unfiltered_roles: Set[int] = field(default_factory=set)

    # using str instead of int since json only supports string keys
    _muted_users: Dict[str, datetime] = field(default_factory=dict)


class FilterCog(BaseCog[State]):
    def __init__(self, bot: types.Bot):
        super().__init__(bot)

        self.checkers: Dict[str, BaseChecker] = {
            'strings': ListChecker(),
            'regex': RegexChecker(),
            'ips': IPChecker()
        }

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if Config.muted_role_id and not self._unmute_expired.is_running():
            logger.debug('starting unmute loop')
            self._unmute_expired.start()

    def cog_unload(self) -> None:
        logger.debug('stopping unmute loop')
        self._unmute_expired.stop()

    async def cog_any_check(self, ctx: types.AnyContext) -> bool:
        return await checks.manage_messages(ctx)

    @loop_error_handled(minutes=1)
    async def _unmute_expired(self) -> None:
        role = self._get_muted_role()

        for user_id, expiry in self.state._muted_users.copy().items():
            if expiry < utils.utcnow():
                logger.info(f'unmuting {user_id}')

                member = self._guild.get_member(int(user_id))
                if member:
                    await member.remove_roles(types.to_snowflake(role), reason='mute expired')
                else:
                    logger.info('user left guild')
                self.state._muted_users.pop(user_id)
                self._write_state()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        check, check_reason = await self._should_check(message)
        if not check:
            logger.info(f'ignoring message {message.id} by {message.author} ({check_reason})')
            return

        for checker in self.checkers.values():
            if filter_reason := await utils.wait_timeout(checker.check_match(message.content), 5, None):  # 5 second timeout
                await self._handle_blocked(message, filter_reason)
                break

    async def _should_check(self, message: discord.Message) -> Tuple[bool, str]:
        if not message.guild:
            return False, 'DM'
        assert message.guild.id == Config.guild_id
        if message.author.bot:
            return False, 'bot'
        if message.webhook_id:
            return False, 'webhook'

        ctx: types.Context = await self._bot.get_context(message)
        if ctx.invoked_with:
            return False, 'command'

        if any(
            discord.utils.get(cast(discord.Member, message.author).roles, id=role_id)
            for role_id in self.state.unfiltered_roles
        ):
            return False, 'user with unfiltered role'

        return True, ''

    async def _handle_blocked(self, message: discord.Message, reason: str) -> None:
        author = cast(discord.Member, message.author)
        logger.info(f'blocking message {message.id} by {str(author)}/{author.id} (\'{message.content}\') - {reason}')

        # delete message
        await message.delete()

        # mute user
        mute = Config.muted_role_id is not None
        if mute:
            await self._mute_user(author, timedelta(minutes=self.state.mute_minutes), reason)

        # send notification to channel
        if self.state.report_channel:
            prefix = 'Muted' if mute else 'Blocked message by'
            embed = discord.Embed(
                color=0x992e22,
                description=author.mention,
                timestamp=utils.utcnow()
            ).set_author(
                name=f'{prefix} {str(author)} ({author.id})',
                icon_url=author.display_avatar.url
            )

            embed.add_field(
                name='Text',
                value=f'```\n{message.clean_content}\n``` ({message.id})',
                inline=False
            )
            embed.add_field(
                name='Channel',
                value=cast(discord.TextChannel, message.channel).mention,
                inline=False
            )

            embed.add_field(
                name='Reason',
                value=reason
            )
            if mute:
                embed.add_field(
                    name='Duration',
                    value=f'{self.state.mute_minutes}min'
                )

            report_channel = cast(discord.TextChannel, self._bot.get_channel(self.state.report_channel))
            await report_channel.send(embed=embed)

        logger.info(f'successfully blocked message {message.id}')

    async def _mute_user(self, user: discord.Member, duration: timedelta, reason: Optional[str]) -> None:
        role = self._get_muted_role()

        await user.add_roles(types.to_snowflake(role), reason=reason)
        self.state._muted_users[str(user.id)] = utils.utcnow() + duration
        self._write_state()

        # sanity check to make sure task wasn't stopped for some reason
        assert self._unmute_expired.is_running()

    def _get_muted_role(self) -> discord.Role:
        assert Config.muted_role_id
        role = self._guild.get_role(Config.muted_role_id)
        assert role
        return role

    @commands.command()
    async def mute(self, ctx: types.Context, user: discord.Member, duration: utils.TimedeltaConverter) -> None:
        await self._mute_user(user, duration, f'requested by {str(ctx.author)} ({ctx.author.id})')
        await utils.add_checkmark(ctx.message)

    @commands.command()
    async def unmute(self, ctx: types.Context, user: discord.Member) -> None:
        # remove role from user
        await user.remove_roles(types.to_snowflake(self._get_muted_role()))

        # remove user from muted list
        self.state._muted_users.pop(str(user.id), None)

        await utils.add_checkmark(ctx.message)

    @commands.command()
    async def muted(self, ctx: types.Context) -> None:
        if self.state._muted_users:
            desc = '**name**  -  **expiry**\n'
            desc += '\n'.join(
                f'<@!{id}>: {discord.utils.format_dt(expiry)}'
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

    @commands.group()
    @utils.strict_group
    async def filter(self, ctx: types.Context) -> None:
        pass

    @filter.command(name='add')
    async def filter_add(self, ctx: types.Context, blocklist: FilterChecker, input: str) -> None:
        logger.info(f'adding {input} to list')
        res = blocklist.entry_add(input)
        if res is True:
            await ctx.send(f'Successfully added `{input}`')
        elif res is False:
            await ctx.send(f'List already contains `{input}`')
        else:
            await ctx.send(f'Unable to add `{input}` to list: `{res}`')

    @filter.command(name='remove')
    async def filter_remove(self, ctx: types.Context, blocklist: FilterChecker, input: str) -> None:
        logger.info(f'removing {input} from list')
        if blocklist.entry_remove(input):
            await ctx.send(f'Successfully removed `{input}`')
        else:
            await ctx.send(f'List does not contain `{input}`')

    @filter.command(name='list')
    async def filter_list(self, ctx: types.Context, blocklist: FilterChecker, raw: Optional[Literal['raw']]) -> None:
        if len(blocklist) == 0:
            await ctx.send('List contains no elements.')
            return

        items = list(blocklist) if raw else sorted(blocklist)
        s = f'List contains {len(items)} element(s):\n'

        file: Optional[discord.File]
        if len(items) > 20:  # arbitrary line limit for switching to attachments
            name = next(k for k, v in self.checkers.items() if v is blocklist)
            file = discord.File(io.BytesIO('\n'.join(items).encode()), f'{name}.txt')
        else:
            s += '```\n' + '\n'.join(items) + '\n```'
            file = None

        await ctx.send(s, file=types.unwrap_opt(file))

    # config stuff

    @filter.group(name='config')
    @utils.strict_group
    async def filter_config(self, ctx: types.Context) -> None:
        pass

    @filter_config.command(name='report_channel')
    async def filter_config_report_channel(self, ctx: types.Context, channel: Optional[discord.TextChannel]) -> None:
        if channel:
            self.state.report_channel = channel.id
            self._write_state()
            await ctx.send(f'Set channel to {channel.id}')
        else:
            await ctx.send(f'```\nreport_channel = {self.state.report_channel}\n```')

    @filter_config.command(name='mute_minutes')
    async def filter_config_mute_minutes(self, ctx: types.Context, minutes: Optional[int]) -> None:
        if minutes:
            self.state.mute_minutes = minutes
            self._write_state()
            await ctx.send(f'Set mute duration to {minutes}min')
        else:
            await ctx.send(f'```\nmute_minutes = {self.state.mute_minutes}\n```')

    @filter_config.command(name='unfiltered_roles')
    async def filter_config_unfiltered_roles(self, ctx: types.Context, role: Optional[discord.Role]) -> None:
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


def setup(bot: types.Bot) -> None:
    bot.add_cog(FilterCog(bot))
