"""
Initialize the JARVIS SQLite database with proper schema.
Run this once to set up the database tables.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_data.sqlite")

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Conversation logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            user_message TEXT,
            assistant_response TEXT,
            intent TEXT,
            session_id TEXT
        )
    """)
    
    # User preferences table  
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # Command history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            command TEXT,
            intent TEXT,
            success INTEGER DEFAULT 1,
            latency_ms REAL
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_database()
