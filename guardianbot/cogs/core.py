import logging
import pprint
import sys
import textwrap
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union

import disnake
import humanize
from disnake.ext import commands

from .. import multicmd, types, utils
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
    @commands.has_permissions(manage_messages=True)
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

        # require string/codeblock
        code = code.strip()
        if not code.startswith("`"):
            await ctx.send("code must be a \\`string\\` or \\`\\`\\`code block\\`\\`\\`")
            return

        # add `return` to single-line args
        code = code.strip("`").strip()
        if len(code.splitlines()) == 1 and not code.startswith("return "):
            code = f"return {code}"

        # set global context
        eval_globals = {
            "discord": disnake,
            "disnake": disnake,
            "ctx": ctx,
            "bot": self._bot,
            "Config": Config,
        }

        code = f'async def _func():\n{textwrap.indent(code, "    ")}'
        logger.info(f"evaluating:\n{code}")
        try:
            loc: Dict[str, Any] = {}
            exec(code, eval_globals, loc)
            result = await loc["_func"]()
            await ctx.send(
                f"```\n{disnake.utils.escape_mentions(pprint.pformat(result, depth=3, sort_dicts=False))}\n```"
            )
        except Exception as e:
            logger.exception("failed evaluating code")

            line = ""
            if e.__traceback__ is not None:
                # find line number in input code
                try:
                    for frame, lineno in traceback.walk_tb(e.__traceback__):
                        if frame.f_code.co_filename == "<string>":
                            line = f" (line {lineno - 1})"  # -1 because of header
                except Exception:
                    pass

            await ctx.send(
                f"Something went wrong{line}:\n"
                f"```\n{type(e).__name__}: {disnake.utils.escape_mentions(str(e))}\n```"
            )


def setup(bot: types.Bot) -> None:
    bot.add_cog(CoreCog(bot))
