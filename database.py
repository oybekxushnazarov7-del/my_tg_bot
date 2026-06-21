import sqlite3
import datetime
from config import Config

def get_connection():
    """Establish a connection to the SQLite database."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionary-like objects
    return conn

def init_db():
    """Initialize the database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table for FAQs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    """)

    # Table for Chat History (context memory)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL, -- 'user' or 'assistant'
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for Handoff Requests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            status TEXT NOT NULL DEFAULT 'pending', -- 'pending' or 'resolved'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for Usage Stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL, -- e.g., 'start_command', 'faq_query', 'handoff_request'
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# --- FAQ Operations ---

def add_faq(question: str, answer: str) -> int:
    """Add a new FAQ entry and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO faqs (question, answer) VALUES (?, ?)",
        (question.strip(), answer.strip())
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_faq_by_id(faq_id: int):
    """Retrieve an FAQ entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def list_faqs():
    """Retrieve all FAQ entries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faqs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_faq(faq_id: int) -> bool:
    """Delete an FAQ entry by ID. Returns True if deleted, False otherwise."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    conn.commit()
    changes = conn.total_changes
    conn.close()
    return changes > 0

def search_faqs(query: str, limit: int = 5):
    """
    Search FAQs based on simple keyword matching.
    Splits the query into words and scores each FAQ based on how many
    words match the question and answer (giving higher weight to question matches).
    Returns a list of matching FAQ rows sorted by score descending.
    """
    query_words = [w.lower() for w in query.strip().split() if len(w) > 1]
    if not query_words:
        # If query is too short or empty, return recent FAQs
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faqs LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, answer FROM faqs")
    all_faqs = cursor.fetchall()
    conn.close()

    scored_faqs = []
    for faq in all_faqs:
        q_lower = faq['question'].lower()
        a_lower = faq['answer'].lower()
        
        score = 0
        for word in query_words:
            # Check question matches (higher weight)
            if word in q_lower:
                score += 3
                # Exact word matching bonus
                if f" {word} " in f" {q_lower} ":
                    score += 2
            # Check answer matches
            if word in a_lower:
                score += 1
                if f" {word} " in f" {a_lower} ":
                    score += 1
                    
        if score > 0:
            scored_faqs.append((score, faq))

    # Sort by score descending and return rows
    scored_faqs.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_faqs[:limit]]

# --- Chat History Operations ---

def save_chat_message(user_id: int, role: str, message: str):
    """Save a chat message to history."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, role, message)
    )
    conn.commit()
    conn.close()

def get_chat_history(user_id: int, limit: int = 10):
    """Retrieve chat history for a user, sorted chronologically."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, message FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # Reverse so they are in chronological order (oldest to newest)
    return list(reversed(rows))

def clear_chat_history(user_id: int):
    """Clear chat history for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- Handoff Operations ---

def create_handoff_request(user_id: int, username: str, first_name: str) -> bool:
    """Create a new handoff request or reopen one. Returns True if created/updated."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO handoffs (user_id, username, first_name, status, created_at)
            VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET 
                username = excluded.username,
                first_name = excluded.first_name,
                status = 'pending',
                created_at = CURRENT_TIMESTAMP
            """,
            (user_id, username, first_name)
        )
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error creating handoff: {e}")
        success = False
    finally:
        conn.close()
    return success

def get_pending_handoffs():
    """Retrieve all pending handoff requests."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM handoffs WHERE status = 'pending' ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def resolve_handoff(user_id: int) -> bool:
    """Resolve a handoff request by changing status to 'resolved'."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE handoffs SET status = 'resolved' WHERE user_id = ?", (user_id,))
    conn.commit()
    changes = conn.total_changes
    conn.close()
    return changes > 0

def is_user_in_handoff(user_id: int) -> bool:
    """Check if the user currently has a pending handoff request."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM handoffs WHERE user_id = ? AND status = 'pending'", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

# --- Usage Statistics Operations ---

def log_usage(user_id: int, action: str):
    """Log a user action for analytical purposes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO usage_stats (user_id, action) VALUES (?, ?)",
        (user_id, action)
    )
    conn.commit()
    conn.close()

def get_stats():
    """Get system-wide usage statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Total actions logged
    cursor.execute("SELECT COUNT(*) FROM usage_stats")
    stats['total_actions'] = cursor.fetchone()[0]
    
    # Unique active users
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM usage_stats")
    stats['unique_users'] = cursor.fetchone()[0]
    
    # Total messages processed
    cursor.execute("SELECT COUNT(*) FROM chat_history WHERE role = 'user'")
    stats['total_user_messages'] = cursor.fetchone()[0]
    
    # Total FAQ entries
    cursor.execute("SELECT COUNT(*) FROM faqs")
    stats['total_faqs'] = cursor.fetchone()[0]
    
    # Total handoff requests (all-time)
    cursor.execute("SELECT COUNT(*) FROM handoffs")
    stats['total_handoff_requests_all_time'] = cursor.fetchone()[0]
    
    # Pending handoff requests
    cursor.execute("SELECT COUNT(*) FROM handoffs WHERE status = 'pending'")
    stats['pending_handoff_requests'] = cursor.fetchone()[0]

    # Action-specific breakdown
    cursor.execute("SELECT action, COUNT(*) as count FROM usage_stats GROUP BY action")
    stats['actions_breakdown'] = {row['action']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    return stats
