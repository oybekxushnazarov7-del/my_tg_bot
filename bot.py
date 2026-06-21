import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from config import Config
import database
import ai_engine

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def is_admin(user_id: int) -> bool:
    """Check if the user ID is in the admin list."""
    return user_id in Config.ADMIN_IDS

async def notify_admins(application: Application, text: str, reply_markup: InlineKeyboardMarkup = None):
    """Send a notification message to all configured admins."""
    for admin_id in Config.ADMIN_IDS:
        try:
            await application.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# --- Menu Builders ---

def get_main_keyboard():
    """Build the main menu inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("📖 View Common FAQs", callback_data="user_faq_menu")],
        [InlineKeyboardButton("🙋‍♂️ Talk to Human Operator", callback_data="user_request_handoff")],
        [InlineKeyboardButton("ℹ️ About EcoGlow", callback_data="user_about")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_main_keyboard():
    """Build a keyboard with just a back button."""
    keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="user_main_menu")]]
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or "there"
    
    database.log_usage(user_id, "start_command")
    
    # Save command to chat history
    database.save_chat_message(user_id, "user", "/start")
    
    welcome_text = (
        f"Hello, {first_name}! Welcome to **EcoGlow Boutique** Support Bot 🌿✨\n\n"
        "I am your AI assistant. You can ask me anything about our organic skincare products, "
        "store hours, shipping, returns, or order tracking by simply typing your question directly.\n\n"
        "Alternatively, you can use the quick menu below to explore:"
    )
    
    # Save bot welcome to history
    database.save_chat_message(user_id, "assistant", welcome_text)
    
    await update.message.reply_text(
        text=welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

async def handoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /handoff command."""
    user = update.effective_user
    user_id = user.id
    username = user.username or "NoUsername"
    first_name = user.first_name or "User"
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    database.log_usage(user_id, "handoff_command")
    database.save_chat_message(user_id, "user", "/handoff")
    
    # Check if user is already in handoff
    if database.is_user_in_handoff(user_id):
        reply_text = "You have already requested a human operator. A support manager will contact you in this chat shortly."
        database.save_chat_message(user_id, "assistant", reply_text)
        await update.message.reply_text(reply_text)
        return

    # Log handoff request
    success = database.create_handoff_request(user_id, username, first_name)
    if success:
        user_reply = (
            "🙋‍♂️ **Support Request Submitted**\n\n"
            "Your request for a live operator has been sent. A support manager will reply directly "
            "to you in this chat shortly. Any message you type now will be forwarded to them."
        )
        database.save_chat_message(user_id, "assistant", user_reply)
        await update.message.reply_text(user_reply, parse_mode="Markdown")
        
        # Get last 3 history messages for admin context
        history = database.get_chat_history(user_id, limit=4)
        history_str = ""
        for h in history[:-1]:  # exclude the /handoff command itself
            role_label = "👤 User" if h['role'] == 'user' else "🤖 Bot"
            history_str += f"{role_label}: {h['message']}\n"
            
        if not history_str:
            history_str = "(No prior messages in database)"
            
        admin_text = (
            "⚠️ **NEW LIVE SUPPORT REQUEST**\n\n"
            f"👤 **Customer**: {full_name}\n"
            f"ID: `{user_id}`\n"
            f"Username: @{username}\n\n"
            f"📋 **Recent Chat History**:\n{history_str}\n"
            f"To reply, use: `/reply {user_id} <your message>`"
        )
        
        # Add quick resolve button for admin
        keyboard = [[InlineKeyboardButton("✅ Resolve Request", callback_data=f"admin_resolve_{user_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await notify_admins(context.application, admin_text, reply_markup=reply_markup)
    else:
        error_text = "Sorry, we could not process your handoff request right now. Please try again later."
        await update.message.reply_text(error_text)

# --- Admin Command Handlers ---

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /admin command - displays admin dashboard."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access Denied. This command is restricted to administrators.")
        return
        
    database.log_usage(user_id, "admin_command")
    
    admin_menu_text = (
        "🛠️ **EcoGlow Admin Dashboard**\n\n"
        "Available Admin Commands:\n"
        "🔹 `/admin` - View this dashboard\n"
        "🔹 `/faq_list` - View all FAQ entries\n"
        "🔹 `/faq_add <question> | <answer>` - Add a new FAQ\n"
        "🔹 `/faq_del <id>` - Delete an FAQ entry\n"
        "🔹 `/stats` - View bot usage statistics\n"
        "🔹 `/pending_handoffs` - View pending support requests\n"
        "🔹 `/resolve <user_id>` - Resolve a support request\n"
        "🔹 `/reply <user_id> <message>` - Reply to a customer"
    )
    
    await update.message.reply_text(admin_menu_text, parse_mode="Markdown")

async def faq_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /faq_list command."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    faqs = database.list_faqs()
    if not faqs:
        await update.message.reply_text("No FAQ entries found in the database. Use `/faq_add` to add some.")
        return

    text = "📖 **FAQ Entries List**:\n\n"
    for faq in faqs:
        text += f"🆔 **ID**: {faq['id']}\n❓ **Q**: {faq['question']}\n💡 **A**: {faq['answer']}\n-------------------\n"
        
    # Split text into chunks if it is too long (Telegram limit is 4096 characters)
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode="Markdown")

async def faq_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /faq_add <question> | <answer>."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    raw_args = " ".join(context.args)
    if "|" not in raw_args:
        await update.message.reply_text(
            "❌ Invalid format. Use:\n`/faq_add <question> | <answer>`\n\nExample:\n`/faq_add Do you ship to Canada? | Yes, shipping to Canada takes 5-7 days.`",
            parse_mode="Markdown"
        )
        return

    parts = raw_args.split("|", 1)
    question = parts[0].strip()
    answer = parts[1].strip()

    if not question or not answer:
        await update.message.reply_text("❌ Question and Answer cannot be empty.")
        return

    faq_id = database.add_faq(question, answer)
    await update.message.reply_text(f"✅ FAQ entry successfully added with **ID: {faq_id}**.", parse_mode="Markdown")

async def faq_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /faq_del <id>."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please specify the FAQ ID. Example: `/faq_del 5`")
        return

    try:
        faq_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. The FAQ ID must be an integer.")
        return

    success = database.delete_faq(faq_id)
    if success:
        await update.message.reply_text(f"✅ FAQ entry with ID {faq_id} has been deleted.")
    else:
        await update.message.reply_text(f"❌ FAQ entry with ID {faq_id} not found.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /stats command."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    stats = database.get_stats()
    
    actions_str = ""
    for action, count in stats.get('actions_breakdown', {}).items():
        actions_str += f" - {action}: {count}\n"
    
    text = (
        "📈 **EcoGlow Bot Statistics**\n\n"
        f"🔹 **Total FAQs in DB**: {stats['total_faqs']}\n"
        f"🔹 **Unique Active Users**: {stats['unique_users']}\n"
        f"🔹 **Total Messages Processed**: {stats['total_user_messages']}\n"
        f"🔹 **Handoff Requests (All-Time)**: {stats['total_handoff_requests_all_time']}\n"
        f"🔹 **Pending Handoff Requests**: {stats['pending_handoff_requests']}\n"
        f"🔹 **Total System Actions**: {stats['total_actions']}\n\n"
        f"📋 **Actions Breakdown**:\n{actions_str or ' - None'}"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def pending_handoffs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /pending_handoffs command."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    pending = database.get_pending_handoffs()
    if not pending:
        await update.message.reply_text("✅ There are no pending handoff requests at the moment.")
        return

    text = "📋 **Pending Handoff Requests**:\n\n"
    for idx, p in enumerate(pending, 1):
        username_part = f" (@{p['username']})" if p['username'] else ""
        text += f"{idx}. **User**: {p['first_name']}{username_part}\n   🆔 **ID**: `{p['user_id']}`\n   📅 **Requested**: {p['created_at']}\n   Resolve command: `/resolve {p['user_id']}`\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def resolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /resolve <user_id> command."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please specify the User ID. Example: `/resolve 12345678`")
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. The User ID must be an integer.")
        return

    success = database.resolve_handoff(target_user_id)
    if success:
        # Notify user
        try:
            user_msg = (
                "✅ **Support Session Resolved**\n\n"
                "The live support session has ended. You have been switched back to the AI assistant. "
                "You can continue asking questions and I will reply automatically!"
            )
            await context.application.bot.send_message(chat_id=target_user_id, text=user_msg, parse_mode="Markdown")
            database.save_chat_message(target_user_id, "assistant", user_msg)
        except Exception as e:
            logger.error(f"Could not notify user {target_user_id} about resolution: {e}")

        await update.message.reply_text(f"✅ Handoff request for user `{target_user_id}` has been resolved.", parse_mode="Markdown")
        database.log_usage(user_id, f"resolved_handoff_{target_user_id}")
    else:
        await update.message.reply_text(f"❌ No pending handoff request found for user `{target_user_id}`.", parse_mode="Markdown")

async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /reply <user_id> <message> command."""
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Invalid format. Use:\n`/reply <user_id> <message>`\n\nExample:\n`/reply 12345678 Hello! We are open until 7 PM today.`",
            parse_mode="Markdown"
        )
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. The User ID must be an integer.")
        return

    reply_text = " ".join(context.args[1:])
    
    # Send message to user
    try:
        formatted_user_msg = f"💬 **Support Operator:** {reply_text}"
        await context.application.bot.send_message(
            chat_id=target_user_id,
            text=formatted_user_msg,
            parse_mode="Markdown"
        )
        
        # Save to user chat history
        database.save_chat_message(target_user_id, "assistant", formatted_user_msg)
        database.log_usage(admin_id, f"sent_reply_to_{target_user_id}")
        
        await update.message.reply_text(f"✅ Message successfully sent to user `{target_user_id}`.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send reply to user {target_user_id}: {e}")
        await update.message.reply_text(f"❌ Failed to send message. Error: {e}")

# --- Text Message Handler ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages from users (either AI query or forwarded support chat)."""
    # Ignore commands (they are processed by command handlers)
    if update.message.text.startswith("/"):
        return

    user = update.effective_user
    user_id = user.id
    user_message = update.message.text
    
    # Save user message to history
    database.save_chat_message(user_id, "user", user_message)

    # 1. Check if user is currently in a pending handoff session
    if database.is_user_in_handoff(user_id):
        database.log_usage(user_id, "handoff_forward")
        
        # Forward message to all admins
        username_part = f" (@{user.username})" if user.username else ""
        forward_text = (
            f"💬 **Support Chat [{user.first_name}{username_part} | `{user_id}`]**:\n\n"
            f"{user_message}\n\n"
            f"To reply: `/reply {user_id} <message>`"
        )
        
        # Admin action buttons
        keyboard = [[InlineKeyboardButton("✅ Resolve Request", callback_data=f"admin_resolve_{user_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await notify_admins(context.application, forward_text, reply_markup=reply_markup)
        
        # Notify user that their message was sent to human support
        await update.message.reply_text(
            "⏳ Your message has been forwarded to our support team. An operator will reply to you here shortly."
        )
        return

    # 2. Regular AI response generation (RAG)
    database.log_usage(user_id, "faq_query")
    
    # Send typing status
    await context.application.bot.send_chat_action(chat_id=user_id, action="typing")
    
    # Generate RAG response
    reply_text = await ai_engine.generate_response(user_id, user_message)
    
    # Save assistant response to history
    database.save_chat_message(user_id, "assistant", reply_text)
    
    await update.message.reply_text(reply_text)

# --- Callback Query Handler (Inline Buttons) ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clicks on inline keyboard buttons."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # Acknowledge the callback query to remove loading state
    await query.answer()

    # Admin actions
    if data.startswith("admin_resolve_"):
        if not is_admin(user_id):
            await query.edit_message_text("⛔ You do not have permission to perform this action.")
            return

        target_user_id = int(data.split("admin_resolve_")[1])
        success = database.resolve_handoff(target_user_id)
        if success:
            # Notify user
            try:
                user_msg = (
                    "✅ **Support Session Resolved**\n\n"
                    "The live support session has ended. You have been switched back to the AI assistant. "
                    "You can continue asking questions and I will reply automatically!"
                )
                await context.application.bot.send_message(chat_id=target_user_id, text=user_msg, parse_mode="Markdown")
                database.save_chat_message(target_user_id, "assistant", user_msg)
            except Exception as e:
                logger.error(f"Could not notify user {target_user_id} about resolution: {e}")

            # Edit admin message
            original_text = query.message.text
            resolved_text = f"{original_text}\n\n✅ **Resolved by admin**"
            await query.edit_message_text(text=resolved_text)
            database.log_usage(user_id, f"resolved_handoff_{target_user_id}")
        else:
            await query.message.reply_text(f"❌ Failed to resolve. Handoff for user `{target_user_id}` might already be resolved.")
        return

    # User actions
    if data == "user_main_menu":
        database.log_usage(user_id, "menu_main")
        welcome_text = (
            f"Hello, {query.from_user.first_name}! Welcome to **EcoGlow Boutique** Support Bot 🌿✨\n\n"
            "I am your AI assistant. You can ask me anything about our organic skincare products, "
            "store hours, shipping, returns, or order tracking by simply typing your question directly.\n\n"
            "Alternatively, you can use the quick menu below to explore:"
        )
        try:
            await query.edit_message_text(
                text=welcome_text,
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            # Handle case where text is the same (telegram error)
            pass

    elif data == "user_faq_menu":
        database.log_usage(user_id, "menu_faqs")
        faqs = database.list_faqs()
        
        if not faqs:
            await query.edit_message_text(
                text="We are currently setting up our FAQ database. Please ask your question directly or check back later!",
                reply_markup=get_back_to_main_keyboard()
            )
            return

        # Show FAQ list as buttons (up to top 6)
        keyboard = []
        for faq in faqs[:6]:
            # Truncate question for button label
            label = faq['question']
            if len(label) > 35:
                label = label[:32] + "..."
            keyboard.append([InlineKeyboardButton(label, callback_data=f"user_faq_view_{faq['id']}")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="user_main_menu")])
        
        await query.edit_message_text(
            text="📚 **Frequently Asked Questions**\n\nClick on any question below to see the answer, or type any custom question directly in chat:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("user_faq_view_"):
        faq_id = int(data.split("user_faq_view_")[1])
        database.log_usage(user_id, f"view_faq_{faq_id}")
        faq = database.get_faq_by_id(faq_id)
        
        if not faq:
            await query.edit_message_text(
                text="Sorry, that FAQ entry could not be found.",
                reply_markup=get_back_to_main_keyboard()
            )
            return

        faq_text = f"❓ **Question**: {faq['question']}\n\n💡 **Answer**: {faq['answer']}"
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to FAQs", callback_data="user_faq_menu")],
            [InlineKeyboardButton("⬅️ Main Menu", callback_data="user_main_menu")]
        ]
        
        await query.edit_message_text(
            text=faq_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "user_request_handoff":
        # Simulate running /handoff command
        # Build a mock update structure or call handoff logic directly
        # Let's write the response inline:
        database.log_usage(user_id, "menu_handoff")
        
        if database.is_user_in_handoff(user_id):
            await query.edit_message_text(
                text="You have already requested a human operator. A support manager will contact you in this chat shortly.",
                reply_markup=get_back_to_main_keyboard()
            )
            return

        username = query.from_user.username or "NoUsername"
        first_name = query.from_user.first_name or "User"
        last_name = query.from_user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()

        success = database.create_handoff_request(user_id, username, first_name)
        if success:
            user_reply = (
                "🙋‍♂️ **Support Request Submitted**\n\n"
                "Your request for a live operator has been sent. A support manager will reply directly "
                "to you in this chat shortly. Any message you type now will be forwarded to them."
            )
            database.save_chat_message(user_id, "assistant", user_reply)
            await query.edit_message_text(
                text=user_reply,
                reply_markup=get_back_to_main_keyboard(),
                parse_mode="Markdown"
            )

            # Get history
            history = database.get_chat_history(user_id, limit=4)
            history_str = ""
            for h in history[:-1]:
                role_label = "👤 User" if h['role'] == 'user' else "🤖 Bot"
                history_str += f"{role_label}: {h['message']}\n"
                
            if not history_str:
                history_str = "(No prior messages in database)"

            admin_text = (
                "⚠️ **NEW LIVE SUPPORT REQUEST**\n\n"
                f"👤 **Customer**: {full_name}\n"
                f"ID: `{user_id}`\n"
                f"Username: @{username}\n\n"
                f"📋 **Recent Chat History**:\n{history_str}\n"
                f"To reply, use: `/reply {user_id} <your message>`"
            )
            
            keyboard = [[InlineKeyboardButton("✅ Resolve Request", callback_data=f"admin_resolve_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await notify_admins(context.application, admin_text, reply_markup=reply_markup)
        else:
            await query.edit_message_text(
                text="Sorry, we could not process your handoff request right now. Please try again later.",
                reply_markup=get_back_to_main_keyboard()
            )

    elif data == "user_about":
        database.log_usage(user_id, "menu_about")
        about_text = (
            "🌿 **About EcoGlow Boutique**\n\n"
            "EcoGlow is dedicated to providing premium, organic, and cruelty-free skincare products. "
            "We believe in clean beauty that is good for your skin and kind to the environment.\n\n"
            "🌎 All our packaging is 100% recyclable, and our ingredients are ethically sourced.\n\n"
            "Thank you for supporting sustainable beauty!"
        )
        await query.edit_message_text(
            text=about_text,
            reply_markup=get_back_to_main_keyboard(),
            parse_mode="Markdown"
        )

# --- Application Startup/Shutdown ---

async def post_init(application: Application):
    """Tasks to run on bot startup."""
    # Ensure database is initialized
    database.init_db()
    
    # Notify admins that the bot is online
    startup_msg = "🚀 **EcoGlow Customer Support Bot is now ONLINE** and ready."
    await notify_admins(application, startup_msg)
    logger.info("Bot successfully started and admins notified.")

# --- Main Runner ---

def main():
    """Start the bot."""
    # Validate configuration
    config_errors = Config.validate()
    if config_errors:
        print("[ERROR] CONFIGURATION ERRORS DETECTED:")
        for err in config_errors:
            print(f" - {err}")
        print("\nPlease fix these errors in your .env file before running the bot.")
        sys.exit(1)

    # Start health check server for cloud hosting (Render Free Tier)
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, format, *args):
            return

    try:
        port = int(os.getenv("PORT", "8080"))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health check server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start health check server: {e}")

    print("Starting EcoGlow Telegram Bot...")
    
    # Build the Application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # User Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("handoff", handoff_command))

    # Admin Commands
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("faq_list", faq_list_command))
    application.add_handler(CommandHandler("faq_add", faq_add_command))
    application.add_handler(CommandHandler("faq_del", faq_del_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("pending_handoffs", pending_handoffs_command))
    application.add_handler(CommandHandler("resolve", resolve_command))
    application.add_handler(CommandHandler("reply", reply_command))

    # Callback Query (button clicks) Handler
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Message Handler (for text messages)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
