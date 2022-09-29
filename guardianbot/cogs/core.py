import ast
import inspect
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, List, Optional, Union

import disnake
import humanize
from disnake.ext import commands

from .. import checks, multicmd, types, utils
from ..config import Config
from ._base import BaseCog

logger = logging.getLogger(__name__)


class CoreCog(BaseCog[None]):
    _start_time: Optional[datetime] = None

    async def cog_load(self) -> None:
        self._start_time = utils.utcnow()

    @multicmd.command(description="Shows information about the bot")
    async def info(self, ctx: types.AnyContext) -> None:
        embed = disnake.Embed()

        if Config.git_commit:
            embed.add_field(
                name="Commit",
                value=Config.git_commit,
            )
        embed.add_field(name="disnake", value=disnake.__version__)
        embed.add_field(
            name="Python",
            value=".".join(map(str, sys.version_info[:3])),
        )

        assert self._start_time
        embed.add_field(
            name="Uptime",
            value=humanize.naturaldelta(utils.utcnow() - self._start_time),
            inline=False,
        )
        embed.add_field(name="Ping", value=f"{int(self._bot.latency * 1000)}ms", inline=False)

        await ctx.send(embed=embed)

    @commands.command(
        name="restart" if utils.is_docker() else "shutdown",
        description=f'{"Restarts" if utils.is_docker() else "Shuts down"} the bot',
        hidden=True,
    )
    @commands.is_owner()
    async def shutdown(self, ctx: types.AnyContext) -> None:
        await self._bot.close()

    @multicmd.command(
        description="Sends a message in another channel using the bot",
        slash_kwargs={"default_member_permissions": disnake.Permissions(manage_messages=True)},
    )
    @commands.check(checks.manage_messages)
    async def say(
        self,
        ctx: types.AnyContext,
        channel: Union[disnake.TextChannel, disnake.VoiceChannel],
        *,
        text: str,
    ) -> None:
        await channel.send(text)

        await ctx.send(
            f"Sent the following message in {channel.mention}:\n```\n{disnake.utils.escape_mentions(text)}\n```",
            allowed_mentions=disnake.AllowedMentions.all().merge(
                disnake.AllowedMentions(everyone=False)
            ),
        )

    @commands.command(hidden=True)
    @commands.is_owner()
    async def botinvite(self, ctx: types.Context, *scopes: str) -> None:
        if not scopes:
            scopes = ("bot", "applications.commands")
        link = disnake.utils.oauth_url(
            self._bot.user.id,
            permissions=disnake.Permissions(
                add_reactions=True,
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                manage_roles=True,
                moderate_members=True,
            ),
            scopes=scopes,
        )
        await ctx.send(link)

    @multicmd.command()
    async def snowflaketime(self, ctx: types.AnyContext, snowflake: str) -> None:
        time = disnake.utils.snowflake_time(int(snowflake))
        await ctx.send(str(time))

    @commands.command(hidden=True, enabled=Config.enable_owner_eval)
    @commands.is_owner()
    async def eval(self, ctx: types.Context, *, code: str) -> None:
        if not await self._bot.is_owner(ctx.author):  # *just to be sure*
            raise RuntimeError

        output: List[str] = []

        def _print(*s: Any):
            output.append(" ".join(map(str, s)))

        # require string/codeblock
        code = code.strip(" `").removeprefix("python\n").removeprefix("py\n")

        logger.info(f"evaluating:\n{code}")
        try:
            compiled = compile(code, "<eval>", "exec", ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            result = eval(
                compiled,
                {"ctx": ctx, "bot": ctx.bot, "disnake": disnake, "print": _print, "Config": Config},
            )
            if inspect.isawaitable(result):
                await result

            if output:
                x = "\n".join(output)
                await ctx.send(f"```\n{x}\n```")
        except Exception as e:
            logger.exception("failed evaluating code")

            line = ""
            if e.__traceback__ is not None:
                # find line number in input code
                try:
                    for frame, lineno in traceback.walk_tb(e.__traceback__):
                        if frame.f_code.co_filename == "<eval>":
                            line = f" (line {lineno})"
                except Exception:
                    pass

            await ctx.send(
                f"Something went wrong{line}:\n"
                f"```\n{type(e).__name__}: {disnake.utils.escape_mentions(str(e))}\n```"
            )


def setup(bot: types.Bot) -> None:
    bot.add_cog(CoreCog(bot))
