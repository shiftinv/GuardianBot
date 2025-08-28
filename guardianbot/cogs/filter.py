import asyncio
import io
import json
import logging
from datetime import datetime, timedelta
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    cast,
)

import disnake
from disnake.ext import commands

from .. import checks, error_handler, multicmd, types, utils
from ..config import Config
from ..filter import (
    AllowList,
    AnyMessageList,
    BaseChecker,
    CheckContext,
    DiscordBadDomainsChecker,
    ExternalBaseChecker,
    IPChecker,
    ListChecker,
    ManualBaseChecker,
    RegexChecker,
    SpamChecker,
    SpamCheckerConfig,
)
from ._base import BaseCog, loop_error_handled

logger = logging.getLogger(__name__)

MESSAGE_TYPES = frozenset(
    {
        disnake.MessageType.default,
        disnake.MessageType.reply,
        disnake.MessageType.application_command,
        disnake.MessageType.thread_starter_message,
        disnake.MessageType.context_menu_command,
    }
)


_TChecker = TypeVar("_TChecker", bound=BaseChecker)


def convert_checker(
    type: Type[_TChecker] = BaseChecker,
) -> Callable[[types.AnyContext, str], Coroutine[Any, Any, _TChecker]]:
    async def convert(ctx: types.AnyContext, arg: str) -> _TChecker:
        cog = ctx.application_command.cog if isinstance(ctx, disnake.AppCommandInter) else ctx.cog
        assert isinstance(cog, FilterCog)
        checkers = cog.get_checkers(type)
        if arg not in checkers:
            err = f"Invalid argument. Valid choices: {list(checkers.keys())}"
            await ctx.send(err)
            raise utils.suppress_help(commands.BadArgument(err))
        return checkers[arg]

    return convert


def autocomp_checker(
    type: Type[BaseChecker] = BaseChecker,
) -> Callable[[types.AppCI, str], Coroutine[Any, Any, List[str]]]:
    async def autocomp(ctx: types.AppCI, arg: str) -> List[str]:
        cog = ctx.application_command.cog
        assert isinstance(cog, FilterCog)
        return [n for n in cog.get_checkers(type) if n.startswith(arg)]

    return autocomp


def get_checker_param(type: Type[BaseChecker]) -> Any:
    return commands.Param(autocomp=autocomp_checker(type), converter=convert_checker(type))


class State(utils.StrictModel):
    report_channel: Optional[int] = None
    mute_minutes: int = 10
    unfiltered_roles: Set[int] = set()
    spam_checker_config: SpamCheckerConfig = SpamCheckerConfig()


