import re
import json
from datetime import datetime
from typing import Any, Dict, Optional

from config.config import get_gpt_model, get_gpt_client
from core.chat_core import Chat
from core.classifier.prompt_classifier import PromptClassifier
from core.company_core import Company
from core.contexts.context_manager import ContextManager
from core.faq_core import Faq
from core.farmer_core import Farmer
from core.farmer_core_v2 import FarmerV2
from core.salesrep_core import SalesRep
from exceptions.global_exception import GlobalException

client = get_gpt_client()
gptModel = get_gpt_model()


def load_prompt(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def load_functions(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def detect_language(prompt):
    # detect language
    system_instruction_language = load_prompt("prompts/language_detector.txt")
    functions_language = load_functions("prompts/language_detector.json")

    messages = [
        {"role": "system", "content": system_instruction_language},
        {"role": "user", "content": prompt}
    ]

    language = call_openai(messages, functions_language, "detect_language")

    return language.get("user_language")


def call_openai(messages, functions, function_name):

    response = client.chat.completions.create(
        model=gptModel,
        messages=messages,
        functions=[functions],
        function_call={"name": function_name}
    )

    # Extract the function call arguments as JSON
    arguments = response.choices[0].message.function_call.arguments

    return json.loads(arguments)


def extract_json(text):
    match = re.search(r"```json\s*(\{.*?\})\s*```",
                      text.strip(), re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("No JSON block found in the response.")
    cleaned = match.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON response: {cleaned}")


def store_message_faq(chat_id, prompt, response, category, user_company_id=None, metadata=None):
    chat = Chat()
    faq = Faq()
    chat.add_message(chat_id, "user", prompt, metadata)
    chat.add_message(chat_id, "model", response, metadata)
    faq.insert_faq(prompt, response, category, user_company_id)


def handle_log(
    chat_id,
    user_id,
    prompt,
    prompt_file,
    form_key,
    function_name,
    on_complete,
    context_types: Optional[list] = None
):

    chat = Chat()
    farmer = FarmerV2()
    company = Company()

    # Check if user has active feed program first
    try:
        active_program = farmer.get_active_feed_program(user_id)
        has_active_program = True
    except GlobalException:
        has_active_program = False
        # Return graceful response if no active program
        return handle_no_active_program_response(prompt, form_key)

    # Get user company
    user_company_id = company.get_user_company(user_id)
    today = datetime.today().strftime("%Y/%m/%d")

    # Initialize context system
    context_manager = ContextManager()
    classifier = PromptClassifier(context_manager)

    convo_res = chat.get_conversations_record(chat_id)
    form_data = convo_res.get("form_data") or {}

    chat_history = chat.get_recent_messages(chat_id, get_max_messages())

    if context_types:
        classification_result = classifier.get_specific_contexts(
            user_id, context_types
        )

    # Load system instruction for ai and also the function that will be used by ai to populate form
    system_instruction = load_prompt(f"{prompt_file}.txt")
    functions = load_functions(f"{prompt_file}.json")

    # Build comprehensive context for logging
    logging_context = build_logging_context(
        classification_result,
        form_data,
        today
    )

    # Build user message with intelligent context
    user_message = f"{prompt}\n\n{logging_context}"

    chat_history.append({
        "role": "user",
        "content": user_message
    })

    detected_language = detect_language(prompt)
    chat_history.append({
        "role": "system",
        "content": f"Always answer in {detected_language}.\n{system_instruction}"
    })

    messages = chat_history
    parsed = call_openai(messages, functions, function_name)

    # Handle form data updates
    if form_key != "":
        new_fields = parsed.get(form_key, {})
        form_data.update({k: v for k, v in new_fields.items() if v})
        chat.update_conversation(chat_id, form_data=form_data)

        if parsed["next_action"] == "log_complete":
            success = on_complete(
                farmer, user_id, user_company_id, form_data, parsed)
            if success:
                chat.update_conversation(chat_id, None)

    store_message_faq(chat_id, prompt, parsed["response"], parsed["log_type"], user_company_id,
                      metadata={"form_data": form_data, "next_action": parsed["next_action"], "feed_program_id": active_program.get("id") if has_active_program else None})

    return parsed


def build_logging_context(
    classification_result: Dict[str, Any],
    form_data: Dict[str, Any],
    today: str,
) -> str:
    """Build comprehensive context for logging operations"""

    context_parts = [f"Today's date: {today}"]

    if classification_result.get("needs_context"):
        context_parts.append(classification_result["context_string"])

    # Add previously collected information
    form_summary = "\n".join([
        f"{k.replace('_', ' ').capitalize()}: {v}"
        for k, v in form_data.items() if v
    ]) or "None yet"

    context_parts.append(f"Previously collected info:\n{form_summary}")

    return "\n\n".join(context_parts)

def handle_intent(prompt, prompt_file, function_name):
    system_instruction = load_prompt(f"{prompt_file}.txt")
    functions = load_functions(f"{prompt_file}.json")
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
    ]
    parsed = call_openai(messages, functions, function_name)
    return parsed


def get_max_messages():
    return 10


def get_feed_program_context(farmer: FarmerV2, user_id: int) -> str:
    """Get feed program context for AI responses"""
    try:
        feed_product = farmer.get_active_feed_product(user_id)
        if feed_product:
            return f"""
          Active Feed Program Context:
            Feed: {feed_product['feed_name']}
            Stage: {feed_product['feed_stage']}
            Days on Feed: {feed_product['days_on_feed']}
            Goal: {feed_product['feed_goal']}
            Age Range: {feed_product['age_range_start']}-{feed_product['age_range_end']} days
            """
        else:
            return "No active feed program. User needs to start a feed program first."
    except Exception:
        return "No active feed program. User needs to start a feed program first."


def handle_no_active_program_response(prompt: str, form_key: str) -> dict:
    """Handle responses when user has no active feed program"""

    # Detect language from prompt (simple detection)
    is_filipino = any(word in prompt.lower() for word in [
        'ang', 'ng', 'sa', 'po', 'kasi', 'dahil', 'para', 'mga', 'ako', 'mo', 'ko'
    ])

    if is_filipino:
        if "incident_details" in form_key:
            message = "Para ma-log ang health incident, kailangan mo munang mag-start ng feed program. Gusto mo bang magsimula ng bagong program?"
        elif "report_details" in form_key:
            message = "Para ma-track ang performance, kailangan mo munang mag-start ng feed program. Gusto mo bang magsimula ng bagong program?"
        else:
            message = "Kailangan mo munang mag-start ng feed program para magamit ang feature na ito. Gusto mo bang magsimula ng bagong program?"
    else:
        if "incident_details" in form_key:
            message = "To log health incidents, you need to start a feed program first. Would you like to start a new program?"
        elif "report_details" in form_key:
            message = "To track performance, you need to start a feed program first. Would you like to start a new program?"
        else:
            message = "You need to start a feed program first to use this feature. Would you like to start a new program?"

    return {
        "response": message,
        "log_type": "no_active_program",
        "next_action": "suggest_start_program"
    }
