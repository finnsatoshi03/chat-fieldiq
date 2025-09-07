from core.chat_core import Chat
from core.classifier.prompt_classifier import PromptClassifier
from core.company_core import Company
from core.contexts.context_manager import ContextManager
from core.contexts.context_provider import ContextType
from core.farmer_core_v2 import FarmerV2, create_health_incident_with_program, create_performance_log_with_program
from core.helper_core_v2 import call_openai, get_feed_program_context, get_max_messages, handle_intent, handle_log, load_functions, load_prompt, store_message_faq, detect_language


max = get_max_messages()

# intent 1 ito
def handle_general_questions(chat_id, user_id, prompt):
    chat = Chat()
    company = Company()

    user_company_id = company.get_user_company(user_id)

    context_manager = ContextManager()
    classifier = PromptClassifier(context_manager)

    history = chat.get_recent_messages(chat_id, max_messages=max)

    classification_result = classifier.classify_and_get_context(
        user_id, prompt, history
    )

    system_instruction = load_prompt(
        f"prompts/{classification_result['system_prompt_key']}")
    functions = load_functions(
        f"prompts/{classification_result['system_prompt_key'].replace('.txt', '.json')}")

    user_message = prompt
    if classification_result["needs_context"]:
        user_message = f"{prompt}\n\n{classification_result['context_string']}"

    history.append({
        "role": "user",
        "content": user_message
    })
    
    detected_language = detect_language(prompt)
    history.append({
        "role": "system", 
        "content": f"Always answer in {detected_language}.\n" + system_instruction
    })

    messages = history
    parsed = call_openai(messages, functions, "feed_advisory")

    store_message_faq(
        chat_id, prompt, parsed["response"], parsed["log_type"], user_company_id)
    return parsed

# intent 2 ito
def handle_health_log(chat_id, user_id, prompt):
    return handle_log(
        chat_id, 
        user_id, 
        prompt, 
        "prompts/ask_farmer_health_log", 
        "incident_details",
        "log_health_incident",
        create_health_incident_with_program,
        context_types=[ContextType.FEED_PROGRAM])

# intent 3 ito
def handle_performance_log(chat_id, user_id, prompt):
    return handle_log(
        chat_id,
        user_id,
        prompt,
        "prompts/ask_farmer_log",
        "report_details",
        "log_performance_report",
        create_performance_log_with_program,
        context_types=[ContextType.FEED_PROGRAM])

# intent 4 ito
def handle_local_practice_log(chat_id, user_id, prompt):
    return handle_log(
        chat_id,
        user_id,
        prompt,
        "prompts/ask_farmer_diy_log",
        "diy",
        "log_diy_practice",
        create_health_incident_with_program)


def get_intent(prompt, prompt_file, function_name):
    return handle_intent(prompt, prompt_file, function_name)