class FilterCog(
    BaseCog[State],
    slash_command_attrs={"default_member_permissions": disnake.Permissions(manage_messages=True)},
):
    def __init__(self, bot: types.Bot):
        super().__init__(bot)

        self.allowlist = AllowList()
        self.checkers: Dict[str, BaseChecker] = {
            "allowed_hosts": self.allowlist,
            "strings": ListChecker(),
            "regex": RegexChecker(),
            "bad_domains": DiscordBadDomainsChecker(),
            "spam_regex": SpamChecker(self.state.spam_checker_config),
            "ips": IPChecker(),
        }

    def get_checkers(self, type: Type[_TChecker]) -> Dict[str, _TChecker]:
        return {k: c for k, c in self.checkers.items() if isinstance(c, type)}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.debug("starting tasks")
        if not self._update_checkers.is_running():
            self._update_checkers.start()

    def cog_unload(self) -> None:
        logger.debug("stopping tasks")
        self._update_checkers.stop()

    async def cog_any_check(self, ctx: types.AnyContext) -> bool:
        return await checks.manage_messages(ctx)

    @loop_error_handled(hours=2)
    async def _update_checkers(self) -> None:
        results = await asyncio.gather(
            *(c.update(self._session) for c in self.get_checkers(ExternalBaseChecker).values()),
            return_exceptions=True,
        )
        for exc in (e for e in results if isinstance(e, Exception)):
            await error_handler.handle_task_error(self._bot, exc)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message) -> None:
        check, check_reason = await self._should_check(message)
        if not check:
            author = (
                message.interaction_metadata
                and self._bot.get_user(message.interaction_metadata.user.id)
                or message.author
            )
            logger.info(f"ignoring message {message.id} by {author} ({check_reason})")
            return

        blocked = await self.check_message(message, parent=message)

        if not blocked:
            # recurse for message snapshots, which are considered to be basically the same as
            # the current message (in terms of id/author), but with different content/embeds/...
            for snapshot in message.message_snapshots:
                await self.check_message(snapshot, parent=message)

    async def check_message(self, message: types.AnyMessage, *, parent: disnake.Message) -> bool:
        context = CheckContext.from_message(message, parent=parent)
        for checker in self.checkers.values():
            if checker is self.allowlist:
                continue

            if result := await utils.wait_timeout(
                checker.check_match(context), 5, None  # 5 second timeout
            ):
                if result.host and result.host in self.allowlist:
                    logger.info(f"preventing block, host '{result.host}' is allowed explicitly")
                    continue
                await self._handle_blocked(context, result.reason, result.messages or [parent])
                return True
        return False

    async def _should_check(self, message: disnake.Message) -> Tuple[bool, str]:
        if message.type not in MESSAGE_TYPES:
            return False, f"system message type ({message.type!r})"
        if not message.guild:
            return False, "DM"
        if message.guild.id != Config.guild_id:
            return False, f"unknown guild ({message.guild.id})"
        if not message.interaction_metadata and message.webhook_id:
            return False, "webhook"

        author = CheckContext.get_author(message)
        if author.bot:
            return False, "bot"

        ctx: types.Context = await self._bot.get_context(message)
        if ctx.invoked_with:
            return False, "command"

        if any(
            disnake.utils.get(author.roles, id=role_id) for role_id in self.state.unfiltered_roles
        ):
            return False, "user with unfiltered role"

        return True, ""

    async def _handle_blocked(
        self, context: CheckContext, reason: str, to_delete: AnyMessageList
    ) -> None:
        logger.info(
            f"blocking {'forwarded ' if context.is_forwarded else ''}message(s) by "
            f"{str(context.author)}/{context.author.id} ('{context.string}') - {reason}"
        )

        tasks: List[Awaitable[Any]] = []

        # mute user
        tasks.append(
            self._mute_user(
                context.author,
                timedelta(minutes=self.state.mute_minutes) if self.state.mute_minutes else None,
                reason,
            )
        )

        # delete messages
        if context.message.id not in (m.id for m in to_delete):
            to_delete = [*to_delete, context.message]
        logger.info(f"deleting {len(to_delete)} message(s): {[m.id for m in to_delete]}")
        tasks.extend(m.delete() for m in to_delete)

        delete_res = await asyncio.gather(*tasks, return_exceptions=True)
        for exc in (e for e in delete_res if isinstance(e, Exception)):
            # TODO: don't skip exceptions from _mute_user here
            if not isinstance(exc, disnake.errors.NotFound):
                raise exc

        # send notification to channel
        if self.state.report_channel:
            content_fmt = (
                f"{context.author.mention}\n"
                "```\n"
                f"{disnake.utils.escape_markdown(context.string)}\n"
                f"``` ([{context.message.id}]({context.message.jump_url}))"
            )
            embed = disnake.Embed(
                color=0x992E22, description=content_fmt, timestamp=utils.utcnow()
            ).set_author(
                name=f"Muted {str(context.author)} ({context.author.id})",
                icon_url=context.author.display_avatar.url,
            )

            embed.add_field(
                name="Channel",
                value=cast(disnake.TextChannel, context.message.channel).mention,
                inline=False,
            )

            embed.add_field(name="Reason", value=reason)
            if self.state.mute_minutes:
                embed.add_field(name="Duration", value=f"{self.state.mute_minutes}min")

            report_channel = cast(
                disnake.TextChannel, self._bot.get_channel(self.state.report_channel)
            )
            await report_channel.send(embed=embed)

        logger.info(f"successfully blocked message {context.message.id}")

    async def _mute_user(
        self, user: disnake.Member, duration: Optional[timedelta], reason: Optional[str]
    ) -> None:
        if duration is None:
            role = self._get_muted_role()
            assert role, "can't mute permanently without a mute role set"
            await user.add_roles(role, reason=reason)
        else:
            await user.timeout(duration=duration, reason=reason)

    def _get_muted_role(self) -> Optional[disnake.Role]:
        return self._guild.get_role(Config.muted_role_id) if Config.muted_role_id else None

    @multicmd.command(description="Mutes a user")
    async def mute(
        self,
        ctx: types.AnyContext,
        user: disnake.Member,
        duration: Optional[str] = commands.Param(... if Config.muted_role_id is None else None),
    ) -> None:
        duration_td = await utils.convert_timedelta(ctx, duration) if duration else None
        if duration_td and duration_td > timedelta(days=28):
            await ctx.send("Failed to mute user, temporary mute maximum is 28 days")
            return
        await self._mute_user(
            user, duration_td, f"requested by {str(ctx.author)} ({ctx.author.id})"
        )
        await ctx.send(f"Muted {str(user)}/{user.id}")

    @multicmd.command(description="Unmutes a user")
    async def unmute(self, ctx: types.AnyContext, user: disnake.Member) -> None:
        if role := self._get_muted_role():
            await user.remove_roles(role)
        await user.timeout(duration=None)

        await ctx.send(f"Unmuted {str(user)}/{user.id}")

    @multicmd.command(description="Lists all currently muted users")
    async def muted(self, ctx: types.AnyContext) -> None:
        # TODO: this is inefficient in large guilds
        muted: Dict[disnake.Member, Optional[datetime]] = {}
        for m in self._guild.members:
            if disnake.utils.get(m.roles, id=Config.muted_role_id):
                muted[m] = None
            elif m.current_timeout:
                muted[m] = m.current_timeout

        if muted:
            desc = "**name**  -  **expiry**\n"
            desc += "\n".join(
                f'{member.mention}: {disnake.utils.format_dt(expiry) if expiry else "-"}'
                for member, expiry in muted.items()
            )
        else:
            desc = "none"

        embed = disnake.Embed(title="Currently muted users", description=desc)
        await ctx.send(embed=embed)

    # filter list stuff

    @multicmd.group()
    async def filter(self, ctx: types.AnyContext) -> None:
        pass

    @filter.subcommand(name="add", description="Adds an entry to a filter list")
    async def filter_add(
        self,
        ctx: types.AnyContext,
        blocklist: ManualBaseChecker = get_checker_param(ManualBaseChecker),
        input: str = commands.Param(),
    ) -> None:
        logger.info(f"adding {input} to list")
        res = blocklist.entry_add(input)
        if res is True:
            await ctx.send(f"Successfully added `{input}`")
        elif res is False:
            await ctx.send(f"List already contains `{input}`")
        else:
            await ctx.send(f"Unable to add `{input}` to list: `{res}`")

    @filter.subcommand(name="remove", description="Removes an entry from a filter list")
    async def filter_remove(
        self,
        ctx: types.AnyContext,
        blocklist: ManualBaseChecker = get_checker_param(ManualBaseChecker),
        input: str = commands.Param(),
    ) -> None:
        logger.info(f"removing {input} from list")
        if blocklist.entry_remove(input):
            await ctx.send(f"Successfully removed `{input}`")
        else:
            await ctx.send(f"List does not contain `{input}`")

    @filter.subcommand(name="list", description="Shows all entries in a filter list")
    async def filter_list(
        self,
        ctx: types.AnyContext,
        blocklist: BaseChecker = get_checker_param(BaseChecker),
        raw: bool = False,
    ) -> None:
        if len(blocklist) == 0:
            await ctx.send("List contains no elements.")
            return

        items = list(blocklist) if raw else sorted(blocklist)
        s = f"List contains {len(items)} element(s):\n"
        lines = "\n".join(items)

        kwargs: Dict[str, Any] = {}
        if len(lines) > 1900:
            name = next(k for k, v in self.checkers.items() if v is blocklist)
            kwargs["file"] = disnake.File(io.BytesIO(lines.encode()), f"{name}.txt")
        else:
            s += "```\n" + lines + "\n```"

        await ctx.send(s, **kwargs)

    # config stuff

    @filter._command.group(name="config")
    async def filter_config(self, ctx: types.Context) -> None:
        pass

    @filter_config.command(name="report_channel", help="Sets/shows the channel to send reports in")
    async def filter_config_report_channel(
        self, ctx: types.Context, channel: Optional[disnake.TextChannel] = None
    ) -> None:
        if channel is not None:
            self.state.report_channel = channel.id
            self._write_state()
            await ctx.send(f"Set channel to {channel.id}")
        else:
            await ctx.send(f"```\nreport_channel = {self.state.report_channel}\n```")

    @filter_config.command(
        name="mute_minutes",
        help="Sets/shows the number of minutes to mute users sending filtered messages; set to 0 to mute permanently",
    )
    async def filter_config_mute_minutes(
        self, ctx: types.Context, minutes: Optional[int] = None
    ) -> None:
        if minutes is not None:
            self.state.mute_minutes = minutes
            self._write_state()
            await ctx.send(f"Set mute duration to {minutes}min")
        else:
            await ctx.send(f"```\nmute_minutes = {self.state.mute_minutes}\n```")

    @filter_config.command(
        name="unfiltered_roles", help="Adds/removes/shows roles that bypass any filters"
    )
    async def filter_config_unfiltered_roles(
        self, ctx: types.Context, role: Optional[disnake.Role] = None
    ) -> None:
        if role is not None:
            if role.id in self.state.unfiltered_roles:
                self.state.unfiltered_roles.remove(role.id)
                self._write_state()
                await ctx.send(f"Removed {role.id}")
            else:
                self.state.unfiltered_roles.add(role.id)
                self._write_state()
                await ctx.send(f"Added {role.id}")
        else:
            roles = ", ".join(
                f'{role_id} ({self._guild.get_role(role_id) or "<unknown>"})'
                for role_id in self.state.unfiltered_roles
            )
            await ctx.send(f"```\nunfiltered_roles = {{{roles}}}\n```")

    @filter_config.command(
        name="spam_interval_sec", help="Sets/shows the length of the spam interval in seconds"
    )
    async def filter_config_spam_interval_sec(
        self, ctx: types.Context, seconds: Optional[int] = None
    ) -> None:
        if seconds is not None:
            self.state.spam_checker_config.interval_sec = seconds
            self._write_state()
            await ctx.send(f"Set spam interval to {seconds}sec")
        else:
            await ctx.send(
                f"```\nspam_interval_sec = {self.state.spam_checker_config.interval_sec}\n```"
            )

    @filter_config.command(
        name="spam_repeat_count",
        help="Sets/shows the number of required repetitions within the interval for a message to be considered spam",
    )
    async def filter_config_spam_repeat_count(
        self, ctx: types.Context, count: Optional[int] = None
    ) -> None:
        if count is not None:
            self.state.spam_checker_config.repeat_count = count
            self._write_state()
            await ctx.send(f"Set spam repeat count to {count}")
        else:
            await ctx.send(
                f"```\nspam_repeat_count = {self.state.spam_checker_config.repeat_count}\n```"
            )

    def _read_state(self) -> None:
        with self._state_path.open("r") as f:
            data: Dict[str, Any] = json.load(f)

        is_old = False
        if isinstance(r := data.get("unfiltered_roles"), dict) and "$__set" in r:
            # strip '$__set'
            is_old = True
            data["unfiltered_roles"] = data["unfiltered_roles"]["$__set"]

        if "_muted_users" in data:
            # drop unused property
            is_old = True
            data.pop("_muted_users")

        if is_old:
            with self._state_path.open("w") as f:
                json.dump(data, f)
            logger.info("Migrated state to new format")

        return super()._read_state()


def setup(bot: types.Bot) -> None:
    bot.add_cog(FilterCog(bot))
