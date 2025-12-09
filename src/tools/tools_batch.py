"""
Batch Script Execution Tools
Tools for executing multi-command batch scripts on remote servers
Phase 4: Database integration for batch execution tracking
"""

import logging
import json
from datetime import datetime

from mcp import types
from batch_executor import execute_batch_script, create_diagnostic_script
from database_batch import BatchDatabaseOperations

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of batch execution tools"""
    return [
        types.Tool(
            name="execute_batch_script",
            description="""Execute multi-command batch script on remote Linux server.

OUTPUT_MODE_GUIDANCE: Use output_mode='full' for diagnostic commands with expected concise output. Full output returns directly in the response for immediate analysis.

LOG_FILE_LOCATION: Script output is automatically saved to the local user's home directory:
- %USERPROFILE%\mcp_batch_logs\batch_output_[timestamp].log

Use Aspen tools (apsen-tool_v2:read_file) with project root ~\mcp_batch_logs to access saved log files for post-execution analysis—for example, extracting specific error context, parsing structured data, debugging by reading lines around errors, or processing log entries for analysis. Do not use bash/Linux tools to access local log files; use Aspen tools for local file system access.

Workflow:
1. Pre-authenticate sudo if script contains sudo commands
2. Upload script to remote /tmp directory
3. Set executable permissions
4. Execute script with output logging (AI blocks here)
5. Download log file to local machine
6. Parse output and return structured results

User sees live progress in terminal. AI is blocked until completion.
Parsing happens AFTER execution completes.

OUTPUT_MODE:
- "summary" (default): Steps, errors, execution time + preview (first/last 10 lines)
  Token efficient. Log file saved locally for later analysis if needed.
- "full": Includes complete output in response (for diagnostics where AI needs to analyze output)
  Uses more tokens but gives AI all data in one round trip.

Example script format:
#!/bin/bash
echo "=== [STEP 1/3] Check interfaces ==="
ip link show
echo "[STEP_1_COMPLETE]"

echo "=== [STEP 2/3] Check routing ==="
ip route show
echo "[STEP_2_COMPLETE]"

