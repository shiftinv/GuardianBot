import logging
import discord
from discord.ext import commands
from discord.ext.commands.base_core import InvokableApplicationCommand
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

from . import error_handler, multicmd, utils
from .config import Config


logger = logging.getLogger(__name__)


class CustomBot(commands.Bot):
    async def _sync_application_commands(self) -> None:
        try:
            # register commands
            await super()._sync_application_commands()
            if not self._sync_commands:
                return

            guild_id = Config.guild_id

            # TODO: workaround until this is fixed: https://github.com/EQUENOS/disnake/blob/95c1cd4ff2cdf62232ffcba6422e91a6b11a14bb/disnake/state.py#L1590
            if isinstance(self._connection._guild_application_commands.get(guild_id), set):
                await self._cache_application_commands()

            # collect new permissions
            new_permissions: Dict[str, discord.PartialGuildAppCmdPerms] = {}

            # iterate over registered command handlers
            for command in self.application_commands:
                # get custom permission data, skip if not set
                reqs: Optional[_AppCommandPermissions] = getattr(command, '__app_cmd_perms__', None)
                if not reqs:
                    continue

                # get corresponding guild command (required for guild-specific command ID)
                guild_command = self.get_guild_command_named(guild_id, command.name)
                assert guild_command, f'No guild command with name \'{command.name}\' found in cache, something is broken'
                assert guild_command.id is not None  # this should never fail

                # create new permission data
                assert command.name not in new_permissions
                new_permissions[command.name] = await reqs.to_perms(self, guild_command.id)

            if new_permissions:
                perms_list = "\n".join(
                    f'\t{n}: {[p.to_dict() for p in v.permissions]}'
                    for n, v in new_permissions.items()
                )
                logger.debug(f'setting new permissions:\n{perms_list}')

                await self.bulk_edit_command_permissions(guild_id, list(new_permissions.values()))
                logger.debug('successfully set permissions')

        except Exception as e:
            await error_handler.handle_task_error(self, e)
            exit(1)  # can't re-raise, since we're running in a separate task without error handling


_TCmd = TypeVar(
    '_TCmd',
    InvokableApplicationCommand,
    # permissions can only be set on top level, not per subcommand/subgroup
    multicmd._MultiCommand,
    multicmd._MultiGroup
)


def allow(
    *,
    role_ids: Optional[Dict[int, bool]] = None,
    user_ids: Optional[Dict[int, bool]] = None,
    owner: Optional[bool] = None
) -> Callable[[_TCmd], _TCmd]:
    def wrap(cmd: _TCmd) -> _TCmd:
        app_cmd: InvokableApplicationCommand
        if isinstance(cmd, InvokableApplicationCommand):
            app_cmd = cmd
        else:
            app_cmd = cmd._slash_command

        assert app_cmd.body.default_permission is False, \
            f'custom command permissions require `default_permission = False` (command: \'{app_cmd.qualified_name}\')'
        setattr(app_cmd, '__app_cmd_perms__', _AppCommandPermissions(
            role_ids=role_ids,
            user_ids=user_ids,
            owner=owner
        ))
        return cmd
    return wrap


# TODO: wrap slash_command decorator and set default_permission automatically (if arg is None)
if Config.mod_role_ids:
    allow_mod = allow(owner=True, role_ids=dict.fromkeys(Config.mod_role_ids, True))
    allow_mod_default = False
else:
    # if no mod role IDs are configured, don't override any permissions
    allow_mod = lambda x: x  # noqa: E731
    allow_mod_default = True


@dataclass(frozen=True)
class _AppCommandPermissions:
    role_ids: Optional[Dict[int, bool]]
    user_ids: Optional[Dict[int, bool]]
    owner: Optional[bool]

    def __post_init__(self) -> None:
        if (not self.role_ids) and (not self.user_ids) and self.owner is None:
            raise discord.errors.InvalidArgument('at least one of \'role_ids\', \'user_ids\', \'owner\' must be set')

    async def to_perms(self, bot: commands.Bot, command_id: int) -> discord.PartialGuildAppCmdPerms:
        user_ids = dict(self.user_ids or {})
        # add owner to user IDs
        if self.owner is not None:
            owner_id = await utils.owner_id(bot)
            user_ids[owner_id] = self.owner

        return discord.PartialGuildAppCmdPerms(
            command_id,
            role_ids=self.role_ids or {},
            user_ids=user_ids
        )
