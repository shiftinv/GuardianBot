import disnake
from disnake.ext import commands
from typing import Any, Callable, Coroutine, Optional, Protocol, TypeVar, Union


# general definitions
Bot = commands.Bot
Context = commands.Context[Bot]


# useful typing shortcuts
AppCI = disnake.ApplicationCommandInteraction
AnyContext = Union[Context, AppCI]

NoneCoro = Coroutine[Any, Any, None]
HandlerType = Callable[..., NoneCoro]
THandlerType = TypeVar('THandlerType', bound=HandlerType)


# some typing utils (mostly to work around incorrect interface specs in discord.py):

_T = TypeVar('_T')


class _SupportsID(Protocol):
    id: int


def to_snowflake(val: _SupportsID) -> disnake.abc.Snowflake:
    return val  # type: ignore


def unwrap_opt(val: Optional[_T]) -> _T:
    return val  # type: ignore
