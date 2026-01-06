"""
Batch Script Management - CRUD Operations
Functions for listing, getting, saving, and deleting batch scripts
"""

import logging
import hashlib
from datetime import datetime
from mcp import types

logger = logging.getLogger(__name__)


async def _list_batch_scripts(
    limit: int,
    offset: int,
    sort_by: str,
    search: str,
    database=None
) -> list[types.TextContent]:
    """List batch scripts from database"""

    if not database or not database.is_connected():
        return [types.TextContent(
            type="text",
            text="Error: Database not connected"
        )]

    try:
        # Validate limit
        if limit < 1 or limit > 200:
            limit = 50

        cursor = database.conn.cursor()

        # Build query based on sort_by
        order_clause = {
            "most_used": "times_used DESC, last_used_at DESC",
            "recently_used": "last_used_at DESC",
            "newest": "created_at DESC",
            "oldest": "created_at ASC"
        }.get(sort_by, "last_used_at DESC")

        # Build WHERE clause for search
        where_clause = ""
        params = []
        if search:
            where_clause = "WHERE (name LIKE ? OR description LIKE ?)"
            params = [f"%{search}%", f"%{search}%"]

        # Get total count
        count_query = f"SELECT COUNT(*) FROM batch_scripts {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Get scripts
        query = f"""
            SELECT
                id, name, description,
                times_used, last_used_at, created_at,
                LENGTH(script_content) as content_length
            FROM batch_scripts
            {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
        """

        cursor.execute(query, params + [limit, offset])
        scripts = cursor.fetchall()

        if not scripts:
            return [types.TextContent(
                type="text",
                text=f"No batch scripts found{' matching search criteria' if search else ''}."
            )]

        # Format response
        lines = [
            f"Found {total_count} batch script(s) (showing {len(scripts)})",
            ""
        ]

        for script in scripts:
            script_id, name, desc, times_used, last_used, created, content_len = script
            lines.extend([
                f"ID: {script_id}",
                f"  Name: {name}",
                f"  Description: {desc or 'N/A'}",
                f"  Used: {times_used} time(s), Last: {last_used or 'Never'}",
                f"  Created: {created}",
                f"  Size: {content_len} bytes",
                ""
            ])

        if total_count > offset + len(scripts):
            lines.append(f"... {total_count - offset - len(scripts)} more scripts available (use offset={offset + limit})")

        return [types.TextContent(
            type="text",
            text="\n".join(lines)
        )]

    except Exception as e:
        logger.error(f"Error listing scripts: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error listing scripts: {str(e)}"
        )]


async def _get_batch_script(
    script_id: int,
    database=None
) -> list[types.TextContent]:
    """Get batch script details and content"""

    if not database or not database.is_connected():
        return [types.TextContent(
            type="text",
            text="Error: Database not connected"
        )]

    try:
        cursor = database.conn.cursor()
        cursor.execute("""
            SELECT
                id, name, description, script_content,
                content_hash, times_used, last_used_at, created_at
            FROM batch_scripts
            WHERE id = ?
        """, (script_id,))

        script = cursor.fetchone()

        if not script:
            return [types.TextContent(
                type="text",
                text=f"Error: Script with ID {script_id} not found"
            )]

        script_id, name, desc, content, hash_val, times_used, last_used, created = script

        # Format response
        response = [
            f"Batch Script ID: {script_id}",
            f"Name: {name}",
            f"Description: {desc or 'N/A'}",
            f"Times Used: {times_used}",
            f"Last Used: {last_used or 'Never'}",
            f"Created: {created}",
            f"Content Hash: {hash_val[:16]}...",
            "",
            "Script Content:",
            "```bash",
            content,
            "```"
        ]

        return [types.TextContent(
            type="text",
            text="\n".join(response)
        )]

    except Exception as e:
        logger.error(f"Error getting script: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error getting script: {str(e)}"
        )]


