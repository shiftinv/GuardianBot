from dataclasses import dataclass
from discord.ext import commands
from typing import Any, Callable, Dict, Optional

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


#####
# internal stuff

@dataclass
class _MultiCommand:
    command: commands.Command[commands.Cog, Any, None]  # type: ignore[type-arg]
    slash_command: commands.InvokableSlashCommand


# see `_BaseCogMeta`
def _fixup_attrs(name: str, attrs: Dict[str, Any]) -> None:
    for k, v in attrs.copy().items():
        if isinstance(v, _MultiCommand):
            if Config.debug:
                # printing, since logging isn't set up at this point yet
                print(f'patching command and slash command for \'{name}.{k}\'')

            for suffix, cmd in (('cmd', v.command), ('slash', v.slash_command)):
                new_key = f'_{k}_{suffix}'
                assert new_key not in attrs
                attrs[new_key] = cmd
