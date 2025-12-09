"""
Database Batch Operations - SQLite Version (FIXED)
Adapter layer to match tools_batch.py calling patterns with existing schema
"""

import sqlite3
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class BatchDatabaseOperations:
    """
    Database operations for batch script execution tracking
    Adapts tools_batch.py calls to existing SQLite schema
    """
    
    def __init__(self, database_manager):
        """
        Initialize with database manager
        
        Args:
            database_manager: DatabaseManager instance
        """
        self.db = database_manager
    
    # ========== METHODS CALLED BY tools_batch.py ==========
    
    
    def create_batch_execution(self, machine_id: str, script_name: str = "batch_script", 
                               created_by: str = "claude", 
                               conversation_id: int = None) -> Optional[int]:
        """
        Create a new batch execution record (ADAPTED to existing schema)
        
        Args:
            machine_id: Machine ID where batch is running
            created_by: Who created this batch (not used in schema, for compatibility)
            
        Returns:
            Batch execution ID or None on error
        """
        if not self.db.ensure_connected():
            return None
        
        try:
            cursor = self.db.conn.cursor()
            # Adapt to existing schema: set default values for required fields
            cursor.execute(
                """INSERT INTO batch_executions (
                    machine_id, conversation_id, script_name, total_steps, 
                    completed_steps, status
                ) VALUES (?, ?, ?, 0, 0, 'pending')""",
                (machine_id, conversation_id, script_name)
            )
                     
                        
            batch_id = cursor.lastrowid
            self.db.conn.commit()
            logger.info(f"Created batch execution {batch_id} for machine {machine_id}")
            return batch_id
            
        except Exception as e:
            logger.error(f"Error creating batch execution: {e}")
            self.db.conn.rollback()
            return None
    
    
    def save_batch_script(self, batch_execution_id: int, source_code: str, 
                         description: str, filename: str, content_hash: str = None) -> Optional[int]:
        """
        Save batch script source code with hash for deduplication
        
        Args:
            batch_execution_id: Batch execution ID (not used in schema, for compatibility)
            source_code: Script content
            description: Script description
            filename: Script filename (used as 'name' in schema)
            content_hash: SHA256 hash of script content (calculated if not provided)
            
        Returns:
            Script ID or None on error
        """
        if not self.db.ensure_connected():
            return None
        
        try:
            import hashlib
            cursor = self.db.conn.cursor()
            
            # Calculate hash if not provided
            if content_hash is None:
                content_hash = hashlib.sha256(source_code.encode()).hexdigest()
            
            # Check if script with this name exists
            cursor.execute(
                "SELECT id FROM batch_scripts WHERE name = ?",
                (filename,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                cursor.execute(
                    """UPDATE batch_scripts 
                       SET description = ?, script_content = ?, content_hash = ?
                       WHERE name = ?""",
                    (description, source_code, content_hash, filename)
                )
                script_id = existing[0]
                logger.info(f"Updated batch script: {filename}")
            else:
                # Create new
                cursor.execute(
                    """INSERT INTO batch_scripts (name, description, script_content, content_hash, created_by, times_used)
                       VALUES (?, ?, ?, ?, 'claude', 1)""",
                    (filename, description, source_code, content_hash)
                )
                script_id = cursor.lastrowid
                logger.info(f"Created batch script: {filename} (hash={content_hash[:16]}...)")
            
            self.db.conn.commit()
            return script_id
            
        except Exception as e:
            logger.error(f"Error saving batch script: {e}")
            self.db.conn.rollback()
            return None
      
    def update_batch_execution(self, batch_execution_id: int, status: str,
                              exit_code: Optional[int], output_file_path: Optional[str]) -> bool:
        """
        Update batch execution with final status (ADAPTED to existing schema)
        
        Args:
            batch_execution_id: Batch execution ID
            status: Final status ('success', 'failed', 'timeout')
            exit_code: Command exit code (not stored in schema, for compatibility)
            output_file_path: Path to output log (not stored in schema, for compatibility)
            
        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False
        
        try:
            cursor = self.db.conn.cursor()
            
            # Map status to schema values
            if status == "success":
                db_status = "completed"
            elif status == "timeout":
                db_status = "timeout"
            else:
                db_status = "failed"
            
            # Update status and completion time
            cursor.execute(
                """UPDATE batch_executions 
                   SET status = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (db_status, batch_execution_id)
            )
            self.db.conn.commit()
            logger.info(f"Updated batch {batch_execution_id} to status: {db_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating batch execution: {e}")
            self.db.conn.rollback()
            return False
    
    # ========== ADDITIONAL HELPER METHODS ==========
    
    def update_batch_progress(self, batch_id: int, completed_steps: int) -> bool:
        """
        Update batch execution progress
        
        Args:
            batch_id: Batch execution ID
            completed_steps: Number of completed steps
            
        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE batch_executions 
                   SET completed_steps = ? 
                   WHERE id = ?""",
                (completed_steps, batch_id)
            )
            self.db.conn.commit()
            logger.debug(f"Updated batch {batch_id} progress: {completed_steps} steps")
            return True
            
        except Exception as e:
            logger.error(f"Error updating batch progress: {e}")
            self.db.conn.rollback()
            return False
    
    def complete_batch_execution(self, batch_id: int, status: str,
                                 duration_seconds: float) -> bool:
        """
        Mark batch execution as complete with duration
        
        Args:
            batch_id: Batch execution ID
            status: 'completed' or 'failed'
            duration_seconds: Total execution time
            
        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE batch_executions 
                   SET status = ?, completed_at = CURRENT_TIMESTAMP, duration_seconds = ?
                   WHERE id = ?""",
                (status, duration_seconds, batch_id)
            )
            self.db.conn.commit()
            logger.info(f"Completed batch {batch_id} with status: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error completing batch execution: {e}")
            self.db.conn.rollback()
            return False
    
    def get_batch_execution(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """
        Get batch execution details
        
        Args:
            batch_id: Batch execution ID
            
        Returns:
            Batch execution dict or None
        """
        if not self.db.ensure_connected():
            return None
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM batch_executions WHERE id = ?",
                (batch_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"Error getting batch execution: {e}")
            return None
    
    def list_batch_executions(self, machine_id: str = None,
                             conversation_id: int = None,
                             status: str = None,
                             limit: int = 50) -> List[Dict[str, Any]]:
        """
        List batch executions with filters
        
        Args:
            machine_id: Filter by machine ID
            conversation_id: Filter by conversation ID
            status: Filter by status
            limit: Maximum results
            
        Returns:
            List of batch execution dicts
        """
        if not self.db.ensure_connected():
            return []
        
        try:
            cursor = self.db.conn.cursor()
            query = "SELECT * FROM batch_executions WHERE 1=1"
            params = []
            
            if machine_id:
                query += " AND machine_id = ?"
                params.append(machine_id)
            
            if conversation_id:
                query += " AND conversation_id = ?"
                params.append(conversation_id)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error listing batch executions: {e}")
            return []
    
    def link_command_to_batch(self, command_id: int, batch_execution_id: int) -> bool:
        """
        Link a command to a batch execution
        
        Args:
            command_id: Command ID
            batch_execution_id: Batch execution ID
            
        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE commands SET batch_execution_id = ? WHERE id = ?",
                (batch_execution_id, command_id)
            )
            self.db.conn.commit()
            logger.debug(f"Linked command {command_id} to batch {batch_execution_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error linking command to batch: {e}")
            self.db.conn.rollback()
            return False
    
    def get_batch_commands(self, batch_execution_id: int) -> List[Dict[str, Any]]:
        """
        Get all commands for a batch execution
        
        Args:
            batch_execution_id: Batch execution ID
            
        Returns:
            List of command dicts
        """
        if not self.db.ensure_connected():
            return []
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT * FROM commands 
                   WHERE batch_execution_id = ? 
                   ORDER BY executed_at ASC""",
                (batch_execution_id,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error getting batch commands: {e}")
            return []
    
    def get_batch_script(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get batch script by name
        
        Args:
            name: Script name
            
        Returns:
            Script dict or None
        """
        if not self.db.ensure_connected():
            return None
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM batch_scripts WHERE name = ?",
                (name,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"Error getting batch script: {e}")
            return None
    
    def list_batch_scripts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all batch scripts
        
        Args:
            limit: Maximum results
            
        Returns:
            List of script dicts
        """
        if not self.db.ensure_connected():
            return []
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM batch_scripts ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error listing batch scripts: {e}")
            return []
    
    def increment_script_usage(self, script_name: str) -> bool:
        """
        Increment usage counter for a script
        
        Args:
            script_name: Script name
            
        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE batch_scripts 
                   SET times_used = times_used + 1, last_used_at = CURRENT_TIMESTAMP
                   WHERE name = ?""",
                (script_name,)
            )
            self.db.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing script usage: {e}")
            self.db.conn.rollback()
            return False