async def _save_batch_script(
    content: str,
    description: str,
    database=None,
    shared_state=None
) -> list[types.TextContent]:
    """Save batch script to database (without executing)"""

    if not database or not database.is_connected():
        return [types.TextContent(
            type="text",
            text="Error: Database not connected"
        )]

    try:
        # Calculate content hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        cursor = database.conn.cursor()

        # Check if this exact script already exists
        cursor.execute("""
            SELECT id, name, times_used FROM batch_scripts
            WHERE content_hash = ?
        """, (content_hash,))

        existing = cursor.fetchone()

        if existing:
            # Script already exists - just return info
            return [types.TextContent(
                type="text",
                text=f"ℹ️ This exact script already exists in database:\n\nScript ID: {existing[0]}\nName: {existing[1]}\nTimes Used: {existing[2]}\n\nNo new script created (deduplication)."
            )]

        # Create new script
        script_name = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sh"

        cursor.execute("""
            INSERT INTO batch_scripts (
                name, script_content, description, content_hash,
                created_by, created_at, times_used
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
        """, (script_name, content, description, content_hash, "claude"))

        script_id = cursor.lastrowid
        database.conn.commit()

        return [types.TextContent(
            type="text",
            text=f"✅ Script saved to database:\n\nScript ID: {script_id}\nName: {script_name}\nDescription: {description}\n\nUse execute_script_content_by_id(script_id={script_id}) to run it."
        )]

    except Exception as e:
        logger.error(f"Error saving script: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error saving script: {str(e)}"
        )]


async def _delete_batch_script(
    script_id: int,
    confirm: bool,
    database=None
) -> list[types.TextContent]:
    """Delete batch script (hard delete with confirmation)"""

    if not database or not database.is_connected():
        return [types.TextContent(
            type="text",
            text="Error: Database not connected"
        )]

    try:
        cursor = database.conn.cursor()

        # STEP 1: First call without confirm - show details and warn
        if not confirm:
            cursor.execute("""
                SELECT
                    id, name, description,
                    times_used, last_used_at, created_at,
                    (SELECT COUNT(*) FROM batch_executions WHERE script_name = batch_scripts.name) as execution_count
                FROM batch_scripts
                WHERE id = ?
            """, (script_id,))

            script = cursor.fetchone()

            if not script:
                return [types.TextContent(
                    type="text",
                    text=f"Error: Script with ID {script_id} not found"
                )]

            # Format warning message
            warning = [
                "⚠️ CONFIRM DELETION",
                "",
                f"Script ID: {script[0]}",
                f"Name: {script[1]}",
                f"Description: {script[2] or 'N/A'}",
                f"Times Used: {script[3]}",
                f"Last Used: {script[4] or 'Never'}",
                f"Created: {script[5]}",
                f"Execution History: {script[6]} executions recorded",
                "",
                "⚠️ WARNING: This will permanently delete the script.",
                "⚠️ Execution history will remain but script content will be lost.",
                "",
                "To proceed, call delete_batch_script with confirm=true"
            ]

            return [types.TextContent(
                type="text",
                text="\n".join(warning)
            )]

        # STEP 2: Second call with confirm=true - actually delete
        # Get script name before deletion
        cursor.execute("SELECT name FROM batch_scripts WHERE id = ?", (script_id,))
        result = cursor.fetchone()

        if not result:
            return [types.TextContent(
                type="text",
                text=f"Error: Script with ID {script_id} not found"
            )]

        script_name = result[0]

        # Hard delete from batch_scripts
        cursor.execute("DELETE FROM batch_scripts WHERE id = ?", (script_id,))
        database.conn.commit()

        return [types.TextContent(
            type="text",
            text=f"✅ Script deleted: {script_name} (ID: {script_id})\n\nExecution history preserved in batch_executions table."
        )]

    except Exception as e:
        logger.error(f"Error deleting script: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error deleting script: {str(e)}"
        )]
