import asyncio
import logging
import sys

import disnake
from disnake.ext import commands

from . import error_handler, types, utils
from .config import Config

assert sys.version_info[:2] >= (3, 9)

# required for aiodns on windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


logging.basicConfig(
    format="%(asctime)s: [%(levelname)s] (%(threadName)s) %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger("guardianbot")
logger.setLevel(logging.DEBUG if Config.debug else logging.INFO)


intents = disnake.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(Config.prefix),
    activity=disnake.Activity(type=disnake.ActivityType.watching, name="Link(s)"),
    intents=intents,
    test_guilds=[Config.guild_id],
    sync_commands_debug=Config.debug,
    reload=utils.debugger_active(),
    allowed_mentions=disnake.AllowedMentions.none(),
)


def load_ext(name: str) -> None:
    bot.load_extension(name, package=__package__)


load_ext(".cogs.core")
load_ext(".cogs.filter")


@bot.event
async def on_ready():
    guild = disnake.utils.get(bot.guilds, id=Config.guild_id)
    assert guild, f"couldn't find guild with ID {Config.guild_id}"
    logger.info(
        f"{bot.user} is connected to the following guild:\n" f"{guild.name} (id: {guild.id})"
    )

    logger.info(f"Latency: {int(bot.latency * 1000)}ms")


@bot.event
async def on_command(ctx: types.Context) -> None:
    logger.debug(
        f"{str(ctx.author)}/{ctx.author.id} invoked "
        f"command '{ctx.message.content}' "
        f"in '{ctx.channel}'"
    )


async def _on_app_cmd(ctx: types.AppCI, type: str) -> None:
    logger.debug(
        f"{str(ctx.author)}/{ctx.author.id} invoked "
        f"{type} command '{ctx.application_command.qualified_name} {ctx.filled_options}' "
        f"in '{ctx.channel}'"
    )


@bot.event
async def on_slash_command(ctx: types.AppCI) -> None:
    await _on_app_cmd(ctx, "slash")


@bot.event
async def on_user_command(ctx: types.AppCI) -> None:
    await _on_app_cmd(ctx, "user")


@bot.event
async def on_message_command(ctx: types.AppCI) -> None:
    await _on_app_cmd(ctx, "message")


# add global command checks
async def no_dm_filter(ctx: types.AnyContext) -> bool:
    if await bot.is_owner(ctx.author):
        return True
    return ctx.guild is not None


bot.check(no_dm_filter)
bot.application_command_check(
    slash_commands=True,
    user_commands=True,
    message_commands=True,
)(no_dm_filter)

# initialize global error handler
error_handler.init(bot)
error_handler.init_warnings_handler(bot)

# connect
bot.run(Config.token)
