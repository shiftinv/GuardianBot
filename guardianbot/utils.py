import re
import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from typing import Awaitable, List, TypeVar, Union

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
