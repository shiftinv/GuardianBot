import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Collection, Iterator, List, Optional, Sequence, Union

import aiohttp
import disnake

from ..config import Config

__all__ = [
    "AnyMessageList",
    "CheckContext",
    "BaseChecker",
    "ExternalBaseChecker",
    "ManualBaseChecker",
]

AnyMessageList = Sequence[Union[disnake.Message, disnake.PartialMessage]]


@dataclass(frozen=True)
class CheckContext:
    message: disnake.Message
    string: str
    author: disnake.Member

    @classmethod
    def from_message(cls, msg: disnake.Message):
        strings: List[str] = [msg.content]
        for embed in msg.embeds:
            embed_contents = [embed.title or "", embed.description or ""]
            embed_contents.extend(f"{field.name}: {field.value}" for field in embed.fields)
            strings.extend(embed_contents)

        return cls(msg, "\n".join(s for s in strings if s), cls.get_author(msg))

    @staticmethod
    def get_author(msg: disnake.Message) -> disnake.Member:
        author = msg.author
        if msg._interaction_user_id:
            assert msg.guild  # this always exists here
            author = msg.guild.get_member(msg._interaction_user_id)
        assert isinstance(author, disnake.Member)
        return author


@dataclass(frozen=True)
class CheckResult:
    # reason for filter match
    reason: str
    # hostname if host-based block (IP, bad-domains, ...)
    host: Optional[str] = None
    # messages to delete, if multiple
    messages: Optional[AnyMessageList] = None


logger = logging.getLogger(__name__)


class BaseChecker(Collection[str]):
    def __init__(self, cache_name: str):
        self.__cache_name = cache_name
        self._strings: List[str] = []

        self._load_list()

    async def check_match(self, context: CheckContext) -> Optional[CheckResult]:
        """Returns a reason string if the input matched and should be blocked, returns None otherwise"""
        raise NotImplementedError

    @property
    def cache_path(self) -> str:
        return os.path.join(Config.data_dir, self.__cache_name)

    def _load_list(self) -> None:
        if not os.path.isfile(self.cache_path):
            return
        with open(self.cache_path, "r") as f:
            self._strings.clear()
            self._strings.extend(json.load(f))
        logger.debug(f"loaded {len(self)} entries for {self}")

    def _write_list(self) -> None:
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump(list(self._strings), f, indent=4)
        logger.debug(f"wrote {len(self)} entries for {self}")

    def __len__(self) -> int:
        return len(self._strings)

    def __iter__(self) -> Iterator[str]:
        yield from self._strings

    def __contains__(self, obj: Any) -> bool:
        return obj in self._strings


class ManualBaseChecker(BaseChecker):
    def entry_add(self, input: str) -> Union[bool, str]:
        """
        Adds given input to list, returning True if successful, False if value already exists,
        or a string response if other validation checks failed
        """
        if input in self._strings:
            return False
        self._strings.append(input)
        self._write_list()
        return True

    def entry_remove(self, input: str) -> bool:
        """
        Removes given input from list, returning True if successful, or False if value doesn't exist
        """
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
