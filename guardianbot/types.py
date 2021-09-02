from typing import TYPE_CHECKING

from discord.ext import commands


Context = commands.Context

if TYPE_CHECKING:
    Cog = commands.Cog[Context]
    Bot = commands.Bot[Context]
else:
    Cog = commands.Cog
    Bot = commands.Bot
