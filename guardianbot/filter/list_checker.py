import os
import json
import logging
from typing import Iterator, List

from ..config import Config


logger = logging.getLogger(__name__)


class ListChecker:
    def __init__(self):
        self.__strings: List[str] = []

        self._load_list()

    def check_match(self, input: str) -> bool:
        # TODO: maybe improve this
        return any(s in input for s in self.__strings)

    def entry_add(self, input: str) -> bool:
        if input in self.__strings:
            return False
        self.__strings.append(input)
        self._write_list()
        return True

    def entry_remove(self, input: str) -> bool:
        if input not in self.__strings:
            return False
        self.__strings.remove(input)
        self._write_list()
        return True

    @property
    def cache_path(self) -> str:
        return os.path.join(Config.data_dir, 'blocklist.json')

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
