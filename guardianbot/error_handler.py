import io
import sys
import discord
import traceback
from discord.ext import commands
from typing import Any, Optional

from . import types


_attr_suppress_help = '_suppress_help'

ignored_exc = (commands.errors.UserInputError, commands.errors.CommandNotFound, commands.errors.CommandOnCooldown)
ignored_exc_exact = (commands.errors.CheckFailure, commands.errors.CheckAnyFailure)


async def _handle_error(bot: types.Bot, exc: Optional[Exception]) -> bool:
    try:
        file = None
        if type(exc) in ignored_exc_exact or isinstance(exc, ignored_exc):
            # ignore check/command failures
            return True
        elif exc:
            msg = f'{type(exc).__name__}: `{exc}`\n'
            full = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))

            if len(msg) + len(full) < 2000:
                msg += f'```\n{full}\n```'
            else:
                file = discord.File(io.StringIO(full), 'traceback.txt')  # type: ignore  # discord.py-stubs isn't updated yet
        else:
            msg = 'something is definitely broken'

        if not bot.owner_id:
            bot.owner_id = (await bot.application_info()).owner.id
        user = await bot.fetch_user(bot.owner_id)
        await user.send(msg, file=file)
    except Exception:
        print('failed sending exception:', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    return False


async def handle_task_error(bot: types.Bot, exc: Exception) -> None:
    if not await _handle_error(bot, exc):
        print('Exception in task', file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__)


def init(bot: types.Bot) -> None:
    @bot.event
    async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
        exc = sys.exc_info()[1]
        exc = exc if isinstance(exc, Exception) else None
        if not await _handle_error(bot, exc):
            await super(types.Bot, bot).on_error(event, *args, **kwargs)

    @bot.event
    async def on_command_error(ctx: types.Context, exc: commands.errors.CommandError) -> None:
        if not await _handle_error(bot, exc):
            await super(types.Bot, bot).on_command_error(ctx, exc)

        if isinstance(exc, commands.errors.CommandNotFound):
            # react to unknown commands
            await ctx.message.add_reaction('❓')
        elif isinstance(exc, commands.errors.UserInputError) and not getattr(exc, _attr_suppress_help, None):
            # send help for specific command if the parameters are incorrect
            assert ctx.command
            await ctx.send_help(ctx.command)
        elif isinstance(exc, commands.errors.CommandOnCooldown):
            await ctx.message.add_reaction('🕒')
