import json
import logging
import discord
import functools
from pathlib import Path
from datetime import datetime
from dataclasses import asdict, fields, is_dataclass
from typing import Any, Awaitable, Callable, Dict, Generic, Type, TypeVar, get_args
from discord.ext import commands, tasks

from .. import error_handler, multicmd, types
from ..config import Config


logger = logging.getLogger(__name__)


class _CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return {'$__set': list(o)}
        if isinstance(o, datetime):
            return {'$__datetime': o.isoformat()}
        return super().default(o)


def _custom_decoder(dct: Dict[str, Any]) -> Any:
    if '$__set' in dct:
        return set(dct['$__set'])
    if '$__datetime' in dct:
        return datetime.fromisoformat(dct['$__datetime'])
    return dct


# this is a hack for the multicmd decorator
class _BaseCogMeta(commands.CogMeta):
    def __new__(cls: Type['_BaseCogMeta'], *args: Any, **kwargs: Any) -> '_BaseCogMeta':
        multicmd._fixup_attrs(args[0], args[2])
        self = super().__new__(cls, *args, **kwargs)
        return self  # type: ignore[return-value]


_TState = TypeVar('_TState')


class BaseCog(Generic[_TState], commands.Cog, metaclass=_BaseCogMeta):
    state: _TState
    _bot: types.Bot
    _guild: discord.Guild = None  # type: ignore  # late init

    def __init__(self, bot: types.Bot):
        self._bot = bot

        self.__state_path = Path(Config.data_dir) / 'state' / f'{type(self).__name__.lower()}.json'
        # get `_TState` at runtime
        self.__state_type = get_args(type(self).__orig_bases__[0])[0]  # type: ignore
        if self.__state_type is type(None):  # noqa: E721
            self.__state_type = None
        else:
            assert is_dataclass(self.__state_type), f'state type must be a dataclass (got \'{self.__state_type}\')'

        self._read_state()

    def _read_state(self) -> None:
        if self.__state_type is None:
            self.state = None  # type: ignore
            return

        if self.__state_path.exists():
            state_dict: Dict[str, Any] = json.loads(self.__state_path.read_text(), object_hook=_custom_decoder)
            state_field_names = {field.name for field in fields(self.__state_type)}
            for key in list(state_dict.keys()):
                if key not in state_field_names:
                    logger.warning(f'removing unknown state field in \'{self.__state_path}\': \'{key}\'')
                    del state_dict[key]
            self.state = self.__state_type(**state_dict)
        else:
            self.state = self.__state_type()
        self._write_state()

    def _write_state(self) -> None:
        if self.__state_type is None:
            return

        self.__state_path.parent.mkdir(parents=True, exist_ok=True)
        self.__state_path.write_text(json.dumps(asdict(self.state), cls=_CustomEncoder, indent=4))

    async def cog_check(self, ctx: types.Context) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    async def cog_slash_command_check(self, ctx: types.AppCI) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    # TODO: test user/message command checks
    async def cog_user_command_check(self, ctx: types.AppCI) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    async def cog_message_command_check(self, ctx: types.AppCI) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    # override in subclasses
    async def cog_any_check(self, ctx: types.AnyContext) -> bool:
        return True


_CogT = TypeVar('_CogT', bound=BaseCog[Any])
_LoopFunc = Callable[[_CogT], Awaitable[None]]


def loop_error_handled(**kwargs: Any) -> Callable[[_LoopFunc[_CogT]], types.Loop[_LoopFunc[_CogT]]]:
    def decorator(f: _LoopFunc[_CogT]) -> types.Loop[_LoopFunc[_CogT]]:
        @functools.wraps(f)
        async def wrap(self: _CogT) -> None:
            try:
                await f(self)
            except Exception as e:
                await error_handler.handle_task_error(self._bot, e)

        return tasks.loop(**kwargs)(wrap)
    return decorator
