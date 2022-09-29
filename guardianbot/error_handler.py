import io
import sys
import traceback
import warnings
from typing import Any, Optional

import disnake
from disnake.ext import commands

from . import types, utils

_attr_suppress_help = "_suppress_help"

ignored_exc = (
    commands.errors.UserInputError,
    commands.errors.CommandNotFound,
    commands.errors.CommandOnCooldown,
)
ignored_exc_exact = (commands.errors.CheckFailure, commands.errors.CheckAnyFailure)


async def _handle_error(bot: types.Bot, exc: Optional[Exception]) -> bool:
    try:
        file = None
        if type(exc) in ignored_exc_exact or isinstance(exc, ignored_exc):
            # ignore check/command failures
            return True
        elif exc:
            msg = str(exc).replace("`", "'")
            msg = f"{type(exc).__name__}: `{msg}`\n"
            full = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

            if len(msg) + len(full) < 2000:
                msg += f"```\n{full}\n```"
            else:
                file = disnake.File(io.BytesIO(full.encode()), "traceback.txt")
        else:
            msg = "something is definitely broken"

        user = await bot.fetch_user(await utils.owner_id(bot))
        await user.send(msg, files=[file] if file else [])
    except Exception:
        print("failed sending exception:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    return False


async def handle_task_error(bot: types.Bot, exc: Exception) -> None:
    if not await _handle_error(bot, exc):
        print("Exception in task", file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__)


def init(bot: types.Bot) -> None:
    async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
        exc = sys.exc_info()[1]
        exc = exc if isinstance(exc, Exception) else None
        if not await _handle_error(bot, exc):
            await super(types.Bot, bot).on_error(event, *args, **kwargs)

    async def on_gateway_error(
        event: str, data: Any, shard_id: Optional[int], exc: Exception
    ) -> None:
        if not await _handle_error(bot, exc):
            print(f"error payload: {data!r}")
            await super(types.Bot, bot).on_gateway_error(event, data, shard_id, exc)

    async def on_command_error(ctx: types.Context, exc: commands.errors.CommandError) -> None:
        if not await _handle_error(bot, exc):
            await super(types.Bot, bot).on_command_error(ctx, exc)

        if isinstance(exc, commands.errors.UserInputError) and not getattr(
            exc, _attr_suppress_help, None
        ):
            # send help for specific command if the parameters are incorrect
            assert ctx.command
            await ctx.send_help(ctx.command)
        elif isinstance(exc, commands.errors.CommandOnCooldown):
            await ctx.message.add_reaction("🕒")

    async def on_slash_command_error(inter: types.AppCI, exc: commands.errors.CommandError) -> None:
        if not await _handle_error(bot, exc):
            await super(types.Bot, bot).on_slash_command_error(inter, exc)

    async def on_user_command_error(inter: types.AppCI, exc: commands.errors.CommandError) -> None:
        if not await _handle_error(bot, exc):
            await super(types.Bot, bot).on_user_command_error(inter, exc)

    async def on_message_command_error(
        inter: types.AppCI, exc: commands.errors.CommandError
    ) -> None:
        if not await _handle_error(bot, exc):
            await super(types.Bot, bot).on_message_command_error(inter, exc)

    bot.event(on_error)
    bot.event(on_gateway_error)
    bot.event(on_command_error)
    bot.event(on_slash_command_error)
    bot.event(on_user_command_error)
    bot.event(on_message_command_error)


# oof
def init_warnings_handler(bot: types.Bot) -> None:
    orig_showwarnmsg = warnings._showwarnmsg_impl  # type: ignore

    def new_showwarnmsg(msg: warnings.WarningMessage) -> None:
        bot.loop.create_task(_handle_error(bot, RuntimeError(msg)))
        orig_showwarnmsg(msg)

    warnings._showwarnmsg_impl = new_showwarnmsg  # type: ignore
