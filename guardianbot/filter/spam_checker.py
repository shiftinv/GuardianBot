import itertools
import re
import disnake
import logging
from datetime import timedelta
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ._base import ManualBaseChecker, CheckResult


logger = logging.getLogger(__name__)


@dataclass
class Config:
    interval_sec: int = 15
    repeat_count: int = 2  # TODO: limit range


class SpamChecker(ManualBaseChecker):
    def __init__(self, config: Config):
        super().__init__('blocklist_spam.json')
        self.config = config

        # (author ID, message content) -> list of messages
        self.history: Dict[Tuple[int, str], List[disnake.PartialMessage]] = defaultdict(list)

    async def check_match(self, msg: disnake.Message) -> Optional[CheckResult]:
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
                hist[:] = itertools.dropwhile(
                    lambda m: m.created_at < created - timedelta(seconds=self.config.interval_sec),
                    hist
                )
                logger.debug(f'dropped {before - len(hist)} history entries')

                if len(hist) >= self.config.repeat_count:
                    diff = (created - hist[0].created_at).seconds
                    logger.debug(f'{self.config.repeat_count} messages within {diff} seconds')
                    return CheckResult(f'detected spam: `{match.group()}` (regex: `{r}`)', messages=hist)

                break  # don't continue searching since spam detection is based on message content, not the specific regex that matched
        return None
