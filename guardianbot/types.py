import discord
from discord.ext import commands
from typing import Any, Callable, Coroutine, Optional, Protocol, TypeVar, Union


# general definitions
Bot = commands.Bot
Context = commands.Context[Bot]


# useful typing shortcuts
AppCI = discord.ApplicationCommandInteraction
AnyContext = Union[Context, AppCI]

NoneCoro = Coroutine[Any, Any, None]
HandlerType = Callable[..., NoneCoro]
THandlerType = TypeVar('THandlerType', bound=HandlerType)


# fix missing import in discord-disnake shim
import disnake.ext.tasks  # noqa: E402
Loop = disnake.ext.tasks.Loop


# some typing utils (mostly to work around incorrect interface specs in discord.py):

_T = TypeVar('_T')


class _SupportsID(Protocol):
    id: int


def to_snowflake(val: _SupportsID) -> discord.abc.Snowflake:
    return val  # type: ignore


def unwrap_opt(val: Optional[_T]) -> _T:
    return val  # type: ignore
