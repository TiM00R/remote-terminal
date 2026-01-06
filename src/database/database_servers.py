"""
Database Server Operations
Server management functions for database operations
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseServers:
    """Server management operations"""

    def __init__(self, db_manager):
        """
        Initialize with database manager reference

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

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
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()

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
                self.db.conn.commit()
                logger.info(f"Updated server connection details for machine_id={machine_id[:16]}...")
                return machine_id

            # Create new server
            cursor.execute(
                """INSERT INTO servers (machine_id, hostname, host, user, port, description, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (machine_id, hostname, host, user, port, description, tags)
            )
            self.db.conn.commit()
            logger.info(f"Created server: {user}@{host}:{port} (machine_id={machine_id[:16]}...)")
            return machine_id

        except Exception as e:
            logger.error(f"Error getting/creating server: {e}")
            self.db.conn.rollback()
            return None

    def get_server_by_machine_id(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """
        Get server details by machine_id

        Args:
            machine_id: Machine identifier

        Returns:
            Server dict or None
        """
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM servers WHERE machine_id = ?",
                (machine_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting server by machine_id: {e}")
            return None
