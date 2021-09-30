import sys
import asyncio
import logging
import discord
from discord.ext import commands
from typing import cast

from . import cogs, error_handler, types
from .cogs._base import BaseCog
from .config import Config


assert sys.version_info[:2] >= (3, 9)

# required for aiodns on windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


logging.basicConfig(format='%(asctime)s: [%(levelname)s] (%(threadName)s) %(name)s: %(message)s', level=logging.INFO)
logger = logging.getLogger('guardianbot')
logger.setLevel(logging.DEBUG if Config.debug else logging.INFO)


intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix=Config.prefix,
    intents=intents
)

bot.add_cog(cogs.CoreCog(bot))
bot.add_cog(cogs.FilterCog(bot))


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='Link(s)'))

    guild = discord.utils.get(bot.guilds, id=Config.guild_id)
    assert guild, f'couldn\'t find guild with ID {Config.guild_id}'
    logger.info(
        f'{bot.user} is connected to the following guild:\n'
        f'{guild.name} (id: {guild.id})'
    )

    logger.info(f'Latency: {int(bot.latency * 1000)}ms')

    for cog in bot.cogs.values():
        if isinstance(cog, BaseCog):
            cog._guild = guild


@bot.check
async def global_command_filter(ctx: types.Context) -> bool:
    if await bot.is_owner(ctx.author):
        return True  # allow owner
    if ctx.guild and ctx.guild.id == Config.guild_id and cast(discord.Member, ctx.author).guild_permissions.manage_messages:
        return True  # allow users with 'Manage Messages' permission in guild
    return False


error_handler.init(bot)

bot.run(Config.token)
