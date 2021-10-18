import discord
from discord.ext import commands
from typing import Any, Callable, Dict, Optional, TypeVar

from . import error_handler, multicmd, types, utils
from .config import Config


class CustomBot(commands.Bot):
    async def _sync_application_command_permissions(self) -> None:
        try:
            owner_id = await utils.owner_id(self)

            # iterate over defined permissions of all commands
            for command in self.application_commands:
                # make sure `default_permission` is `False` if custom permissions are set
                if command.permissions:
                    assert command.body.default_permission is False, \
                        f'custom command permissions require `default_permission = False` (command: \'{command.qualified_name}\')'

                for partial_perms in command.permissions.values():
                    # if partial permissions contain marker value, replace with owner ID
                    owner_perms = discord.utils.get(partial_perms.permissions, id=_owner_marker)
                    if owner_perms is not None:
                        assert discord.utils.get(partial_perms.permissions, id=owner_id) is None, \
                            f'permission override for owner ID ({owner_id}) already exists'
                        owner_perms.id = owner_id

            # call original func
            await super()._sync_application_command_permissions()
        except Exception as e:
            await error_handler.handle_task_error(self, e)
            exit(1)  # can't re-raise, since we're running in a separate task without error handling


_owner_marker = -123412344321432100112233440011223344  # just a random number (supposed to be an invalid ID)

_TCmd = TypeVar(
    '_TCmd',
    commands.InvokableApplicationCommand,
    types.HandlerType,
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
        new_user_ids = dict(user_ids or {})  # copy
        # add marker ID to user IDs if required
        if owner is not None:
            new_user_ids[_owner_marker] = owner

        dec = commands.guild_permissions(
            Config.guild_id,
            role_ids=types.unwrap_opt(role_ids),
            user_ids=new_user_ids
        )

        dec_input: Any
        if isinstance(cmd, (multicmd._MultiCommand, multicmd._MultiGroup)):
            dec_input = cmd._slash_command
        elif isinstance(cmd, multicmd._MultiBase) or not callable(cmd):
            raise TypeError(f'permissions cannot be set on `{type(cmd).__name__}` objects')
        else:
            dec_input = cmd

        # apply decorator to handler func/object
        r = dec(dec_input)
        # sanity check to protect against internal changes, since we're not returning the decorator's result
        assert r is dec_input

        return cmd
    return wrap


if Config.mod_role_ids:
    allow_mod = allow(owner=True, role_ids=dict.fromkeys(Config.mod_role_ids, True))
    allow_mod_default = False
else:
    # if no mod role IDs are configured, don't override any permissions
    allow_mod: Callable[[_TCmd], _TCmd] = lambda x: x  # type: ignore[no-redef]  # noqa: E731
    allow_mod_default = True
