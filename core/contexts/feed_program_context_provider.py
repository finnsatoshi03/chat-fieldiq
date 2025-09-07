from typing import Dict, Optional
from core.contexts.context_provider import ContextData, ContextProvider, ContextType
from core.farmer_core_v2 import FarmerV2


class FeedProgramContextProvider(ContextProvider):
    """Provides feed program context"""
    
    def __init__(self):
        self.farmer = FarmerV2()
        self.feed_related_keywords = [
            'feed', 'feeding', 'nutrition', 'diet', 'program', 'stage', 
            'starter', 'grower', 'finisher', 'broiler', 'layer', 'current',
            'my farm', 'weight', 'growth', 'performance', 'supplement',
            'medication', 'schedule', 'timeline', 'day', 'week', 'age',
            'switch', 'transition', 'change feed'
        ]
    
    def get_context(self, user_id: int, **kwargs) -> Optional[ContextData]:
        """Get active feed program context"""
        try:
            feed_program = self.farmer.get_active_feed_program(user_id)
            feed_product = self.farmer.get_active_feed_product(user_id)
            
            context_data = {
                "feed_program": feed_program,
                "feed_product": feed_product,
                "formatted_context": self._format_feed_program_context(feed_program, feed_product)
            }
            
            return ContextData(
                context_type=ContextType.FEED_PROGRAM,
                data=context_data,
                relevance_score=1.0,
                metadata={
                    "days_on_feed": feed_program.get("days_on_feed", 0),
                    "feed_stage": feed_product.get("feed_stage") if feed_product else None
                }
            )
        except Exception as e:
            print(f"Error getting feed program context: {e}")
            return None
    
    def is_relevant(self, prompt: str, **kwargs) -> float:
        """Calculate relevance score based on keywords"""
        prompt_lower = prompt.lower()
        matches = sum(1 for keyword in self.feed_related_keywords if keyword in prompt_lower)
        
        # Higher score for more matches, capped at 1.0
        relevance = min(matches * 0.2, 1.0)
        
        # Boost score for direct feed program references
        if any(phrase in prompt_lower for phrase in ['current feed', 'my program', 'feed program']):
            relevance = min(relevance + 0.3, 1.0)
            
        return relevance
    
    def get_context_type(self) -> ContextType:
        return ContextType.FEED_PROGRAM
    
    def _format_feed_program_context(self, feed_program: Dict, feed_product: Dict) -> str:
        """Format feed program data into readable context"""
        if not feed_program or not feed_product:
            return ""
            
        context_parts = [
            f"Current Feed Program: {feed_product.get('feed_name', 'Unknown')}",
            f"Feed Stage: {feed_product.get('feed_stage', 'Unknown')}",
            f"Days on Feed: {feed_program.get('days_on_feed', 0)}",
            f"Animal Quantity: {feed_program.get('animal_quantity', 0)}",
            f"Feed Goal: {feed_product.get('feed_goal', 'Unknown')}"
        ]
        
        return "\n".join(context_parts)