echo "=== [STEP 3/3] Check DNS ==="
cat /etc/resolv.conf
echo "[STEP_3_COMPLETE]"
echo "[ALL_DIAGNOSTICS_COMPLETE]"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_content": {
                        "type": "string",
                        "description": "Complete bash script content with step markers"
                    },
                    "description": {
                        "type": "string",
                        "description": "What this script does (for logging/tracking)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max execution time in seconds (default: 300 = 5 min)",
                        "default": 300
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output format: summary (efficient, default) or full (includes complete output)",
                        "enum": ["summary", "full"],
                        "default": "summary"
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Link batch to conversation for tracking"
                    }
                },
                "required": ["script_content", "description"]
            }
        ),
        types.Tool(
            name="create_diagnostic_script",
            description="""Helper tool to create a diagnostic batch script from command list.

Useful for AI to quickly build properly formatted scripts.

Example:
commands = [
    {"description": "Network interfaces", "command": "ip link show"},
    {"description": "Routing table", "command": "ip route show"},
    {"description": "DNS config", "command": "cat /etc/resolv.conf"}
]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "description": "List of command objects with 'description' and 'command' fields",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "command": {"type": "string"}
                            },
                            "required": ["description", "command"]
                        }
                    },
                    "description": {
                        "type": "string",
                        "description": "Overall script description",
                        "default": "Diagnostics"
                    }
                },
                "required": ["commands"]
            }
        )
    ]


async def handle_call(name: str, arguments: dict, shared_state, config, web_server, database=None, **kwargs) -> list[types.TextContent]:
    """Handle batch execution tool calls - with database integration"""
    
    if name == "execute_batch_script":
        return await _execute_batch_script(
            arguments.get("script_content"),
            arguments.get("description"),
            arguments.get("timeout", 300),
            arguments.get("output_mode", "summary"),
            shared_state,
            config,
            web_server,
            database,
            arguments.get("conversation_id")  
        )
    
    elif name == "create_diagnostic_script":
        return await _create_diagnostic_script(
            arguments.get("commands"),
            arguments.get("description", "Diagnostics")
        )
    
    # Not our tool, return None
    return None


async def _execute_batch_script(
    script_content: str,
    description: str,
    timeout: int,
    output_mode: str,
    shared_state,
    config,
    web_server,
    database=None,
    conversation_id=None 
) -> list[types.TextContent]:
    """Execute batch script on remote server with database tracking"""
    
    # Check if connected to server
    if not shared_state.ssh_manager or not shared_state.ssh_manager.is_connected():
        return [types.TextContent(
            type="text",
            text="Error: Not connected to any server. Use select_server first."
        )]
    
    # Check database connection
    if database and not database.is_connected():
        logger.warning("Database not connected, will execute batch but skip DB saving")
        database = None
    
    # ====================================================================
    # PHASE 1: BEFORE EXECUTION - Create batch execution record
    # ====================================================================
    
    batch_db = None
    batch_id = None
    script_id = None
    script_filename = None
    
    if database:
        try:
            batch_db = BatchDatabaseOperations(database)
            machine_id = shared_state.current_machine_id
            
            if machine_id:
                # Calculate content hash for deduplication
                import hashlib
                content_hash = hashlib.sha256(script_content.encode()).hexdigest()
                
                # STEP 1: Check if this exact script already exists in database
                cursor = database.conn.cursor()
                cursor.execute("""
                    SELECT id, name FROM batch_scripts 
                    WHERE content_hash = ?
                    LIMIT 1
                """, (content_hash,))
                existing_script = cursor.fetchone()
                
                if existing_script:
                    # DEDUPLICATION: Reuse existing script
                    script_id = existing_script[0]
                    script_filename = existing_script[1]
                    
                    # Increment usage counter
                    cursor.execute("""
                        UPDATE batch_scripts 
                        SET times_used = times_used + 1,
                            last_used_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (script_id,))
                    database.conn.commit()
                    
                    logger.info(f"REUSING existing script: {script_filename} (id={script_id}, hash={content_hash[:16]}...)")
                else:
                    # New unique script - generate timestamp filename
                    script_filename = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sh"
                    script_id = None  # Will be created in Phase 3
                    logger.info(f"NEW script: {script_filename} (hash={content_hash[:16]}...)")
                
                # STEP 2: Create batch_execution record (ALWAYS NEW - tracks each run)
                batch_id = batch_db.create_batch_execution(
                    machine_id=machine_id,
                    script_name=script_filename,
                    created_by="claude",
                    conversation_id=conversation_id
                )
                
                if batch_id:
                    # STEP 3: Save script to batch_scripts table ONLY if new
                    if script_id is None:
                        script_id = batch_db.save_batch_script(
                            batch_execution_id=batch_id,
                            source_code=script_content,
                            description=description,
                            filename=script_filename,
                            content_hash=content_hash
                        )
                        logger.info(f"Saved NEW script to DB: id={script_id}")
                    else:
                        logger.info(f"Skipped save - script {script_id} already in DB")
                else:
                    logger.error("Failed to create batch execution record")
                    database = None
            else:
                logger.warning("No machine_id available, skipping batch DB record")
                database = None
        except Exception as e:
            logger.error(f"Error in Phase 1 (batch setup): {e}")
            database = None
    
    
    # ====================================================================
    # PHASE 2: EXECUTE THE BATCH SCRIPT
    # ====================================================================
    
    # Import the sophisticated command execution from tools.tools_commands
    from tools.tools_commands import _execute_command, pre_authenticate_sudo
    
    # Create SFTP wrappers (synchronous)
    def upload_wrapper(local_path, remote_path):
        try:
            sftp = shared_state.ssh_manager.get_sftp()
            sftp.put(local_path, remote_path)
            return {"success": True}
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {"success": False, "error": str(e)}
    
    def download_wrapper(remote_path, local_path):
        try:
            sftp = shared_state.ssh_manager.get_sftp()
            # Ensure local directory exists
            import os
            local_dir = os.path.dirname(local_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
            sftp.get(remote_path, local_path)
            return {"success": True}
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return {"success": False, "error": str(e)}
    
    # Create async execute wrapper using _execute_command
    async def execute_wrapper(command, timeout, output_mode="auto"):
        """
        Uses the sophisticated _execute_command that:
        - Waits for prompt return (real completion detection)
        - Monitors buffer continuously
        - Supports output_mode
        - Handles timeouts properly
        """
        result_content = await _execute_command(
            shared_state=shared_state,
            config=config,
            command=command,
            timeout=timeout,
            output_mode=output_mode,
            web_server=web_server
        )
        # _execute_command returns list[TextContent], extract the JSON text
        return result_content[0].text
    
    # Create async preauth wrapper
    async def preauth_wrapper(script_content):
        """Pre-authenticate sudo if script contains sudo commands"""
        return await pre_authenticate_sudo(
            shared_state=shared_state,
            config=config,
            web_server=web_server,
            command=script_content  # Pass script to check for sudo
        )
    
    # Execute batch script
    result = await execute_batch_script(
        script_content=script_content,
        description=description,
        timeout=timeout,
        output_mode=output_mode,
        upload_file_func=upload_wrapper,
        download_file_func=download_wrapper,
        execute_command_func=execute_wrapper,
        preauth_sudo_func=preauth_wrapper
    )
    
    # ====================================================================
    # PHASE 3: AFTER EXECUTION - Update batch + save command
    # ====================================================================
    
    if batch_db and batch_id and database:
        try:
            # Determine final status
            execution_status = result.get("status", "completed")
            exit_code = result.get("exit_code")
            output_file_path = result.get("local_log_file")
            
            
            # Map execution status to batch status
            if execution_status == "timeout":
                batch_status = "timeout"
            elif result.get("error_detected"):
                batch_status = "failed"  # Has errors, mark as failed
            elif execution_status == "completed" and (exit_code == 0 or exit_code is None):
                batch_status = "success"
            else:
                batch_status = "failed"
                        
            
            # Update batch execution with steps and duration
            #logger.info(f"DEBUG result keys: {result.keys()}")
            #logger.info(f"DEBUG execution_time field: {result.get('execution_time')}")
            #logger.info(f"DEBUG steps_completed field: {result.get('steps_completed')}")

            steps_str = str(result.get('steps_completed', '0'))
            if '/' in steps_str:
                parts = steps_str.split('/')
                completed_steps = int(parts[0])
                total_steps = int(parts[1])
            else:
                completed_steps = int(steps_str or 0)
                total_steps = 0

            
            # Try multiple possible field names for execution time
            execution_time = float(result.get('execution_time_seconds') or result.get('execution_time') or result.get('duration') or 0)
            execution_time = round(execution_time, 1)  # Round to 1 decimal places
            # logger.info(f"DEBUG parsed execution_time: {execution_time}")


            # Update step progress with BOTH completed and total
            if completed_steps > 0:
                # Update completed_steps
                batch_db.update_batch_progress(batch_id, completed_steps)
                # Update total_steps separately
                cursor = database.conn.cursor()
                cursor.execute("UPDATE batch_executions SET total_steps = ? WHERE id = ?", (total_steps, batch_id))
                database.conn.commit()


            # Complete batch execution with duration
            batch_db.complete_batch_execution(
                batch_id=batch_id,
                status=batch_status,
                duration_seconds=execution_time
            )
                  
            # logger.info(f"DEBUG RAW duration from result: {result.get('duration')}")
            # logger.info(f"DEBUG RAW execution_time_seconds: {result.get('execution_time_seconds')}")
            # raw_dur = result.get('duration', 0)
            # logger.info(f"DEBUG before float conversion: {raw_dur}, type: {type(raw_dur)}")
            # execution_time = float(result.get('execution_time_seconds') or result.get('execution_time') or result.get('duration') or 0)
            # logger.info(f"DEBUG after float conversion, before rounding: {execution_time}")
            # execution_time = round(execution_time, 2)
            # logger.info(f"DEBUG after rounding: {execution_time}")     
                              
            # Extract actual script filename from remote path
            remote_script = result.get('remote_script_file', '/tmp/batch_script_unknown.sh')
            # Save the bash script command to commands table
            # ONE row per batch execution (not individual script steps)
            # Save the bash script command to commands table
            command_id = database.add_command(
                machine_id=shared_state.current_machine_id,
                conversation_id=conversation_id,
                command_text=f"bash {remote_script}",
                result_output=result.get("output_preview", {}).get("last_lines", ""),
                status="executed",
                exit_code=exit_code,
                has_errors=result.get("error_detected", False),
                error_context=result.get("error_summary"),
                line_count=result.get("output_preview", {}).get("total_lines", 0)
            )
            
            # Link command to batch and increment usage
            if command_id:
                # Link command to batch execution
                if batch_db.link_command_to_batch(command_id, batch_id):
                    logger.info(f"Linked command {command_id} to batch {batch_id}")
                
                # Increment script usage counter
                if script_filename and batch_db.increment_script_usage(script_filename):
                    logger.debug(f"Incremented usage for script: {script_filename}")
                                
            # Add tracking info to result
            result["tracking"] = {
                "batch_execution_id": batch_id,
                "batch_script_id": script_id,
                "command_id": command_id,
                "database_saved": True,
                "batch_status": batch_status
            }
            
            if command_id:
                logger.info(f"Saved batch {batch_id} as command {command_id}")
            else:
                logger.warning(f"Failed to save command for batch {batch_id}")
                result["tracking"]["database_saved"] = False
                result["tracking"]["error"] = "Failed to save command"
        
        except Exception as e:
            logger.error(f"Error in Phase 3 (batch update): {e}")
            result["tracking"] = {
                "batch_execution_id": batch_id,
                "database_saved": False,
                "error": str(e)
            }
    
    # Format response for AI
    if result["status"] == "completed":
        response_text = _format_success_response(result)
    else:
        response_text = _format_error_response(result)
    
    return [types.TextContent(type="text", text=response_text)]


async def _create_diagnostic_script(commands: list, description: str) -> list[types.TextContent]:
    """Create diagnostic script from command list"""
    
    try:
        script = create_diagnostic_script(commands, description)
        return [types.TextContent(
            type="text",
            text=f"Generated diagnostic script:\n\n```bash\n{script}\n```"
        )]
    except Exception as e:
        logger.error(f"Error creating script: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error creating script: {str(e)}"
        )]


