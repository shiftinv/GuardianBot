import io
import sys
import discord
import traceback
from discord.ext import commands
from typing import Any, Optional


async def _handle_error(bot: commands.Bot, exc: Optional[Exception]) -> bool:
    try:
        file = None
        if type(exc) in (commands.errors.CheckFailure, commands.errors.CheckAnyFailure) or isinstance(exc, commands.errors.UserInputError):
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


async def handle_task_error(bot: commands.Bot, exc: Exception) -> None:
    if not await _handle_error(bot, exc):
        print('Exception in task', file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__)


def init(bot: commands.Bot) -> None:
    @bot.event
    async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
        exc = sys.exc_info()[1]
        exc = exc if isinstance(exc, Exception) else None
        if not await _handle_error(bot, exc):
            await type(bot).on_error(bot, event, *args, **kwargs)

    @bot.event
    async def on_command_error(ctx: commands.Context, exc: commands.errors.CommandError) -> None:
        if not await _handle_error(bot, exc):
            await type(bot).on_command_error(bot, ctx, exc)
