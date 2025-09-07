from typing import Any, Dict, List
from core.contexts.context_provider import ContextData, ContextType
from core.contexts.context_manager import ContextManager


class PromptClassifier:
    """Prompt classification with context awareness"""

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager

    def classify_and_get_context(self, user_id: int, prompt: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """Classify prompt and get appropriate context"""

        # Get relevant contexts
        relevant_contexts = self.context_manager.get_relevant_contexts(
            user_id, prompt, chat_history
        )

        # Determine if any context is needed
        needs_context = len(relevant_contexts) > 0

        # Format context string
        context_string = ""
        if needs_context:
            context_string = self.context_manager.format_contexts_for_prompt(
                relevant_contexts)

        # Determine prompt category
        prompt_category = self._categorize_prompt(prompt, relevant_contexts)

        return {
            "needs_context": needs_context,
            "context_string": context_string,
            "relevant_contexts": relevant_contexts,
            "prompt_category": prompt_category,
            "system_prompt_key": self._get_system_prompt_key(prompt_category, needs_context),
            "function_name": self._get_function_name(prompt_category, needs_context)
        }

    def get_specific_contexts(
        self,
        user_id: int,
        context_types: list
    ) -> Dict[str, Any]:

        relevant_contexts = []

        for context_type in context_types:
            if context_type in self.context_manager.providers:
                provider = self.context_manager.providers[context_type]
                context = provider.get_context(user_id)
                if context:
                    context.relevance_score = 1.0
                    relevant_contexts.append(context)

        context_string = ""
        if relevant_contexts:
            context_string = self.context_manager.format_contexts_for_prompt(
                relevant_contexts)

        return {
            "needs_context": len(relevant_contexts) > 0,
            "context_string": context_string,
            "relevant_contexts": relevant_contexts
        }

    def _categorize_prompt(self, prompt: str, contexts: List[ContextData]) -> str:
        """Categorize the type of prompt"""
        if not contexts:
            return "general"

        primary_context = contexts[0].context_type

        if primary_context == ContextType.FEED_PROGRAM:
            return "feed_related"
        elif primary_context == ContextType.INCIDENT:
            return "incident_related"
        elif primary_context == ContextType.PERFORMANCE:
            return "performance_related"
        else:
            return "general_with_context"

    def _get_system_prompt_key(self, category: str, needs_context: bool) -> str:
        """Get the appropriate system prompt key"""

        # Good to have yung system prompt specific kapag need ng context.
        if category == "feed_related":
            return "ask_farmer_general_prompts.txt"
        elif category == "incident_related":
            return "ask_farmer_health_log.txt"
        elif category == "performance_related":
            return "ask_farmer_log.txt"
        elif needs_context:
            return "ask_farmer_general_prompts.txt"
        else:
            return "ask_farmer_general_prompts.txt"

    def _get_function_name(self, category: str, needs_context: bool) -> str:
        """Get the appropriate function name for the AI call"""
        if category == "feed_related":
            return "ask_farmer_general_prompts.json"
        elif category == "incident_related":
            return "ask_farmer_health_log.json"
        elif category == "performance_related":
            return "ask_farmer_log.json"
        elif needs_context:
            return "ask_farmer_general_prompts.json"
        else:
            return "ask_farmer_general_prompts.json"
