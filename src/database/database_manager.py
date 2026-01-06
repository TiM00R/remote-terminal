"""
Database Manager - SQLite Version
Handles SQLite connection and queries for conversation tracking
Phase 1 Enhanced: Unified command execution, server-scoped conversations
Phase 2: Machine ID-based server identification
"""

import sqlite3
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from database.database_servers import DatabaseServers
from database.database_conversations import DatabaseConversations
from database.database_commands import DatabaseCommands
from database.database_recipes import DatabaseRecipes

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database connection and operations
    """

    def __init__(self, db_path: str = None):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file (default: remote_terminal.db in project root)
        """

        if db_path is None:
            # Current working directory
            cwd = Path.cwd()
            cwd_data_folder = cwd / 'data'
            cwd_data_db = cwd_data_folder / 'remote_terminal.db'

            # Project root (for GitHub users)
            project_root = Path(__file__).parent.parent
            project_data_folder = project_root / 'data'
            project_data_db = project_data_folder / 'remote_terminal.db'

            if cwd_data_db.exists():
                # Use existing database in CWD/data
                db_path = str(cwd_data_db)
            elif project_data_db.exists():
                # Use existing database in project/data folder (GitHub)
                db_path = str(project_data_db)
            elif project_data_folder.exists():
                # Project data folder exists (GitHub setup)
                db_path = str(project_data_db)
            else:
                # Create data folder in CWD (pip setup)
                cwd_data_folder.mkdir(exist_ok=True)
                db_path = str(cwd_data_db)

            logger.info(f"Database path: {db_path}")


        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.connected = False

        # Initialize operation handlers
        self._servers = None
        self._conversations = None
        self._commands = None
        self._recipes = None

    def connect(self) -> bool:
        """
        Connect to SQLite database

        Returns:
            True if connection successful
        """
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Enable dict-like access
            self.connected = True
            logger.info(f"Connected to SQLite database: {self.db_path}")

            # Initialize schema if needed
            self._initialize_schema()

            # Initialize operation handlers
            self._servers = DatabaseServers(self)
            self._conversations = DatabaseConversations(self)
            self._commands = DatabaseCommands(self)
            self._recipes = DatabaseRecipes(self)

            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Close database connection"""
        if self.conn:
            try:
                self.conn.close()
                self.connected = False
                logger.info("Disconnected from database")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    def is_connected(self) -> bool:
        """Check if connected to database"""
        if not self.conn or not self.connected:
            return False
        try:
            # Try a simple query to verify connection
            self.conn.execute("SELECT 1")
            return True
        except:
            self.connected = False
            return False

    def ensure_connected(self) -> bool:
        """Ensure database connection is active, reconnect if needed"""
        if not self.is_connected():
            return self.connect()
        return True

    def _initialize_schema(self) -> None:
        """Initialize database schema if tables don't exist"""
        try:
            cursor = self.conn.cursor()

            # Servers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS servers (
                    machine_id TEXT PRIMARY KEY,
                    hostname TEXT,
                    host TEXT NOT NULL,
                    user TEXT NOT NULL,
                    port INTEGER DEFAULT 22,
                    description TEXT,
                    tags TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    connection_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_servers_connection
                ON servers(host, user, port)
            """)

            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id TEXT NOT NULL,
                    goal_summary TEXT NOT NULL,
                    status TEXT DEFAULT 'in_progress',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    created_by TEXT DEFAULT 'claude',
                    user_notes TEXT,
                    FOREIGN KEY (machine_id) REFERENCES servers(machine_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_machine
                ON conversations(machine_id, status)
            """)

            # Commands table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id TEXT NOT NULL,
                    conversation_id INTEGER,
                    sequence_num INTEGER,
                    command_text TEXT NOT NULL,
                    result_output TEXT,
                    status TEXT DEFAULT 'executed',
                    exit_code INTEGER,
                    has_errors BOOLEAN DEFAULT 0,
                    error_context TEXT,
                    line_count INTEGER DEFAULT 0,
                    backup_file_path TEXT,
                    backup_created_at TIMESTAMP,
                    backup_size_bytes INTEGER,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    undone_at TIMESTAMP,
                    batch_execution_id INTEGER,
                    FOREIGN KEY (machine_id) REFERENCES servers(machine_id),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_commands_conversation
                ON commands(conversation_id, sequence_num)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_commands_machine
                ON commands(machine_id, executed_at)
            """)

            # Recipes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    command_sequence TEXT NOT NULL,
                    prerequisites TEXT,
                    success_criteria TEXT,
                    source_conversation_id INTEGER,
                    times_used INTEGER DEFAULT 0,
                    last_used_at TIMESTAMP,
                    created_by TEXT DEFAULT 'claude',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
                )
            """)

            # Batch executions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id TEXT NOT NULL,
                    conversation_id INTEGER,
                    script_name TEXT NOT NULL,
                    total_steps INTEGER NOT NULL,
                    completed_steps INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_seconds REAL,
                    FOREIGN KEY (machine_id) REFERENCES servers(machine_id),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)


            # Batch scripts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    script_content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_by TEXT DEFAULT 'claude',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    times_used INTEGER DEFAULT 0,
                    last_used_at TIMESTAMP
                )
            """)


            # Add index for hash lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_scripts_hash
                ON batch_scripts(content_hash)
            """)

            self.conn.commit()
            logger.info("Database schema initialized")

        except Exception as e:
            logger.error(f"Error initializing schema: {e}")
            raise

    # Delegate to operation handlers
    def get_or_create_server(self, *args, **kwargs):
        """Get or create server - delegates to DatabaseServers"""
        return self._servers.get_or_create_server(*args, **kwargs)

    def get_server_by_machine_id(self, *args, **kwargs):
        """Get server by machine_id - delegates to DatabaseServers"""
        return self._servers.get_server_by_machine_id(*args, **kwargs)

    def start_conversation(self, *args, **kwargs):
        """Start conversation - delegates to DatabaseConversations"""
        return self._conversations.start_conversation(*args, **kwargs)

    def end_conversation(self, *args, **kwargs):
        """End conversation - delegates to DatabaseConversations"""
        return self._conversations.end_conversation(*args, **kwargs)

    def get_conversation(self, *args, **kwargs):
        """Get conversation - delegates to DatabaseConversations"""
        return self._conversations.get_conversation(*args, **kwargs)

    def get_active_conversation(self, *args, **kwargs):
        """Get active conversation - delegates to DatabaseConversations"""
        return self._conversations.get_active_conversation(*args, **kwargs)

    def pause_conversation(self, *args, **kwargs):
        """Pause conversation - delegates to DatabaseConversations"""
        return self._conversations.pause_conversation(*args, **kwargs)

    def resume_conversation(self, *args, **kwargs):
        """Resume conversation - delegates to DatabaseConversations"""
        return self._conversations.resume_conversation(*args, **kwargs)

    def get_paused_conversations(self, *args, **kwargs):
        """Get paused conversations - delegates to DatabaseConversations"""
        return self._conversations.get_paused_conversations(*args, **kwargs)

    def list_conversations(self, *args, **kwargs):
        """List conversations - delegates to DatabaseConversations"""
        return self._conversations.list_conversations(*args, **kwargs)

    def add_command(self, *args, **kwargs):
        """Add command - delegates to DatabaseCommands"""
        return self._commands.add_command(*args, **kwargs)

    def get_commands(self, *args, **kwargs):
        """Get commands - delegates to DatabaseCommands"""
        return self._commands.get_commands(*args, **kwargs)

    def update_command_status(self, *args, **kwargs):
        """Update command status - delegates to DatabaseCommands"""
        return self._commands.update_command_status(*args, **kwargs)

    def create_recipe(self, *args, **kwargs):
        """Create recipe - delegates to DatabaseRecipes"""
        return self._recipes.create_recipe(*args, **kwargs)

    def get_recipe(self, *args, **kwargs):
        """Get recipe - delegates to DatabaseRecipes"""
        return self._recipes.get_recipe(*args, **kwargs)

    def list_recipes(self, *args, **kwargs):
        """List recipes - delegates to DatabaseRecipes"""
        return self._recipes.list_recipes(*args, **kwargs)

    def increment_recipe_usage(self, *args, **kwargs):
        """Increment recipe usage - delegates to DatabaseRecipes"""
        return self._recipes.increment_recipe_usage(*args, **kwargs)
