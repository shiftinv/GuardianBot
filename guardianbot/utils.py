import os
import re
import asyncio
import discord
import functools
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Coroutine, List, TypeVar, Union

from . import types


_T = TypeVar('_T')
_U = TypeVar('_U')


def utcnow() -> datetime:
    # note: this uses `timezone.utc` instead of just calling `datetime.utcnow()`,
    #       as utcnow doesn't set tzinfo
    return datetime.now(timezone.utc)


async def wait_timeout(aw: Awaitable[_T], timeout: float, fallback: _U) -> Union[_T, _U]:
    try:
        return await asyncio.wait_for(aw, timeout)
    except asyncio.TimeoutError:
        return fallback


def extract_hosts(input: str) -> List[str]:
    return re.findall(r'https?://([^/?#<>\s]+)', input)


async def add_checkmark(message: discord.Message) -> None:
    await message.add_reaction('✅')


class TimedeltaConverter(timedelta):
    _re = re.compile(''.join(
        fr'(?:(?P<{unit}>\d+){unit[0]})?'
        for unit in ['weeks', 'days', 'hours', 'minutes', 'seconds']
    ), re.I)

    @classmethod
    async def convert(cls, ctx: types.Context, arg: str) -> timedelta:
        if arg.isdigit():
            return timedelta(minutes=int(arg))

        if not (match := cls._re.fullmatch(arg)):
            err = 'Invalid argument. Expected number of minutes or string like \'1d2h3m4s\''
            await ctx.send(err)
            raise commands.BadArgument(err)

        if len(match.group(0)) == 0:
            raise commands.BadArgument()

        return timedelta(**{n: int(v) for n, v in match.groupdict(default='0').items()})


_TCallableCo = TypeVar('_TCallableCo', bound=Callable[..., Coroutine[Any, Any, None]])


def strict_group(f: _TCallableCo) -> _TCallableCo:
    '''
    This decorator wraps a command.group handler, and raises
     a UserInputError if the group was invoked without a subcommand.

    Without this, no help will be shown if no subcommand or an incorrect subcommand was specified.
    '''
    @functools.wraps(f)
    async def wrapped(self: commands.Cog, ctx: types.Context, *args: Any, **kwargs: Any) -> None:
        if not ctx.invoked_subcommand:
            raise commands.UserInputError('no subcommand supplied')
        return await f(self, ctx, *args, **kwargs)
    return wrapped  # type: ignore[return-value]


_TExc = TypeVar('_TExc', bound=commands.errors.CommandError)


def suppress_help(exc: _TExc) -> _TExc:
    '''
    Updates the supplied `CommandError` object to suppress sending a help message.
    (see `on_command_error` in error_handler.py)
    '''
    from . import error_handler  # fix circular import
    setattr(exc, error_handler._attr_suppress_help, True)
    return exc


async def owner_id(bot: commands.Bot) -> int:
    if not bot.owner_id:
        app_info = await bot.application_info()
        assert app_info.owner
        bot.owner_id = app_info.owner.id
    return bot.owner_id


def is_docker() -> bool:
    return os.path.exists('/.dockerenv')
