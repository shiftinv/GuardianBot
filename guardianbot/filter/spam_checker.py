import itertools
import re
import disnake
import logging
from pydantic import Field
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from .. import utils
from ._base import ManualBaseChecker, CheckResult


logger = logging.getLogger(__name__)


class Config(utils.StrictModel):
    interval_sec: int = 15
    repeat_count: int = Field(2, gt=0)


class SpamChecker(ManualBaseChecker):
    def __init__(self, config: Config):
        super().__init__('blocklist_spam.json')
        self.config = config

        # (author ID, message content) -> list of messages
        self.history: Dict[Tuple[int, str], List[disnake.PartialMessage]] = defaultdict(list)
        self.__last_clear = utils.utcnow()

    async def check_match(self, msg: disnake.Message) -> Optional[CheckResult]:
        now = msg.created_at
        min_spam_time = now - timedelta(seconds=self.config.interval_sec)

        if self.__last_clear < now - timedelta(seconds=5):
            dropped = 0

            for k, hist in list(self.history.items()):
                new_hist = list(self.__clean_history(hist, min_spam_time))
                if len(new_hist) == 0:
                    # if new history empty, drop the entire thing
                    self.history.pop(k)
                    dropped += len(hist)
                elif len(new_hist) != len(hist):
                    # if new history changed, overwrite old one
                    self.history[k] = new_hist
                    assert len(new_hist) < len(hist)
                    dropped += len(hist) - len(new_hist)

            if dropped:
                logger.debug(f'cleaned {dropped} history entries')
            self.__last_clear = now

        for r in self:
            if match := re.search(r, msg.content, re.MULTILINE):
                created = msg.created_at

                hist = self.history[(msg.author.id, msg.content)]
                logger.debug(
                    f'detected potential spam by {str(msg.author)}/{msg.author.id}: \'{msg.content}\''
                    f' (previous times: {[m.created_at.replace(microsecond=0).isoformat() for m in hist]})'
                )

                # store partial message for deletion later
                hist.append(msg.channel.get_partial_message(msg.id))

                # drop older history entries
                before = len(hist)
                hist[:] = self.__clean_history(hist, min_spam_time)
                logger.debug(f'dropped {before - len(hist)} matching history entries')

                if len(hist) >= self.config.repeat_count:
                    diff = (created - hist[0].created_at).seconds
                    logger.debug(f'{self.config.repeat_count} messages within {diff} seconds')
                    return CheckResult(f'detected spam: `{match.group()}` (regex: `{r}`)', messages=hist[::-1])

                break  # don't continue searching since spam detection is based on message content, not the specific regex that matched
        return None

    @staticmethod
    def __clean_history(history: List[disnake.PartialMessage], min_time: datetime) -> Iterable[disnake.PartialMessage]:
        return itertools.dropwhile(lambda m: m.created_at < min_time, history)
