from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

class ContextType(Enum):
    FEED_PROGRAM = "feed_program"
    PERFORMANCE_DATA = "performance_data"
    INCIDENT_DATA = "health_data"
    # FARM_PROFILE = "farm_profile"

@dataclass
class ContextData:
    """Standard context data structure"""
    context_type: ContextType
    data: Dict[str, Any]
    relevance_score: float = 1.0
    metadata: Optional[Dict[str, Any]] = None

class ContextProvider(ABC):
    """Abstract base class for context providers"""
    
    @abstractmethod
    def get_context(self, user_id: int, **kwargs) -> Optional[ContextData]:
        """Get context data for a specific user"""
        pass
    
    @abstractmethod
    def is_relevant(self, prompt: str, **kwargs) -> float:
        """Return relevance score (0.0-1.0) for this context given the prompt"""
        pass
    
    @abstractmethod
    def get_context_type(self) -> ContextType:
        """Return the type of context this provider handles"""
        pass

