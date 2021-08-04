import json
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from typing import Any, Dict, Generic, TypeVar, get_args
from discord.ext import commands


from ..config import Config


class _SetEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return {'$__set': list(o)}
        if isinstance(o, datetime):
            return {'$__datetime': o.isoformat()}
        return super().default(o)


def _set_decoder(dct: Dict[str, Any]) -> Any:
    if '$__set' in dct:
        return set(dct['$__set'])
    if '$__datetime' in dct:
        return datetime.fromisoformat(dct['$__datetime'])
    return dct


_TState = TypeVar('_TState')


class BaseCog(Generic[_TState], commands.Cog):
    state: _TState

    def __init__(self, bot: commands.Bot):
        self._bot = bot

        self.__state_path = Path(Config.data_dir) / 'state' / f'{type(self).__name__}.json'
        self.__state_type = get_args(type(self).__orig_bases__[0])[0]
        self._read_state()

    def _read_state(self) -> None:
        if self.__state_path.exists():
            self.state = self.__state_type(**json.loads(self.__state_path.read_text(), object_hook=_set_decoder))
        else:
            self.state = self.__state_type()
            self._write_state()

    def _write_state(self) -> None:
        self.__state_path.parent.mkdir(parents=True, exist_ok=True)
        self.__state_path.write_text(json.dumps(asdict(self.state), cls=_SetEncoder, indent=4))
