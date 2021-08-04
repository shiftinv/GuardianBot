import io
import sys
import discord
import traceback
from discord.ext import commands
from typing import Any, Optional


async def handle_error(bot: commands.Bot, exc: Optional[Exception]) -> bool:
    try:
        file = None
        if type(exc) in (commands.errors.CheckFailure, commands.errors.CheckAnyFailure) or isinstance(exc, commands.errors.UserInputError):
            # ignore check failures
            return True
        elif exc:
            msg = f'{type(exc).__name__}: {exc}\n'
            tb = traceback.format_exc()
            if len(msg) + len(tb) < 2000:
                msg += f'```\n{tb}\n```'
            else:
                file = discord.File(io.StringIO(tb), 'traceback.txt')  # type: ignore  # discord.py-stubs isn't updated yet
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


def init(bot: commands.Bot) -> None:
    @bot.event
    async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
        exc = sys.exc_info()[1]
        exc = exc if isinstance(exc, Exception) else None
        if not await handle_error(bot, exc):
            await commands.Bot.on_error(bot, event, *args, **kwargs)

    @bot.event
    async def on_command_error(ctx: commands.Context, exc: commands.errors.CommandError) -> None:
        if not await handle_error(bot, exc):
            await commands.Bot.on_command_error(bot, ctx, exc)
