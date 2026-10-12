import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Set

from agent_mesh.domain.models import Message
from agent_mesh.resilience.exceptions import InfiniteLoopDetectedError, MaxHopsExceededError

logger = logging.getLogger(__name__)


class LoopBreaker:
    """
    Tracks message lineage hashes and enforces maximum recursion/hop limits
    to detect and prevent infinite loops in AI agent swarms.
    """

    def __init__(self, max_hops: int = 50, enable_content_hash: bool = True) -> None:
        self.max_hops = max_hops
        self.enable_content_hash = enable_content_hash

    def compute_lineage_hash(self, message: Message, history: Optional[List[str]] = None) -> str:
        """
        Computes a deterministic hash representing the lineage of a message,
        incorporating its content and its path/history through agents.
        """
        history_str = json.dumps(history or [], sort_keys=True)
        content_str = ""
        if self.enable_content_hash and message.payload:
            try:
                content_str = json.dumps(message.payload, sort_keys=True)
            except (TypeError, ValueError):
                content_str = str(message.payload)

        raw_data = f"{message.sender}:{message.receiver}:{content_str}:{history_str}"
        return hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    def check_loop(self, message: Message, lineage_history: Optional[List[str]] = None) -> None:
        """
        Inspects the message and its lineage history. Raises MaxHopsExceededError
        if the hop limit is reached, or InfiniteLoopDetectedError if a cycle is detected.
        """
        history = list(lineage_history) if lineage_history else []

        if len(history) >= self.max_hops:
            logger.warning(
                f"Max hops exceeded for message {message.id}: {len(history)} >= {self.max_hops}"
            )
            raise MaxHopsExceededError(
                f"Message exceeded maximum allowed hops of {self.max_hops}. Path: {history}"
            )

        current_hash = self.compute_lineage_hash(message, history)

        if current_hash in history:
            logger.error(
                f"Infinite loop detected for message {message.id} with lineage hash {current_hash}"
            )
            raise InfiniteLoopDetectedError(
                f"Infinite loop detected. Lineage hash {current_hash} already exists in message history."
            )

    def append_lineage(self, message: Message, lineage_history: Optional[List[str]] = None) -> List[str]:
        """
        Appends the current message state to the lineage history and returns the updated history.
        Performs loop check before appending.
        """
        history = list(lineage_history) if lineage_history else []
        self.check_loop(message, history)
        
        current_hash = self.compute_lineage_hash(message, history)
        history.append(current_hash)
        return history
