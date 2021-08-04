import logging
import discord
from discord.ext import commands
from typing import cast

from . import cogs
from .config import Config


logging.basicConfig(format='%(asctime)s: [%(levelname)s] (%(threadName)s) %(name)s: %(message)s', level=logging.INFO)
logging.getLogger('guardianbot').setLevel(logging.DEBUG if Config.debug else logging.INFO)


bot = commands.Bot(Config.prefix)

bot.add_cog(cogs.FilterCog(bot))


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='Link(s)'))

    guild = discord.utils.get(bot.guilds, id=Config.guild_id)
    assert guild, f'couldn\'t find guild with ID {Config.guild_id}'
    print(
        f'{bot.user} is connected to the following guild:\n'
        f'{guild.name} (id: {guild.id})'
    )

    print(f'Latency: {int(bot.latency * 1000)}ms')


@bot.check
async def global_command_filter(ctx: commands.Context) -> bool:
    if await bot.is_owner(ctx.author):
        return True  # allow owner
    if ctx.guild is not None and cast(discord.Member, ctx.author).guild_permissions.manage_messages:
        return True  # allow users with 'Manage Messages' permission in guild
    return False

bot.run(Config.token)
