import re
import asyncio
from datetime import datetime, timezone
from typing import Awaitable, List, TypeVar, Union

import discord


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
    await message.add_reaction('\N{WHITE HEAVY CHECK MARK}')
