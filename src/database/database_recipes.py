"""
Database Recipe Operations
Recipe management functions for database operations
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseRecipes:
    """Recipe management operations"""

    def __init__(self, db_manager):
        """
        Initialize with database manager reference

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def create_recipe(self, name: str, description: str, command_sequence: List[Dict],
                     prerequisites: str = None, success_criteria: str = None,
                     source_conversation_id: int = None, created_by: str = "claude") -> Optional[int]:
        """
        Create a new recipe

        Returns:
            Recipe ID or None on error
        """
        if not self.db.ensure_connected():
            return None

        try:
            import json
            cursor = self.db.conn.cursor()
            cursor.execute(
                """INSERT INTO recipes (
                    name, description, command_sequence, prerequisites,
                    success_criteria, source_conversation_id, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, description, json.dumps(command_sequence), prerequisites,
                 success_criteria, source_conversation_id, created_by)
            )
            recipe_id = cursor.lastrowid
            self.db.conn.commit()
            logger.info(f"Created recipe {recipe_id}: {name}")
            return recipe_id

        except Exception as e:
            logger.error(f"Error creating recipe: {e}")
            self.db.conn.rollback()
            return None

    def get_recipe(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        """Get recipe by ID"""
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting recipe: {e}")
            return None

    def list_recipes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all recipes"""
        if not self.db.ensure_connected():
            return []

        try:
            cursor = self.db.conn.cursor()
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
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE recipes SET times_used = times_used + 1, last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
                (recipe_id,)
            )
            self.db.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error incrementing recipe usage: {e}")
            self.db.conn.rollback()
            return False
