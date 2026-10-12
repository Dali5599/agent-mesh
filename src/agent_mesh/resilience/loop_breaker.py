from typing import Any, Dict, List, Optional
import logging
from typing import Dict, List, Set, Optional
from agent_mesh.resilience.exceptions import LoopDetectedError, InfiniteLoopDetectedError, MaxHopsExceededError

logger = logging.getLogger(__name__)

class LoopBreaker:
    def __init__(self, max_hops: int = 50, max_depth: Optional[int] = None, enable_content_hash: bool = True):
        self.max_depth = max_depth if max_depth is not None else max_hops
        self.history: Dict[str, List[str]] = {}

    def track_call(self, trace_id: str, caller: str, callee: str) -> None:
        if trace_id not in self.history:
            self.history[trace_id] = [caller]
        self.history[trace_id].append(callee)

    def check_loop(self, trace_id_or_msg: Any, caller: Optional[str] = None, callee: Optional[str] = None) -> bool:
        if caller is not None and callee is not None:
            trace_id = str(trace_id_or_msg)
            chain = self.history.get(trace_id, [])
            if len(chain) > self.max_depth:
                return True
            if callee in chain:
                return True
            return False
        return False

    def validate_call(self, trace_id: str, caller: str, callee: str) -> None:
        chain = self.history.get(trace_id, [])
        if len(chain) >= self.max_depth or callee in chain:
            raise LoopDetectedError(f"Loop or max depth exceeded for {caller} -> {callee}")
        self.track_call(trace_id, caller, callee)
