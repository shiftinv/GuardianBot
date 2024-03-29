import asyncio
import contextlib
import functools
import inspect
import os
import re
import sys
import types as _types
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, TypeVar, Union

import pydantic
from disnake.ext import commands

from . import types

_T = TypeVar("_T")
_U = TypeVar("_U")


def utcnow() -> datetime:
    # note: this uses `timezone.utc` instead of just calling `datetime.utcnow()`,
    #       as utcnow doesn't set tzinfo
    return datetime.now(timezone.utc)


async def wait_timeout(aw: Awaitable[_T], timeout: float, fallback: _U) -> Union[_T, _U]:
    try:
        return await asyncio.wait_for(aw, timeout)
    except asyncio.TimeoutError:
        return fallback


def extract_hosts(input: str) -> List[str]:
    return re.findall(r"https?://([^/?#<>\s]+)", input)


_timedelta_re = re.compile(
    "".join(
        rf"(?:(?P<{unit}>\d+){unit[0]})?"
        for unit in ["weeks", "days", "hours", "minutes", "seconds"]
    ),
    re.I,
)


async def convert_timedelta(ctx: types.AnyContext, arg: str) -> timedelta:
    if arg.isdigit():
        return timedelta(minutes=int(arg))

    if not (match := _timedelta_re.fullmatch(arg)):
        err = "Invalid argument. Expected number of minutes or string like '1d2h3m4s'"
        await ctx.send(err)
        raise commands.BadArgument(err)

    if len(match.group(0)) == 0:
        raise commands.BadArgument()

    return timedelta(**{n: int(v) for n, v in match.groupdict(default="0").items()})


def strict_group(f: types.THandlerType) -> types.THandlerType:
    """
    This decorator wraps a command.group handler, and raises
     a UserInputError if the group was invoked without a subcommand.

    Without this, no help will be shown if no subcommand or an incorrect subcommand was specified.

    For application command handlers, this is a no-op.
    """

    @functools.wraps(f)
    async def wrapped(self: commands.Cog, ctx: types.AnyContext, *args: Any, **kwargs: Any) -> None:
        if isinstance(ctx, commands.Context) and not ctx.invoked_subcommand:
            raise commands.UserInputError("no subcommand supplied")
        return await f(self, ctx, *args, **kwargs)

    return wrapped  # type: ignore[return-value]


_TExc = TypeVar("_TExc", bound=commands.errors.CommandError)


def suppress_help(exc: _TExc) -> _TExc:
    """
    Updates the supplied `CommandError` object to suppress sending a help message.
    (see `on_command_error` in error_handler.py)
    """
    from . import error_handler  # fix circular import

    setattr(exc, error_handler._attr_suppress_help, True)
    return exc


async def owner_id(bot: commands.Bot) -> int:
    if not bot.owner_id:
        app_info = await bot.application_info()
        assert app_info.owner
        bot.owner_id = app_info.owner.id
    return bot.owner_id


def is_docker() -> bool:
    return os.path.exists("/.dockerenv")


def debugger_active() -> bool:
    return bool(getattr(sys, "gettrace", lambda: False)())


@contextlib.asynccontextmanager
async def catch_and_exit(bot: types.Bot) -> AsyncIterator[None]:
    try:
        yield
    except Exception as e:
        try:
            from . import error_handler

            await error_handler.handle_task_error(bot, e)
        finally:
            sys.exit(1)


TCallable = TypeVar("TCallable", bound=Callable[..., Any])


def copy_patch_signature(func: TCallable, sig: inspect.Signature) -> TCallable:
    # copy function
    new_func = _types.FunctionType(
        func.__code__, func.__globals__, func.__name__, func.__defaults__, func.__closure__
    )
    new_func = functools.update_wrapper(new_func, func)
    new_func.__kwdefaults__ = func.__kwdefaults__  # type: ignore
    del new_func.__wrapped__

    # set signature
    new_func.__signature__ = sig  # type: ignore
    return new_func  # type: ignore


def patch_parameters(
    func: TCallable, map_func: Callable[[inspect.Parameter], Dict[str, Any]]
) -> TCallable:
    sig = inspect.signature(func)
    new_p = [p.replace(**map_func(p)) for p in sig.parameters.values()]
    return copy_patch_signature(func, sig.replace(parameters=new_p))


class dotdict(Dict[_T, _U]):
    __getattr__ = dict.get  # type: ignore
    __setattr__ = dict.__setitem__  # type: ignore
    __delattr__ = dict.__delitem__  # type: ignore


class StrictModel(pydantic.BaseModel):
    class Config:
        extra = pydantic.Extra.forbid
        validate_assignment = True
