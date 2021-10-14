from dataclasses import dataclass
from discord.ext import commands
from typing import Any, Callable, Dict, Optional, Type

from . import types
from .config import Config


def command(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    command_kwargs: Optional[Dict[str, Any]] = None,
    slash_kwargs: Optional[Dict[str, Any]] = None,
) -> Callable[[Callable[..., Any]], '_MultiCommand']:
    def wrap(f: Callable[..., Any]) -> _MultiCommand:
        return _MultiCommand(
            commands.Command(
                f,
                name=name,
                help=description,
                **(command_kwargs or {})
            ),
            commands.InvokableSlashCommand(
                f,
                name=types.unwrap_opt(name),
                description=types.unwrap_opt(description),
                **(slash_kwargs or {})
            )
        )
    return wrap


async def send_response(ctx: types.AnyContext, content: Optional[str] = None, **kwargs: Any) -> None:
    if isinstance(ctx, types.AppCI):
        await ctx.response.send_message(content, **kwargs)
    else:
        await ctx.send(content, **kwargs)


#####
# internal stuff

@dataclass
class _MultiCommand:
    _command: commands.Command[commands.Cog, Any, None]  # type: ignore[type-arg]
    _slash_command: commands.InvokableSlashCommand

    # (ab)using __set_name__ for sanity checks
    def __set_name__(self, owner: Type[commands.Cog], name: str) -> None:
        from .cogs._base import BaseCog  # avoid circular import
        assert issubclass(owner, BaseCog), 'multicmd may only be used in types derived from `BaseCog`'


# see `_BaseCogMeta`
def _fixup_attrs(name: str, attrs: Dict[str, Any]) -> None:
    for k, v in attrs.copy().items():
        if isinstance(v, _MultiCommand):
            if Config.debug:
                # printing, since logging isn't set up at this point yet
                print(f'patching command and slash command for \'{name}.{k}\'')

            for suffix, cmd in (('cmd', v._command), ('slash', v._slash_command)):
                new_key = f'_{k}_{suffix}'
                assert new_key not in attrs
                attrs[new_key] = cmd
