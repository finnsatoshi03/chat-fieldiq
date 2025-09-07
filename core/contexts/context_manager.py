from typing import Dict, List
from core.contexts.context_provider import ContextData, ContextProvider, ContextType
from core.contexts.feed_program_context_provider import FeedProgramContextProvider


class ContextManager:
    """Manages multiple context providers and determines which contexts to use"""

    def __init__(self):
        self.providers: Dict[ContextType, ContextProvider] = {}
        self.relevance_threshold = 0.3  # Minimum relevance score to include context

        # Register providers
        self.register_provider(FeedProgramContextProvider())

    def register_provider(self, provider: ContextProvider):
        """Register a new context provider"""
        self.providers[provider.get_context_type()] = provider

    def get_relevant_contexts(self, user_id: int, prompt: str, chat_history: List[Dict] = None,
                              max_contexts: int = 3) -> List[ContextData]:
        """Get relevant contexts based on the prompt and conversation history"""
        relevant_contexts = []

        for provider in self.providers.values():
            try:
                # Calculate relevance score
                relevance = provider.is_relevant(
                    prompt, chat_history=chat_history)

                # Include context if above threshold
                if relevance >= self.relevance_threshold:
                    context = provider.get_context(user_id)
                    if context:
                        context.relevance_score = relevance
                        relevant_contexts.append(context)
            except Exception as e:
                print(
                    f"Error getting context from {provider.get_context_type()}: {e}")

        # Sort by relevance and return top contexts
        relevant_contexts.sort(key=lambda x: x.relevance_score, reverse=True)
        return relevant_contexts[:max_contexts]

    def format_contexts_for_prompt(self, contexts: List[ContextData]) -> str:
        """Format multiple contexts into a single context string for the AI"""
        if not contexts:
            return ""

        formatted_parts = ["=== RELEVANT CONTEXT ==="]

        for context in contexts:
            context_section = [
                f"\n--- {context.context_type.value.upper()} CONTEXT ---",
                context.data.get("formatted_context",
                                 "No formatted context available")
            ]
            formatted_parts.extend(context_section)

        formatted_parts.append("\n=== END CONTEXT ===")
        return "\n".join(formatted_parts)
