import logging
import aiohttp
import disnake
import functools
from pathlib import Path
from typing import Any, Awaitable, Callable, Generic, List, Optional, Tuple, Type, TypeVar, cast, get_args
from disnake.ext import commands, tasks

from .. import error_handler, interactions, multicmd, types, utils
from ..config import Config


logger = logging.getLogger(__name__)


# no `Optional[StrictModel]` bound since narrowing optional typevar bounds is close to impossible
_TState = TypeVar('_TState')
PermissionDecorator = Callable[[Any], Any]


class _BaseMeta(multicmd._MultiCmdMeta):
    def __init__(cls: Type['BaseCog'], *args: Any, **kwargs: Any):  # type: ignore
        super().__init__(*args, **kwargs)  # type: ignore
        for cmd in cls.__cog_app_commands__:
            if (
                isinstance(cmd, commands.InvokableApplicationCommand)
                and not isinstance(cmd, (commands.SubCommand, commands.SubCommandGroup))
            ):
                decorators, default = cls.cog_guild_permissions()
                if default is not None:
                    cmd.body.default_permission = default
                for dec in decorators:
                    r = dec(cmd)
                    assert r is cmd


class BaseCog(Generic[_TState], commands.Cog, metaclass=_BaseMeta):
    state: _TState
    _bot: types.Bot

    def __init__(self, bot: types.Bot):
        if not isinstance(bot, interactions.CustomSyncBot):
            raise TypeError('expected bot to be (a subclass of) `interactions.CustomSyncBot`')
        self._bot = bot

        self._state_path = Path(Config.data_dir) / 'state' / f'{type(self).__name__.lower()}.json'
        # get `_TState` at runtime
        state_type = get_args(type(self).__orig_bases__[0])[0]  # type: ignore
        if state_type is type(None):  # noqa: E721
            state_type = None
        else:
            assert issubclass(state_type, utils.StrictModel), f'state type must inherit from `StrictModel` (got \'{state_type}\')'
        self.__state_type: Optional[Type[utils.StrictModel]] = state_type

        self._read_state()

    def _read_state(self) -> None:
        if self.__state_type is None:
            self.state = None  # type: ignore
            return

        if self._state_path.exists():
            state = self.__state_type.parse_file(self._state_path)
        else:
            state = self.__state_type()
        self.state = cast(_TState, state)  # see `_TState` comment above
        self._write_state()

    def _write_state(self) -> None:
        if self.__state_type is None:
            return

        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(cast(utils.StrictModel, self.state).json(indent=4))

    # checks

    async def cog_check(self, ctx: types.Context) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    async def cog_slash_command_check(self, ctx: types.AppCI) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    async def cog_user_command_check(self, ctx: types.AppCI) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    async def cog_message_command_check(self, ctx: types.AppCI) -> bool:  # type: ignore [override]
        return await self.cog_any_check(ctx)

    # override in subclasses
    async def cog_any_check(self, ctx: types.AnyContext) -> bool:
        return True

    @staticmethod
    def cog_guild_permissions() -> Tuple[List[PermissionDecorator], Optional[bool]]:
        return [], None

    # other stuff

    @property
    def _guild(self) -> disnake.Guild:
        guild = self._bot.get_guild(Config.guild_id)
        assert guild
        return guild

    @disnake.utils.cached_property
    def _session(self) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=self._bot.http.connector,
        )
        session._request = functools.partial(session._request, proxy=self._bot.http.proxy)  # type: ignore[assignment]
        return session


_CogT = TypeVar('_CogT', bound=BaseCog[Any])
_LoopFunc = Callable[[_CogT], Awaitable[None]]


def loop_error_handled(**kwargs: Any) -> Callable[[_LoopFunc[_CogT]], tasks.Loop[_LoopFunc[_CogT]]]:
    def decorator(f: _LoopFunc[_CogT]) -> tasks.Loop[_LoopFunc[_CogT]]:
        @functools.wraps(f)
        async def wrap(self: _CogT) -> None:
            try:
                await f(self)
            except Exception as e:
                await error_handler.handle_task_error(self._bot, e)

        return tasks.loop(**kwargs)(wrap)
    return decorator
