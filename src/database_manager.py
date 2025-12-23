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
    
    # Server Management
    def get_or_create_server(self, machine_id: str, host: str, user: str, port: int = 22,
                            hostname: str = "", description: str = "", tags: str = "") -> Optional[str]:
        """
        Get existing server by machine_id or create new one
        
        Args:
            machine_id: Unique machine identifier from /etc/machine-id
            host: Current host address
            user: Current username
            port: Current SSH port
            hostname: Discovered hostname
            description: Optional description
            tags: Optional tags
        
        Returns:
            Server ID (machine_id) or None on error
        """
        if not self.ensure_connected():
            return None
        
        try:
            cursor = self.conn.cursor()
            
            # Check if server exists
            cursor.execute(
                "SELECT machine_id FROM servers WHERE machine_id = ?",
                (machine_id,)
            )
            result = cursor.fetchone()
            
            if result:
                # Update last seen and connection details
                cursor.execute(
                    """UPDATE servers 
                       SET host = ?, user = ?, port = ?, hostname = ?,
                           last_seen = CURRENT_TIMESTAMP, connection_count = connection_count + 1
                       WHERE machine_id = ?""",
                    (host, user, port, hostname, machine_id)
                )
                self.conn.commit()
                logger.info(f"Updated server connection details for machine_id={machine_id[:16]}...")
                return machine_id
            
            # Create new server
            cursor.execute(
                """INSERT INTO servers (machine_id, hostname, host, user, port, description, tags) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (machine_id, hostname, host, user, port, description, tags)
            )
            self.conn.commit()
            logger.info(f"Created server: {user}@{host}:{port} (machine_id={machine_id[:16]}...)")
            return machine_id
                
        except Exception as e:
            logger.error(f"Error getting/creating server: {e}")
            self.conn.rollback()
            return None
    
    def get_server_by_machine_id(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """
        Get server details by machine_id
        
        Args:
            machine_id: Machine identifier
            
        Returns:
            Server dict or None
        """
        if not self.ensure_connected():
            return None
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM servers WHERE machine_id = ?",
                (machine_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Error getting server by machine_id: {e}")
            return None
    
    # Conversation Management
    def start_conversation(self, machine_id: str, goal_summary: str, 
                          created_by: str = "claude") -> Optional[int]:
        """
        Start a new conversation
        
        Returns:
            Conversation ID or None on error
        """
        if not self.ensure_connected():
            return None
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO conversations (machine_id, goal_summary, created_by) 
                   VALUES (?, ?, ?)""",
                (machine_id, goal_summary, created_by)
            )
            conversation_id = cursor.lastrowid
            self.conn.commit()
            logger.info(f"Started conversation {conversation_id}: {goal_summary}")
            return conversation_id
                
        except Exception as e:
            logger.error(f"Error starting conversation: {e}")
            self.conn.rollback()
            return None
    
    def end_conversation(self, conversation_id: int, status: str, 
                        user_notes: str = None) -> bool:
        """
        End a conversation
        
        Args:
            conversation_id: Conversation ID
            status: 'success', 'failed', or 'rolled_back'
            user_notes: Optional notes
            
        Returns:
            True if successful
        """
        if not self.ensure_connected():
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """UPDATE conversations 
                   SET status = ?, ended_at = CURRENT_TIMESTAMP, user_notes = ? 
                   WHERE id = ?""",
                (status, user_notes, conversation_id)
            )
            self.conn.commit()
            logger.info(f"Ended conversation {conversation_id} with status: {status}")
            return True
                
        except Exception as e:
            logger.error(f"Error ending conversation: {e}")
            self.conn.rollback()
            return False
    
    def get_conversation(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get conversation details"""
        if not self.ensure_connected():
            return None
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return None

    def get_active_conversation(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """
        Get in-progress conversation for a machine

        Args:
            machine_id: Machine ID

        Returns:
            Conversation dict or None
        """
        if not self.ensure_connected():
            return None
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """SELECT * FROM conversations 
                   WHERE machine_id = ? AND status = 'in_progress'
                   ORDER BY started_at DESC 
                   LIMIT 1""",
                (machine_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Error getting active conversation: {e}")
            return None
    
    def pause_conversation(self, conversation_id: int) -> bool:
        """
        Pause a conversation (status -> 'paused')
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if successful
        """
        if not self.ensure_connected():
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE conversations SET status = 'paused' WHERE id = ?",
                (conversation_id,)
            )
            self.conn.commit()
            logger.info(f"Paused conversation {conversation_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error pausing conversation: {e}")
            self.conn.rollback()
            return False
    
    def resume_conversation(self, conversation_id: int) -> bool:
        """
        Resume a conversation (status -> 'in_progress')
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if successful
        """
        if not self.ensure_connected():
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE conversations SET status = 'in_progress' WHERE id = ?",
                (conversation_id,)
            )
            self.conn.commit()
            logger.info(f"Resumed conversation {conversation_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error resuming conversation: {e}")
            self.conn.rollback()
            return False

    def get_paused_conversations(self, machine_id: str) -> List[Dict[str, Any]]:
        """
        Get all paused conversations for a machine

        Args:
            machine_id: Machine ID

        Returns:
            List of paused conversation dicts
        """
        if not self.ensure_connected():
            return []
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """SELECT * FROM conversations 
                   WHERE machine_id = ? AND status = 'paused'
                   ORDER BY started_at DESC""",
                (machine_id,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error getting paused conversations: {e}")
            return []

    def list_conversations(self, machine_id: str = None, status: str = None, 
                          limit: int = 50) -> List[Dict[str, Any]]:
        """List conversations with optional filters"""
        if not self.ensure_connected():
            return []
        
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM conversations WHERE 1=1"
            params = []

            if machine_id:
                query += " AND machine_id = ?"
                params.append(machine_id)

            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []
    
    # Command Management - Phase 1 Enhanced
    def add_command(self, machine_id: str, conversation_id: int = None,
                   command_text: str = "", result_output: str = "",
                   status: str = 'executed', exit_code: int = None,
                   has_errors: bool = False, error_context: str = None, 
                   line_count: int = 0, backup_file_path: str = None, 
                   backup_size_bytes: int = None) -> Optional[int]:
        """
        Add command to database (all commands tracked, conversation optional)
        
        Args:
            machine_id: Machine where command was executed (required)
            conversation_id: Optional conversation ID (None for standalone commands)
            command_text: The command that was executed
            result_output: Command output
            status: Execution status (executed/cancelled/timeout/undone)
            exit_code: Command exit code if captured
            has_errors: Whether output contains errors (from analysis)
            error_context: Extracted error details
            line_count: Number of output lines
            backup_file_path: Path to backup file if created
            backup_size_bytes: Size of backup file
        
        Returns:
            Command ID or None on error
        """
        if not self.ensure_connected():
            return None
        
        try:
            cursor = self.conn.cursor()
            
            # Get next sequence number only if conversation_id is provided
            sequence_num = None
            if conversation_id is not None:
                cursor.execute(
                    "SELECT COALESCE(MAX(sequence_num), 0) + 1 as next_seq FROM commands WHERE conversation_id = ?",
                    (conversation_id,)
                )
                result = cursor.fetchone()
                sequence_num = result['next_seq'] if result else 1
            
            # Insert command
            cursor.execute(
                """INSERT INTO commands (
                    machine_id, conversation_id, sequence_num, command_text, result_output,
                    status, exit_code, has_errors, error_context, line_count,
                    backup_file_path, backup_created_at, backup_size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (machine_id, conversation_id, sequence_num, command_text, result_output,
                 status, exit_code, has_errors, error_context, line_count,
                 backup_file_path, datetime.now() if backup_file_path else None, backup_size_bytes)
            )
            command_id = cursor.lastrowid
            self.conn.commit()
            
            if conversation_id:
                logger.debug(f"Added command {command_id} to conversation {conversation_id}")
            else:
                logger.debug(f"Added standalone command {command_id}")
            
            return command_id
                
        except Exception as e:
            logger.error(f"Error adding command: {e}")
            self.conn.rollback()
            return None
    
    def get_commands(self, conversation_id: int, reverse_order: bool = False) -> List[Dict[str, Any]]:
        """
        Get all commands for a conversation
        
        Args:
            conversation_id: Conversation ID
            reverse_order: Return in reverse order (for rollback)
            
        Returns:
            List of command dictionaries
        """
        if not self.ensure_connected():
            return []
        
        try:
            cursor = self.conn.cursor()
            order = "DESC" if reverse_order else "ASC"
            cursor.execute(
                f"SELECT * FROM commands WHERE conversation_id = ? ORDER BY sequence_num {order}",
                (conversation_id,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error getting commands: {e}")
            return []
    
    def update_command_status(self, command_id: int, status: str) -> bool:
        """
        Update command status (for rollback tracking)
        
        Args:
            command_id: Command ID
            status: New status ('undone')
            
        Returns:
            True if successful
        """
        if not self.ensure_connected():
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE commands SET status = ?, undone_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, command_id)
            )
            self.conn.commit()
            logger.debug(f"Updated command {command_id} status to: {status}")
            return True
                
        except Exception as e:
            logger.error(f"Error updating command status: {e}")
            self.conn.rollback()
            return False
    
    # Recipe Management
    def create_recipe(self, name: str, description: str, command_sequence: List[Dict],
                     prerequisites: str = None, success_criteria: str = None,
                     source_conversation_id: int = None, created_by: str = "claude") -> Optional[int]:
        """
        Create a new recipe
        
        Returns:
            Recipe ID or None on error
        """
        if not self.ensure_connected():
            return None
        
        try:
            import json
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO recipes (
                    name, description, command_sequence, prerequisites, 
                    success_criteria, source_conversation_id, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, description, json.dumps(command_sequence), prerequisites,
                 success_criteria, source_conversation_id, created_by)
            )
            recipe_id = cursor.lastrowid
            self.conn.commit()
            logger.info(f"Created recipe {recipe_id}: {name}")
            return recipe_id
                
        except Exception as e:
            logger.error(f"Error creating recipe: {e}")
            self.conn.rollback()
            return None
    
    def get_recipe(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        """Get recipe by ID"""
        if not self.ensure_connected():
            return None
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Error getting recipe: {e}")
            return None
    
    def list_recipes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all recipes"""
        if not self.ensure_connected():
            return []
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM recipes ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error listing recipes: {e}")
            return []
    
    def increment_recipe_usage(self, recipe_id: int) -> bool:
        """Increment recipe usage counter"""
        if not self.ensure_connected():
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE recipes SET times_used = times_used + 1, last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
                (recipe_id,)
            )
            self.conn.commit()
            return True
                
        except Exception as e:
            logger.error(f"Error incrementing recipe usage: {e}")
            self.conn.rollback()
            return False

            return False
    
            return False
    
            return []
    
