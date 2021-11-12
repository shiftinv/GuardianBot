import os
import json
import logging
import aiohttp
from typing import Any, Iterable, Iterator, List, Optional, Sized, Union

from ..config import Config


logger = logging.getLogger(__name__)


class BaseChecker(Iterable[str], Sized):
    def __init__(self, cache_name: str):
        self.__cache_name = cache_name
        self._strings: List[str] = []

        self._load_list()

    async def check_match(self, input: str) -> Optional[str]:
        ''' Returns a reason string if the input matched and should be blocked, returns None otherwise '''
        raise NotImplementedError

    @property
    def cache_path(self) -> str:
        return os.path.join(Config.data_dir, self.__cache_name)

    def _load_list(self) -> None:
        if not os.path.isfile(self.cache_path):
            return
        with open(self.cache_path, 'r') as f:
            self._strings.clear()
            self._strings.extend(json.load(f))
        logger.debug(f'loaded {len(self)} entries for {self}')

    def _write_list(self) -> None:
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(list(self._strings), f, indent=4)
        logger.debug(f'wrote {len(self)} entries for {self}')

    def __len__(self) -> int:
        return len(self._strings)

    def __iter__(self) -> Iterator[str]:
        yield from self._strings

    def __contains__(self, obj: Any) -> bool:
        return obj in self._strings


class ManualBaseChecker(BaseChecker):
    def entry_add(self, input: str) -> Union[bool, str]:
        '''
        Adds given input to list, returning True if successful, False if value already exists,
        or a string response if other validation checks failed
        '''
        if input in self._strings:
            return False
        self._strings.append(input)
        self._write_list()
        return True

    def entry_remove(self, input: str) -> bool:
        '''
        Removes given input from list, returning True if successful, or False if value doesn't exist
        '''
        if input not in self._strings:
            return False
        self._strings.remove(input)
        self._write_list()
        return True


class ExternalBaseChecker(BaseChecker):
    def __init__(self, cache_name: str, url: str):
        super().__init__(cache_name)
        self._url = url

    async def update(self, session: aiohttp.ClientSession) -> None:
        async with session.get(self._url) as res:
            res.raise_for_status()
            self._strings = await self._process_update(res)
        self._write_list()

    async def _process_update(self, res: aiohttp.ClientResponse) -> List[str]:
        raise NotImplementedError
