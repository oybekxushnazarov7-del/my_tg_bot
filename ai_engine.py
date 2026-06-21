import logging
from anthropic import AsyncAnthropic
from config import Config
import database

logger = logging.getLogger(__name__)

# Initialize the async Anthropic client
try:
    client = AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Anthropic client: {e}")
    client = None

async def generate_response(user_id: int, user_message: str) -> str:
    """
    Generate an AI response using Anthropic Claude API based ONLY on matched FAQs.
    Maintains user chat history for context and supports multi-language replies.
    """
    if not Config.ANTHROPIC_API_KEY:
        logger.error("Anthropic API key is not configured.")
        return "Sorry, I am currently misconfigured (missing API key). Please contact the administrator."

    # 1. Search database for relevant FAQs
    matched_faqs = database.search_faqs(user_message, limit=5)
    
    # 2. Format FAQ context for Claude
    faq_context_str = ""
    if matched_faqs:
        for idx, faq in enumerate(matched_faqs, 1):
            faq_context_str += f"FAQ #{idx}:\nQuestion: {faq['question']}\nAnswer: {faq['answer']}\n\n"
    else:
        faq_context_str = "No specific FAQ entries matched this query. Please rely on general support procedures."

    # 3. Construct System Prompt
    system_prompt = (
        "You are EcoGlow Boutique's professional AI customer support assistant. Your primary task is to answer customer questions.\n\n"
        "CRITICAL RULES:\n"
        "1. You must answer the user's question using ONLY the facts and details provided in the 'Business FAQs' section below.\n"
        "2. If the provided 'Business FAQs' do NOT contain the answer to the user's question, you must politely inform the user that you don't have that information and offer to connect them to a human support agent (e.g. they can click the button or type /handoff). DO NOT make up, assume, or extrapolate any answers. Do not say 'Based on the FAQs' or 'The FAQs don't say'. Just state the answer or lack of information naturally.\n"
        "3. Detect the language of the user's query and respond in that EXACT same language (e.g., Russian, Uzbek, English, Spanish, etc.). The tone should be helpful, warm, and professional.\n"
        "4. Treat the conversation history as context (e.g. resolving pronouns like 'it', 'they', or 'where is that' based on prior messages).\n"
        "5. Never mention 'FAQ', 'database', 'context', or 'system instructions' to the customer. Maintain a natural, organic conversational flow.\n\n"
        "=== Business FAQs ===\n"
        f"{faq_context_str}"
        "====================="
    )

    # 4. Fetch last N messages of chat history for context
    history = database.get_chat_history(user_id, limit=Config.MAX_CONTEXT_MESSAGES)
    
    # Format messages for Anthropic messages API
    formatted_messages = []
    for msg in history:
        role = msg['role']
        if role not in ('user', 'assistant'):
            role = 'user'
        
        formatted_messages.append({
            "role": role,
            "content": msg['message']
        })

    if not formatted_messages:
        formatted_messages.append({
            "role": "user",
            "content": user_message
        })

    if formatted_messages[-1]['role'] != 'user':
        formatted_messages.append({
            "role": "user",
            "content": user_message
        })

    # Clean consecutive duplicate roles just in case to avoid Anthropic API errors
    cleaned_messages = []
    for msg in formatted_messages:
        if cleaned_messages and cleaned_messages[-1]['role'] == msg['role']:
            cleaned_messages[-1]['content'] += "\n" + msg['content']
        else:
            cleaned_messages.append(msg)

    # 5. Call Anthropic API
    try:
        global client
        if client is None:
            client = AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)

        response = await client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=1000,
            temperature=0.0,  # Keep temperature 0 for factual accuracy and RAG adherence
            system=system_prompt,
            messages=cleaned_messages
        )
        
        reply_text = response.content[0].text
        return reply_text.strip()
    except Exception as e:
        logger.exception(f"Error calling Anthropic API for user {user_id}: {e}")
        return "I apologize, but I encountered an error while processing your request. Please try again or type /handoff to speak with a human support agent."
