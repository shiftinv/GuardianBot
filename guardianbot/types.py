from typing import Any, Callable, Coroutine, TypeVar, Union

import disnake
from disnake.ext import commands

# general definitions
Bot = commands.Bot
Context = commands.Context[Bot]


# useful typing shortcuts
AppCI = disnake.ApplicationCommandInteraction[Bot]
AnyContext = Union[Context, AppCI]

NoneCoro = Coroutine[Any, Any, None]
HandlerType = Callable[..., NoneCoro]
THandlerType = TypeVar("THandlerType", bound=HandlerType)
