from discord.ext import commands
from typing import Callable, Dict, List, Optional, TypeVar, Union

from . import multicmd, types, utils
from .config import Config


class CustomSyncBot(commands.Bot):
    async def _sync_application_command_permissions(self) -> None:
        async with utils.catch_and_exit(self, intercept_warnings=True):
            for command in self.application_commands:
                # make sure `default_permission` is `False` if custom permissions are set
                all_perms: List[bool] = []
                for u in command.permissions.values():
                    for p in (u.permissions, u.role_ids, u.user_ids, {None: u.owner} if u.owner is not None else None):
                        if not p:
                            continue
                        all_perms.extend(p.values())
                if all_perms and all(p is True for p in all_perms):
                    assert command.body.default_permission is False, \
                        f'custom command permissions require `default_permission = False` (command: \'{command.qualified_name}\')'

            # call original func
            return await super()._sync_application_command_permissions()

    async def _sync_application_commands(self) -> None:
        async with utils.catch_and_exit(self, intercept_warnings=True):
            return await super()._sync_application_commands()


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
        dec = commands.guild_permissions(
            Config.guild_id,
            role_ids=types.unwrap_opt(role_ids),
            user_ids=types.unwrap_opt(user_ids),
            owner=types.unwrap_opt(owner),
        )

        dec_input: Union[commands.InvokableApplicationCommand, types.HandlerType]
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
