from __future__ import absolute_import
import types as _types

import inspect
from dataclasses import dataclass
from disnake.ext import commands
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar, cast

from . import types, utils
from .config import Config


def command(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    cmd_kwargs: Optional[Dict[str, Any]] = None,
    slash_kwargs: Optional[Dict[str, Any]] = None,
) -> Callable[[types.HandlerType], '_MultiCommand']:
    def wrap(f: types.HandlerType) -> _MultiCommand:
        return _MultiCommand.create(
            commands.command, commands.slash_command, f,
            name=name,
            description=description,
            cmd_kwargs=cmd_kwargs,
            slash_kwargs=slash_kwargs
        )
    return wrap


_TCog = TypeVar('_TCog', bound=commands.Cog)


def group(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    cmd_group_kwargs: Optional[Dict[str, Any]] = None,
    slash_kwargs: Optional[Dict[str, Any]] = None,
) -> Callable[[Callable[[_TCog, types.AnyContext], types.NoneCoro]], '_MultiGroup']:
    def wrap(f: Callable[[_TCog, types.AnyContext], types.NoneCoro]) -> _MultiGroup:
        return _MultiGroup.create(
            commands.group, commands.slash_command, utils.strict_group(f),
            name=name,
            description=description,
            cmd_kwargs=cmd_group_kwargs,
            slash_kwargs=slash_kwargs
        )
    return wrap


#####
# internal stuff

_T = TypeVar('_T')
_DecoratorType = Callable[..., Callable[[types.HandlerType], _T]]

_AnyCmd = commands.Command[commands.Cog, Any, None]  # type: ignore[type-arg]
_AnyGroup = commands.Group[commands.Cog, Any, None]  # type: ignore[type-arg]
_TCmd = TypeVar('_TCmd', _AnyCmd, _AnyGroup)
_TSlashCmd = TypeVar('_TSlashCmd', commands.InvokableSlashCommand, commands.SubCommandGroup, commands.SubCommand)
_TSlashGroup = TypeVar('_TSlashGroup', commands.InvokableSlashCommand, commands.SubCommandGroup)


@dataclass
class _MultiBase(Generic[_TCmd, _TSlashCmd]):
    _command: _TCmd
    _slash_command: _TSlashCmd

    @classmethod
    def create(
        cls: Type[_T],
        cmd_decorator: _DecoratorType[_TCmd],
        slash_decorator: _DecoratorType[_TSlashCmd],
        func: types.HandlerType,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        cmd_kwargs: Optional[Dict[str, Any]] = None,
        slash_kwargs: Optional[Dict[str, Any]] = None
    ) -> _T:
        _cls = cast(Type[_MultiBase[_TCmd, _TSlashCmd]], cls)  # typing generic classmethods and return types correctly is basically impossible

        # use slash command's `Param` defaults as classic command's defaults as well
        cmd_func = _cls.__replace_defaults(func)

        # create new instance with classic command and slash command
        inst = _cls(
            cmd_decorator(
                name=name,
                help=description,
                **(cmd_kwargs or {})
            )(cmd_func),
            slash_decorator(
                name=name,
                description=description,
                **(slash_kwargs or {})
            )(func)
        )
        return cast(_T, inst)

    @staticmethod
    def __replace_defaults(func: types.HandlerType) -> types.HandlerType:
        # (this is a terrible hack, nothing to see here, move along)

        # build new signature
        sig = inspect.signature(func)
        new_p = []
        for p in sig.parameters.values():
            # if parameter default is disnake's `ParamInfo`,
            # set the value to `ParamInfo.default` instead
            if isinstance(p.default, commands.ParamInfo):
                def_val = p.default.default
                def_val = p.empty if def_val is ... else def_val
                new_p.append(p.replace(default=def_val))
            else:
                new_p.append(p.replace())  # create a copy
        sig = sig.replace(parameters=new_p)

        # copy function
        new_func = _types.FunctionType(func.__code__, func.__globals__, func.__name__, func.__defaults__, func.__closure__)  # type: ignore[attr-defined]
        new_func.__dict__.update(func.__dict__)

        # set signature
        new_func.__signature__ = sig  # type: ignore[attr-defined]
        return new_func

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
    ) -> Callable[[types.HandlerType], _MultiSubCommand]:
        def wrap(f: types.HandlerType) -> _MultiSubCommand:
            return _MultiSubCommand.create(
                self._command.command, self._slash_command.sub_command, f,
                name=name,
                description=description,
                cmd_kwargs=cmd_kwargs,
                slash_kwargs=slash_subcmd_kwargs
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
        description: Optional[str] = None,  # note: this only applies to "standard" commands
        cmd_group_kwargs: Optional[Dict[str, Any]] = None,
        slash_subgroup_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Callable[[_TCog, types.AnyContext], types.NoneCoro]], '_MultiSubGroup']:
        def wrap(f: Callable[[_TCog, types.AnyContext], types.NoneCoro]) -> _MultiSubGroup:
            return _MultiSubGroup.create(
                self._command.group, self._slash_command.sub_command_group, utils.strict_group(f),
                name=name,
                description=description,
                cmd_kwargs=cmd_group_kwargs,
                slash_kwargs=slash_subgroup_kwargs
            )
        return wrap


@dataclass
class _MultiSubGroup(_MultiGroupBase[commands.SubCommandGroup]):
    ''' represents a second-level subgroup '''
    pass


# this is a hack for the multicmd decorator
class _MultiCmdMeta(commands.CogMeta):
    def __new__(cls: Type['_MultiCmdMeta'], *args: Any, **kwargs: Any) -> '_MultiCmdMeta':
        name, _, attrs = args
        for k, v in attrs.copy().items():
            if isinstance(v, _MultiBase):
                if Config.debug:
                    # printing, since logging isn't set up at this point yet
                    print(f'patching command and slash command for \'{name}.{k}\'')

                # add command and slash command to namespace
                for suffix, cmd in (('cmd', v._command), ('slash', v._slash_command)):
                    new_key = f'_{k}_{suffix}'
                    assert new_key not in attrs
                    attrs[new_key] = cmd

        return super().__new__(cls, *args, **kwargs)  # type: ignore[return-value]
