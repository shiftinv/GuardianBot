import discord
from discord.ext import commands
from typing import Any, Callable, Coroutine, cast

from . import types
from .config import Config


def command_filter(**perms: bool) -> Callable[[commands.Context], Coroutine[Any, Any, bool]]:
    '''
    Returns a command filter that allows commands to be used by:
      - the owner
      - guild members (in guilds), optionally requiring specified permissions
    '''

    async def func(ctx: types.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            # allow owner
            return True
        if ctx.guild and ctx.guild.id == Config.guild_id:
            # allow in guilds, if permissions match
            user_perms = cast(discord.Member, ctx.author).guild_permissions
            return all(getattr(user_perms, k) == v for k, v in perms.items())
        return False
    return func


manage_messages = command_filter(manage_messages=True)