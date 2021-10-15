from dataclasses import dataclass
from discord.ext import commands
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar

from . import types
from .config import Config


def command(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    cmd_kwargs: Optional[Dict[str, Any]] = None,
    slash_kwargs: Optional[Dict[str, Any]] = None,
) -> Callable[[Callable[..., Any]], '_MultiCommand']:
    def wrap(f: Callable[..., Any]) -> _MultiCommand:
        return _MultiCommand(
            commands.command(
                name=types.unwrap_opt(name),
                help=description,
                **(cmd_kwargs or {})
            )(f),
            commands.slash_command(
                name=types.unwrap_opt(name),
                description=types.unwrap_opt(description),
                **(slash_kwargs or {})
            )(f)
        )
    return wrap


def group(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    cmd_group_kwargs: Optional[Dict[str, Any]] = None,
    slash_kwargs: Optional[Dict[str, Any]] = None,
) -> Callable[[Callable[..., Any]], '_MultiGroup']:
    def wrap(f: Callable[..., Any]) -> _MultiGroup:
        return _MultiGroup(
            commands.group(
                name=types.unwrap_opt(name),
                help=description,
                **(cmd_group_kwargs or {})
            )(f),
            commands.slash_command(
                name=types.unwrap_opt(name),
                description=types.unwrap_opt(description),
                **(slash_kwargs or {})
            )(f)
        )
    return wrap


async def send_response(ctx: types.AnyContext, content: Optional[str] = None, **kwargs: Any) -> None:
    if isinstance(ctx, types.AppCI):
        await ctx.response.send_message(content, **kwargs)
    else:
        await ctx.send(content, **kwargs)


#####
# internal stuff

_AnyCmd = commands.Command[commands.Cog, Any, None]  # type: ignore[type-arg]
_AnyGroup = commands.Group[commands.Cog, Any, None]  # type: ignore[type-arg]
_TCmd = TypeVar('_TCmd', _AnyCmd, _AnyGroup)
_TSlashCmd = TypeVar('_TSlashCmd', commands.InvokableSlashCommand, commands.SubCommandGroup, commands.SubCommand)
_TSlashGroup = TypeVar('_TSlashGroup', commands.InvokableSlashCommand, commands.SubCommandGroup)


@dataclass
class _MultiBase(Generic[_TCmd, _TSlashCmd]):
    _command: _TCmd
    _slash_command: _TSlashCmd

    # (ab)using __set_name__ for sanity checks
    def __set_name__(self, owner: Type[commands.Cog], name: str) -> None:
        from .cogs._base import BaseCog  # avoid circular import
        assert issubclass(owner, BaseCog), 'multicmd may only be used in types derived from `BaseCog`'


@dataclass
class _MultiCommand(_MultiBase[_AnyCmd, commands.InvokableSlashCommand]):
    ''' represents a top-level command (without any grouping above/below) '''
    pass


@dataclass
class _MultiSubCommand(_MultiBase[_AnyCmd, commands.SubCommand]):
    ''' represents a subcommand, either second-level (in group) or third-level (in subgroup) '''
    pass


@dataclass
class _MultiGroupBase(_MultiBase[_AnyGroup, _TSlashGroup]):
    ''' represents an abstract top-level/second-level group '''

    # top-level (_MultiGroup) and second-level (_MultiSubGroup) groups can have subcommands
    def subcommand(
        self,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        cmd_kwargs: Optional[Dict[str, Any]] = None,
        slash_subcmd_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Callable[..., Any]], _MultiSubCommand]:
        def wrap(f: Callable[..., Any]) -> _MultiSubCommand:
            return _MultiSubCommand(
                self._command.command(
                    name=types.unwrap_opt(name),
                    help=description,
                    **(cmd_kwargs or {})
                )(f),
                self._slash_command.sub_command(
                    name=types.unwrap_opt(name),
                    description=types.unwrap_opt(description),
                    **(slash_subcmd_kwargs or {})
                )(f)
            )
        return wrap


@dataclass
class _MultiGroup(_MultiGroupBase[commands.InvokableSlashCommand]):
    ''' represents a top-level group '''

    # only top-level groups can have subgroups
    def subgroup(
        self,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        cmd_group_kwargs: Optional[Dict[str, Any]] = None,
        slash_subgroup_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Callable[..., Any]], '_MultiSubGroup']:
        def wrap(f: Callable[..., Any]) -> _MultiSubGroup:
            return _MultiSubGroup(
                self._command.group(
                    name=types.unwrap_opt(name),
                    help=description,
                    **(cmd_group_kwargs or {})
                )(f),
                self._slash_command.sub_command_group(
                    name=types.unwrap_opt(name),
                    description=types.unwrap_opt(description),
                    **(slash_subgroup_kwargs or {})
                )(f)
            )
        return wrap


@dataclass
class _MultiSubGroup(_MultiGroupBase[commands.SubCommandGroup]):
    ''' represents a second-level subgroup '''
    pass


# see `_BaseCogMeta`
def _fixup_attrs(name: str, attrs: Dict[str, Any]) -> None:
    for k, v in attrs.copy().items():
        if isinstance(v, _MultiBase):
            if Config.debug:
                # printing, since logging isn't set up at this point yet
                print(f'patching command and slash command for \'{name}.{k}\'')

            for suffix, cmd in (('cmd', v._command), ('slash', v._slash_command)):
                new_key = f'_{k}_{suffix}'
                assert new_key not in attrs
                attrs[new_key] = cmd
