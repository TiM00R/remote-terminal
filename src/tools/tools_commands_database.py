"""
Command Database Operations - Saving commands to database
Handles persistence of command execution results
"""

import logging
from utils.utils import is_error_output, extract_error_context, count_lines

logger = logging.getLogger(__name__)


async def _save_to_database(database, shared_state, command, output, status,
                           conversation_id, preauth_result, backup_result, result):
    """Save command to database - Phase 1 Enhancement with machine_id validation"""
    try:
        # Get machine_id from shared state (should already be set by select_server)
        machine_id = shared_state.current_machine_id

        if not machine_id:
            logger.error("Cannot save command: no machine_id (server not connected)")
            result["tracking"] = {
                "database_saved": False,
                "error": "No machine_id - server not connected",
                "warning": "Commands are NOT being saved to database"
            }
            return

        # Validate machine_id before saving
        if not shared_state.is_valid_machine_id(machine_id):
            logger.error(f"Cannot save command: invalid machine_id (fallback ID detected): {machine_id}")
            result["tracking"] = {
                "database_saved": False,
                "error": f"Invalid machine_id (fallback ID): {machine_id}",
                "warning": "Commands are NOT being saved to database. Machine identity could not be verified."
            }
            return

        # Map status to database status
        db_status = 'executed'
        if status == 'cancelled':
            db_status = 'cancelled'
        elif status == 'timeout_still_running':
            db_status = 'timeout'
        # 'backgrounded' and 'completed' both map to 'executed'

        # Analyze output for errors
        has_errors = is_error_output(output, shared_state.config.claude.error_patterns)
        line_count = count_lines(output)
        error_context = extract_error_context(output) if has_errors else None

        # Get backup path if created
        backup_path = None
        if backup_result and backup_result.get("status") == "success":
            backup_path = backup_result.get("backup_path")

        # Save to database
        command_db_id = database.add_command(
            machine_id=machine_id,
            conversation_id=conversation_id,
            command_text=command,
            result_output=output,
            status=db_status,
            has_errors=has_errors,
            error_context=error_context,
            line_count=line_count,
            backup_file_path=backup_path
        )

        # Add tracking info to result ALWAYS (not just for conversations)
        result["tracking"] = {
            "database_saved": True,
            "command_db_id": command_db_id,
            "machine_id": machine_id,
            "conversation_id": conversation_id,
            "has_errors": has_errors,
            "line_count": line_count,
            "preauth": preauth_result or {"status": "skipped"},
            "backup": backup_result or {"status": "skipped"}
        }

        logger.debug(f"Saved command {command_db_id} to database (machine={machine_id[:16]}..., conversation={conversation_id})")

    except Exception as e:
        logger.error(f"Failed to save command to database: {e}", exc_info=True)
        result["tracking"] = {
            "database_saved": False,
            "error": str(e),
            "warning": "Command execution succeeded but database save failed"
        }
