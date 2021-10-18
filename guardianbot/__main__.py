import sys
import asyncio
import logging
import discord

from . import checks, interactions, error_handler, types, utils
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

bot = interactions.CustomBot(
    command_prefix=Config.prefix,
    intents=intents,
    test_guilds=[Config.guild_id],
    sync_commands_debug=Config.debug,
    sync_permissions=True,
    reload=utils.debugger_active(),
)


def load_ext(name: str) -> None:
    bot.load_extension(name, package=__package__)


load_ext('.cogs.core')
load_ext('.cogs.filter')


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


@bot.event
async def on_command(ctx: types.Context) -> None:
    logger.debug(
        f'{str(ctx.author)}/{ctx.author.id} invoked '
        f'command \'{ctx.message.content}\' '
        f'in \'{ctx.channel}\''
    )


# TODO: add other (user/message) command events
@bot.event
async def on_slash_command(ctx: types.AppCI) -> None:
    logger.debug(
        f'{str(ctx.author)}/{ctx.author.id} invoked '
        f'slash command \'/{ctx.application_command.qualified_name} {ctx.filled_options}\' '
        f'in \'{ctx.channel}\''
    )


# add global command checks
cmd_filter = checks.command_filter()
bot.check(cmd_filter)
bot.application_command_check(slash_commands=True, user_commands=True, message_commands=True)(cmd_filter)

# initialize global error handler
error_handler.init(bot)

# connect
bot.run(Config.token)
