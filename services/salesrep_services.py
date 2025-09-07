from fastapi import APIRouter, Query

from models.chat_model import ChatRequest
from core.chat_core import Chat
from core.salesrep_core import SalesRep
from llm.salesrep_llm_handler import (
  get_intent,
  handle_general_questions,
  handle_field_product_log,
  handle_dealer_log,
  handle_requested_file,
  handle_support_forms,
  handle_sales_log,
  handle_farm_log,
)


router = APIRouter()

@router.post("/chat")
def chat_service(body: ChatRequest):
  try:
    chat = Chat()

    chat_id = body.chat_id
    user_id = body.user_id
    prompt = body.prompt
    
    chat_id = chat.create_conversation(user_id)
        
    if chat_id == None:
      raise Exception("Failed to create conversation")
        
    intent_id = body.intent_id
    intent = {}
    if (intent_id == None or intent_id == 0):
      intent = get_intent(prompt, "prompts/ask_salesrep_intent", "classify_intent")    
      intent_id = intent["id"]
  
    # Early return for out of scope       
    if (intent_id == 6):        
      return {"message": "Success", "data": intent}

    dispatch = {
      1: lambda: handle_general_questions(chat_id, prompt),
      2: lambda: handle_dealer_log(chat_id, user_id, prompt),
      3: lambda: handle_field_product_log(chat_id, user_id, prompt),
      4: lambda: handle_requested_file(intent),
      5: lambda: handle_support_forms(intent),
      7: lambda: handle_sales_log(chat_id, user_id, prompt),
      8: lambda: handle_farm_log(chat_id, user_id, prompt),
      
    }

    handler = dispatch.get(intent_id)
    if handler is None:
      raise Exception("Handler for intent not found")

    return {"message": "Success", "data": handler()}    
  except Exception as e:
    print(f"An error occurred: {e}")
    return {"message": "Something went wrong", "data": None, "error": f"{e}"}

@router.get("/monthly-sales")
def get_monthly_sales(user_id: int = Query(...)):
  try:
    sales_rep = SalesRep()
    sales = sales_rep.get_monthly_sales(user_id)
    return {"message": "Success", "data": sales}
  except Exception as e:
    print(f"An error occurred: {e}")
    return {"message": "Something went wrong", "data": None}

@router.get("/sales-rep-logs")
def get_sales_rep_logs(user_id: int = Query(...)):
  try:
    sales_rep = SalesRep()
    sales = sales_rep.get_alert_incidents(user_id)
    return {"message": "Success", "data": sales}
  except Exception as e:
    print(f"An error occurred: {e}")
    return {"message": "Something went wrong", "data": None}

@router.get("/farms")
def get_farms(user_id: int = Query(...)):
  try:
    sales_rep = SalesRep()
    sales = sales_rep.get_farms(user_id)
    return {"message": "Success", "data": sales}
  except Exception as e:
    print(f"An error occurred: {e}")
    return {"message": "Something went wrong", "data": None}

@router.get("/visit-schedule")
def get_visit_schedule(user_id: int = Query(...)):
  try:
    sales_rep = SalesRep()
    sales = sales_rep.get_visits(user_id)
    return {"message": "Success", "data": sales}
  except Exception as e:
    print(f"An error occurred: {e}")
    return {"message": "Something went wrong", "data": None}


#@router.post("/request/collateral")
def request_collateral():
  return 1