def _format_success_response(result: dict) -> str:
    """Format successful execution response for AI."""
    
    lines = [
        f"Batch script completed: {result['description']}",
        f"  Execution time: {result['execution_time_formatted']}",
        f"  Steps completed: {result['steps_completed']}",
    ]
    
    if result.get("all_complete"):
        lines.append("  Status: All diagnostics complete")
    
    if result.get("error_detected"):
        lines.append(f"  Errors detected: {result.get('error_summary', 'See output')}")
    
    # Add database tracking info if available
    if result.get("tracking", {}).get("database_saved"):
        tracking = result["tracking"]
        lines.append(f"  Database: batch_id={tracking.get('batch_execution_id')}, command_id={tracking.get('command_id')}")
    
    lines.extend([
        "",
        f"Log saved to: {result['local_log_file']}",
        ""
    ])
    
    # Include full output or preview based on output_mode
    if result.get('full_output'):
        # output_mode="full" - Include entire log content
        lines.extend([
            "Complete output:",
            "=" * 80,
            result['full_output'],
            "=" * 80
        ])
    else:
        # output_mode="summary" - Show preview only (token efficient)
        lines.extend([
            "Output preview (first 10 lines):",
            "---",
            result['output_preview']['first_lines'],
            "---",
            "",
            "Output preview (last 10 lines):",
            "---",
            result['output_preview']['last_lines'],
            "---"
        ])
    
    return '\n'.join(lines)


def _format_error_response(result: dict) -> str:
    """Format error response for AI."""
    
    lines = [
        f"Batch script failed: {result['description']}",
        f"  Status: {result['status']}",
        f"  Error: {result.get('error', 'Unknown error')}"
    ]
    
    if result.get('local_log_file'):
        lines.append(f"  Partial log may be at: {result['local_log_file']}")
    
    if result.get("tracking", {}).get("database_saved"):
        lines.append(f"  Batch execution recorded in database: {result['tracking'].get('batch_execution_id')}")
    
    return '\n'.join(lines)
