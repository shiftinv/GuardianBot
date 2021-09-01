import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Iterable, Iterator, List, Optional, Sized, Union

from ..config import Config


logger = logging.getLogger(__name__)


class BaseChecker(ABC, Iterable[str], Sized):
    def __init__(self, cache_name: str):
        self.__cache_name = cache_name
        self.__strings: List[str] = []

        self._load_list()

    @abstractmethod
    async def check_match(self, input: str) -> Optional[str]:
        ''' Returns a reason string if the input matched and should be blocked, returns None otherwise '''
        raise NotImplementedError

    def entry_add(self, input: str) -> Union[bool, str]:
        '''
        Adds given input to list, returning True if successful, False if value already exists,
        or a string response if other validation checks failed
        '''
        if input in self.__strings:
            return False
        self.__strings.append(input)
        self._write_list()
        return True

    def entry_remove(self, input: str) -> bool:
        '''
        Removes given input from list, returning True if successful, or False if value doesn't exist
        '''
        if input not in self.__strings:
            return False
        self.__strings.remove(input)
        self._write_list()
        return True

    @property
    def cache_path(self) -> str:
        return os.path.join(Config.data_dir, self.__cache_name)

    def _load_list(self) -> None:
        if not os.path.isfile(self.cache_path):
            return
        with open(self.cache_path, 'r') as f:
            self.__strings.clear()
            self.__strings.extend(json.load(f))
        logger.debug(f'loaded {len(self)} entries for {self}')

    def _write_list(self) -> None:
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(list(self.__strings), f, indent=4)
        logger.debug(f'wrote {len(self)} entries for {self}')

    def __len__(self) -> int:
        return len(self.__strings)

    def __iter__(self) -> Iterator[str]:
        yield from self.__strings
