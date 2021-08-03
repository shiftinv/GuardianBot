import logging
import discord
from discord.ext import commands

from ..list_checker import ListChecker
from ..config import Config


logger = logging.getLogger(__name__)


class FilterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self._bot = bot

        self.blocklist = ListChecker()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not await self._should_check(message):
            logger.debug(f'not checking message {message.id}')
            return

        if self.blocklist.check_match(message.content):
            await self._handle_blocked(message)

    async def _should_check(self, message: discord.Message) -> bool:
        if not message.guild:
            return False  # don't check DMs
        assert message.guild.id == Config.guild_id
        if message.author.bot:
            return False  # don't check bots

        ctx = await self._bot.get_context(message)  # type: commands.Context
        if ctx.command:
            return False  # don't check commands

        # TODO: filter by role(s) and/or channel
        return True

    async def _handle_blocked(self, message: discord.Message) -> None:
        logger.info(f'blocked message {message.id}')
        # TODO

    @commands.group()
    async def filter(self, ctx: commands.Context) -> None:
        pass

    @filter.command(name='add')
    async def filter_add(self, ctx: commands.Context, input: str) -> None:
        logger.debug(f'adding {input} to list')
        if self.blocklist.entry_add(input):
            await ctx.send(f'Successfully added `{input}`')
        else:
            await ctx.send(f'List already contains `{input}`')

    @filter.command(name='remove')
    async def filter_remove(self, ctx: commands.Context, input: str) -> None:
        logger.debug(f'removing {input} from list')
        if self.blocklist.entry_remove(input):
            await ctx.send(f'Successfully removed `{input}`')
        else:
            await ctx.send(f'List does not contain `{input}`')

    @filter.command(name='list')
    async def filter_list(self, ctx: commands.Context) -> None:
        if len(self.blocklist) == 0:
            await ctx.send('List contains no elements.')
        s = f'List contains {len(self.blocklist)} element(s):\n'
        s += '```\n' + '\n'.join(self.blocklist) + '\n```'
        await ctx.send(s)
