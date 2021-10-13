import sys
import pprint
import discord
import logging
import humanize
import textwrap
import traceback
from datetime import datetime
from discord.ext import commands
from typing import Any, Dict, Optional

from ._base import BaseCog
from .. import checks, utils, types
from ..config import Config


logger = logging.getLogger(__name__)


class CoreCog(BaseCog[None]):
    _start_time: Optional[datetime] = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self._start_time = utils.utcnow()

    @commands.slash_command(
        description='Shows information about the bot'
    )
    async def info(self, inter: types.AppCI) -> None:
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

        await inter.response.send_message(embed=embed)

    @commands.slash_command(
        name='restart' if utils.is_docker() else 'shutdown',
        description=f'{"Restarts" if utils.is_docker() else "Shuts down"} the bot'
    )
    @commands.is_owner()
    async def shutdown(self, inter: types.AppCI) -> None:
        await self._bot.close()

    @commands.slash_command(
        description='Send a message in another channel using the bot'
    )
    @commands.check(checks.manage_messages)
    async def say(self, inter: types.AppCI, channel: discord.TextChannel, *, text: str) -> None:
        await channel.send(text)
        await inter.response.send_message(
            f'Sent the following message in {channel.mention}:\n'
            f'```\n{discord.utils.escape_mentions(text)}\n```'
        )

    @commands.command(hidden=True, enabled=Config.enable_owner_eval)
    @commands.is_owner()
    async def eval(self, ctx: types.Context, *, code: str) -> None:
        if not await self._bot.is_owner(ctx.author):  # *just to be sure*
            raise RuntimeError

        # require string/codeblock
        code = code.strip()
        if not code.startswith('`'):
            await ctx.send('code must be a \\`string\\` or \\`\\`\\`code block\\`\\`\\`')
            return

        # add `return` to single-line args
        code = code.strip('`').strip()
        if len(code.splitlines()) == 1 and not code.startswith('return '):
            code = f'return {code}'

        # set global context
        eval_globals = {
            'discord': discord,
            'ctx': ctx
        }

        code = f'async def _func():\n{textwrap.indent(code, "    ")}'
        logger.info(f'evaluating:\n{code}')
        try:
            loc: Dict[str, Any] = {}
            exec(code, eval_globals, loc)
            result = await loc['_func']()
            await ctx.send(f'```\n{discord.utils.escape_mentions(pprint.pformat(result, depth=3, sort_dicts=False))}\n```')
        except Exception as e:
            logger.exception('failed evaluating code')

            line = ''
            if e.__traceback__ is not None:
                # find line number in input code
                try:
                    for frame, lineno in traceback.walk_tb(e.__traceback__):
                        if frame.f_code.co_filename == '<string>':
                            line = f' (line {lineno - 1})'  # -1 because of header
                except Exception:
                    pass

            await ctx.send(
                f'Something went wrong{line}:\n'
                f'```\n{type(e).__name__}: {discord.utils.escape_mentions(str(e))}\n```'
            )
