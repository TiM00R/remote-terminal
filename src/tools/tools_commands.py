"""
Command Execution Tools
Tools for executing and managing commands on remote servers
Phase 1 Enhanced: Conversation workflow automation
"""

import asyncio
import json
import time
import logging
import re
import shlex
from datetime import datetime
from mcp import types
from command_state import CommandState, generate_command_id
from shared_state import monitor_command
from output_formatter import format_output
from utils import is_error_output, extract_error_context, count_lines

logger = logging.getLogger(__name__)


async def get_tools(**kwargs) -> list[types.Tool]:
    """Get list of command execution tools"""
    return [
        types.Tool(
            name="execute_command",
            description="""Execute command on remote Linux machine with smart completion detection.
                
BEHAVIOR:
- Waits for command completion (detects prompt return) OR timeout
- Returns smart-formatted output based on output_mode
- Full output stored in buffer
- Optionally tracks in conversation for rollback support

TIMEOUT:
- Default: 10 seconds (sufficient for most commands)
- Override for long operations: timeout=300 (5 min), timeout=1800 (30 min)
- Maximum: 3600 seconds (1 hour)

OUTPUT_MODE OPTIONS:
- "auto" (default): Smart output based on command type and size
  * < 100 lines: returns full output
  * >= 100 lines: returns preview only
  * Installation commands with errors: returns error contexts
  * Installation commands without errors: returns last 10 lines
- "full": Always return complete output
- "preview": First 10 + last 10 lines only
- "summary": Metadata only (line count, error flag)
- "minimal": Status + buffer_info only
- "raw": Complete unfiltered output (no truncation, no filtering)

CONVERSATION TRACKING:
- conversation_id (optional): Associate command with conversation for tracking
- If provided: command saved with conversation for rollback support
- If omitted: Behavior depends on user's conversation mode choice:
  * "in-conversation" mode: conversation_id auto-injected
  * "no-conversation" mode: command saved standalone
  * No mode set: Commands run standalone (default behavior)

⚠️ CONVERSATION MODE WORKFLOW:
- User's mode choice persists for ALL commands on current server
- Mode is set when: select_server (user chooses), start_conversation, or user explicitly sets "no-conversation"
- Mode is cleared when: switching servers, new Claude dialog
- Claude should NEVER ask before each command - the mode handles it automatically

RETURN VALUES:
- status="completed": Command finished
- status="cancelled": User interrupted with Ctrl+C
- status="timeout_still_running": Exceeded timeout, still executing
- status="backgrounded": Command backgrounded with &
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute"
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Maximum seconds to wait (default: 10, max: 3600)",
                        "default": 10
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output format: auto, full, preview, summary, minimal, raw",
                        "enum": ["auto", "full", "preview", "summary", "minimal", "raw"],
                        "default": "auto"
                    },
                    "conversation_id": {
                        "type": "integer",
                        "description": "Optional: Associate command with conversation for tracking and rollback"
                    }
                },
                "required": ["command"]
            }
        ),
        types.Tool(
            name="check_command_status",
            description="""Check status of a long-running command.

            OUTPUT_MODE: Same options as execute_command
            - "auto": Smart decision based on output size
            - "full": Get complete output (for completed commands)
            - "preview": Peek at first/last lines
            - "summary": Just metadata (polling frequently)
            - "minimal": Status only
            - "raw": Complete unfiltered output (no truncation, no filtering)
            
            Use "summary" or "minimal" when polling frequently to save tokens.
            Use "full" when command completes and you need results.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {
                        "type": "string",
                        "description": "Command ID returned by execute_command"
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output format: auto, full, preview, summary, minimal, raw",
                        "enum": ["auto", "full", "preview", "summary", "minimal", "raw"],
                        "default": "auto"
                    }
                },
                "required": ["command_id"]
            }
        ),
        types.Tool(
            name="get_command_output",
            description="Get full unfiltered output of a command. WARNING: Uses more tokens than filtered output.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {
                        "type": "string",
                        "description": "Command ID"
                    },
                    "raw": {
                        "type": "boolean",
                        "description": "If true, returns completely unfiltered output",
                        "default": False
                    }
                },
                "required": ["command_id"]
            }
        ),
        types.Tool(
            name="cancel_command",
            description="Send Ctrl+C to a running command. Use when user wants to stop a long-running command.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command_id": {
                        "type": "string",
                        "description": "Command ID to cancel"
                    }
                },
                "required": ["command_id"]
            }
        ),
        types.Tool(
            name="list_commands",
            description="List all tracked commands with status. Useful for seeing what's running or recently completed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "description": "Optional: 'running', 'completed', or 'killed'",
                        "enum": ["running", "completed", "killed"]
                    }
                }
            }
        )
    ]


async def handle_call(name: str, arguments: dict, shared_state, config, web_server, database=None, **kwargs) -> list[types.TextContent]:
    """Handle command execution tool calls - Phase 1 Enhanced"""
    
    if name == "execute_command":
        # Auto-inject conversation_id if user is in "in-conversation" mode
        conversation_id = arguments.get("conversation_id")
        if conversation_id is None:
            # Check if user has chosen a conversation mode
            auto_conv_id = shared_state.get_auto_conversation_id()
            if auto_conv_id is not None:
                conversation_id = auto_conv_id
                logger.debug(f"Auto-injected conversation_id: {conversation_id}")
        
        return await execute_command_with_track(
            shared_state, config, web_server,
            arguments["command"],
            arguments.get("timeout", 10),
            arguments.get("output_mode", "auto"),
            database=database,
            conversation_id=conversation_id
        )
    
    elif name == "check_command_status":
        return await _check_command_status(
            shared_state, config,
            arguments["command_id"],
            arguments.get("output_mode", "auto")
        )
    
    elif name == "get_command_output":
        return await _get_command_output(
            shared_state,
            arguments["command_id"],
            arguments.get("raw", False)
        )
    
    elif name == "cancel_command":
        return await _cancel_command(
            shared_state,
            arguments["command_id"]
        )
    
    elif name == "list_commands":
        return await _list_commands(
            shared_state,
            arguments.get("status_filter")
        )
    
    # Not our tool, return None
    return None


async def execute_command_with_track(shared_state, config, web_server, command: str, timeout: int, 
                                     output_mode: str, database=None, conversation_id=None) -> list[types.TextContent]:
    """
    HIGH-LEVEL command execution with safety features and tracking
    This is called by AI/Claude through MCP
    
    Features:
    - Pre-authenticates sudo (ALWAYS for ALL sudo commands)
    - Creates backups (ALWAYS for ALL file-modifying commands)
    - Executes command via basic _execute_command()
    - Saves to database with tracking info
    - Auto-injects conversation_id based on user's mode choice
    """
    
    # Start web server on first command if not already running
    if not web_server.is_running():
        web_server.start()
    
    if not shared_state.is_connected() or not shared_state.ssh_manager:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Not connected to remote machine. Use select_server to connect.",
                "status": "failed"
            })
        )]
    
    # Validate timeout
    max_timeout = config.command_execution.max_timeout
    if timeout > max_timeout:
        return [types.TextContent(
            type="text",
            text=f"ERROR: Timeout {timeout}s exceeds maximum {max_timeout}s"
        )]
    
    # Warn about long timeouts
    if timeout > config.command_execution.warn_on_long_timeout:
        logger.warning(f"Long timeout requested: {timeout}s for command: {command}")
    
    # PHASE 1: Pre-authenticate sudo if needed (ALWAYS, not just for conversations)
    preauth_result = await pre_authenticate_sudo(shared_state, config, web_server, command)
    
    # PHASE 1: Create backup if needed (ALWAYS, not just for conversations)
    backup_result = await create_backup_if_needed(shared_state, config, web_server, command)
    
    # Execute the actual command using basic internal function
    result_content = await _execute_command(shared_state, config, command, timeout, 
                                            output_mode, web_server)
    
    # Parse result to add tracking info
    result = json.loads(result_content[0].text)
    
    # PHASE 1: Save to database if connected
    if database and database.is_connected():
        await _save_to_database(
            database, shared_state, command, 
            result.get("output", result.get("raw_output", "")),
            result.get("status", "completed"),
            conversation_id, preauth_result, backup_result, result
        )
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]




 
async def _execute_command(shared_state, config, command: str, timeout: int, 
                          output_mode: str, web_server=None, 
                          custom_prompt_pattern: str = None) -> list[types.TextContent]:
    """
    LOW-LEVEL basic command execution (INTERNAL USE ONLY)
    
    NO pre-auth, NO backup, NO database saving
    Used by:
    - pre_authenticate_sudo() 
    - create_backup_if_needed()
    - execute_command_with_track() for the actual user command
    """
    
    # If custom pattern provided, use it; otherwise use prompt_detector's pattern
    if custom_prompt_pattern:
        expected_prompt = custom_prompt_pattern
    else:
        expected_prompt = shared_state.prompt_detector.get_current_prompt()
    
    # Start web server on first command if not already running
    if not web_server.is_running():
        web_server.start()
        
    try:
        # Generate command ID
        command_id = generate_command_id()
        
        # Check for background command
        is_background = shared_state.prompt_detector.is_background_command(command)

        # Get expected prompt
        # expected_prompt = shared_state.prompt_detector.get_current_prompt()

        # Check for prompt-changing command
        new_prompt = shared_state.prompt_detector.detect_prompt_changing_command(command)

        # Create command state
        command_state = CommandState(
            command_id=command_id,
            command=command,
            timeout=timeout,
            expected_prompt=expected_prompt,
            buffer_start_line=len(shared_state.buffer.buffer.lines),
            prompt_changed=new_prompt is not None,
            new_prompt_pattern=new_prompt
        )
        
        # Add to registry
        shared_state.command_registry.add(command_state)
        
        # Mark command start in buffer
        shared_state.buffer.start_command(command)

        # REMOVED: HistoryManager unused (bash handles history)
        # if shared_state.history:
        #     shared_state.history.add(command)

        # Send command
        shared_state.ssh_manager.send_input(command + '\n')

        # Start monitoring thread
        import threading
        monitor_thread = threading.Thread(
            target=monitor_command,
            args=(command_id,),
            daemon=True
        )
        monitor_thread.start()
        
        # Wait loop with prompt detection
        start_time = time.time()
        check_interval = config.command_execution.check_interval
        grace_period = config.command_execution.prompt_grace_period
        
        while True:
            elapsed = time.time() - start_time
            
            # Check command state
            current_state = shared_state.command_registry.get(command_id)
            
            # Check if command finished
            if current_state and not current_state.is_running():
                # Command completed! Wait grace period for trailing output
                await asyncio.sleep(grace_period)
                
                # Get output
                output = shared_state.buffer.get_command_output()
                
                # Format output based on mode
                output_data = format_output(
                    command=command,
                    output=output,
                    status=current_state.status,
                    output_mode=output_mode,
                    config=config,
                    output_filter=shared_state.filter 
                )
                
                result = {
                    "command_id": command_id,
                    "status": current_state.status,
                    "duration": current_state.duration(),
                    **output_data
                }
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            
            # Check timeout
            if elapsed >= timeout:
                # Only mark timeout if monitoring hasn't already finished
                if current_state and current_state.is_running():
                    current_state.mark_timeout()
                
                # Get partial output
                output = shared_state.buffer.get_command_output()
                
                # For timeouts, use preview/summary mode
                effective_mode = output_mode if output_mode != "full" else "preview"
                
                output_data = format_output(
                    command=command,
                    output=output,
                    status="timeout_still_running",
                    output_mode=effective_mode,
                    config=config
                )
                
                result = {
                    "command_id": command_id,
                    "status": "timeout_still_running",
                    "duration": elapsed,
                    **output_data,
                    "message": f"Command running. Use check_command_status('{command_id}', output_mode='...') to check."
                }
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            
            # Check for background command
            if is_background and elapsed > 2:
                result = {
                    "command_id": command_id,
                    "status": "backgrounded",
                    "message": "Command backgrounded (&). Process running but prompt returned.",
                    "duration": elapsed
                }
                current_state.status = "backgrounded"
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            
            # Continue waiting
            await asyncio.sleep(check_interval)
            
    except Exception as e:
        logger.error(f"Error executing command: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"ERROR executing command: {str(e)}"
        )]


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


async def pre_authenticate_sudo(shared_state, config, web_server, command: str) -> dict:
    """Pre-authenticate sudo in main session"""
    if 'sudo' not in command or not shared_state.ssh_manager or not shared_state.ssh_manager.password:
        return {"status": "skipped", "reason": "no sudo in command"}
    
    # ========== ADD THESE 5 LINES HERE ==========
    # Check if preauth still valid
    validity_seconds = config._raw_config.get('sudo', {}).get('preauth_validity_seconds', 300)
    if not shared_state.should_preauth_sudo(validity_seconds):
        logger.debug(f"Sudo preauth still valid, skipping")
        return {"status": "skipped", "reason": "preauth still valid"}
    # ========== END NEW LINES ==========
    
    start_time = time.time()
    try:
        pw = shared_state.ssh_manager.password
        pw_esc = pw.replace('\\', '\\\\').replace('"', '\\"')
        
        preauth = (
            ' {{ printf \'%s\\n\' "{pw}" | sudo -S -v >/dev/null 2>&1; rc=$?; '
            'if [ $rc -eq 0 ]; then echo __SUDO_AUTH_OK__; '
            'else echo __SUDO_AUTH_FAIL__:RC=$rc; fi; }}; '
            'if [ -n "$HISTCMD" ] && type history >/dev/null 2>&1; then '
            'history -d $((HISTCMD-1)) 2>/dev/null || true; '
            'fi'
        ).format(pw=pw_esc)
        
        logger.info("Pre-authenticating sudo")
        if not web_server.is_running():
            web_server.start()
        
        # Use BASIC _execute_command (no recursion!)
        preauth_result = await _execute_command(
            shared_state, config, preauth, 5, "raw", web_server
        )
        
        # Clear the pre-auth lines from terminal
        lines_to_clear = 5
        await asyncio.sleep(0.5)
        clear_sequence = '\\033[1A\\033[2K' * lines_to_clear
        printf_cmd = f"printf $'{clear_sequence}'"
       
        shared_state.ssh_manager.shell.send(printf_cmd+'\n')
        await asyncio.sleep(0.1)
        
        preauth_json = json.loads(preauth_result[0].text)
        raw_output = preauth_json.get("raw_output", "")
        duration = time.time() - start_time
        
        clean_output = raw_output.replace("\r", " ").strip()
        match = re.search(r'__(SUDO_AUTH_OK__|SUDO_AUTH_FAIL__)(?::RC=(\d+))?', clean_output)
        
        if match:
            status_tag = match.group(1)
            rc_value = match.group(2)
            
            if status_tag == "SUDO_AUTH_OK__":
                # Mark successful preauth
                shared_state.mark_sudo_preauth()
                return {"status": "success", "duration": duration}
            else:
                return {
                    "status": "failed",
                    "duration": duration,
                    "error": f"Incorrect sudo password (rc={rc_value or 'unknown'})"
                }
        
        logger.warning("No preauth sentinel found in output:\n%s", clean_output)
        return {
            "status": "failed",
            "duration": duration,
            "error": f"No sudo confirmation received. {clean_output}",
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Sudo pre-auth failed: {e}")
        return {"status": "failed", "duration": duration, "error": str(e)}






async def create_backup_if_needed(shared_state, config, web_server, command: str) -> dict:
    """Detect if command modifies/creates a file and back it up first"""
    
    file_patterns = [
        (r'^\s*(?:sudo\s+)?(?:sed|awk)\b.*?-i(?:\s*\S+)?\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?(?:nano|vi|vim|emacs)\b.*\s+(\S+)$', 1),
        (r'^\s*(?:.*\|\s*)?(?:sudo\s+)?echo\b.*>>\s*(\S+)$', 1),
        (r'^\s*(?:.*\|\s*)?(?:sudo\s+)?echo\b.*>\s*(\S+)$', 1),
        (r'^\s*(?:.*\|\s*)?(?:sudo\s+)?cat\b.*>\s*(\S+)$', 1),
        (r'^\s*(?:.*\|\s*)?(?:sudo\s+)?printf\b.*>\s*(\S+)$', 1),
        (r'^\s*(?:.*\|\s*)?(?:sudo\s+)?tee\b(?:\s+[-\w]+)*\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?cp\b.*\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?mv\b.*\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?install\b.*\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?ln\b.*\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?touch\b.*\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?truncate\b.*\s+(\S+)$', 1),
        (r'^\s*(?:sudo\s+)?dd\b.*\bof=(\S+)', 1),
    ]
    
    # Detect target file path
    file_path = None
    for pattern, idx in file_patterns:
        m = re.match(pattern, command)
        if m:
            file_path = m.group(idx).strip()
            break
    
    if not file_path:
        return {"status": "skipped", "reason": "command does not modify files"}
    
    qpath = shlex.quote(file_path)
    
    # Check if target exists - use BASIC _execute_command (no recursion!)
    check_cmd = f'sudo test -e {qpath}; rc=$?; ' \
                f'if [ $rc -eq 0 ]; then echo __TARGET_EXISTS__; else echo __TARGET_NOTFOUND__; fi'
    
    check_res = await _execute_command(shared_state, config, check_cmd, 5, "raw", web_server)
    check_json = json.loads(check_res[0].text)
    raw_output = check_json.get("raw_output", "")
    clean = raw_output.replace("\r", "")
    
    exists_count = clean.count("__TARGET_EXISTS__")
    notfound_count = clean.count("__TARGET_NOTFOUND__")
    
    if exists_count >= 2:
        pass  # File exists, proceed to backup
    elif notfound_count >= 2:
        return {"status": "skipped", "reason": "file does not exist", "file_path": file_path}
    else:
        logger.info("Unexpected check output: %s", clean)
        return {"status": "failed", "error": f"Unknown check result. {clean}"}
    
    # Create backup - use BASIC _execute_command (no recursion!)
    ts = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    backup_path = f"{file_path}.backup-{ts}"
    qbackup = shlex.quote(backup_path)
    
    backup_cmd = f"sudo cp -p {qpath} {qbackup}"
    backup_res = await _execute_command(shared_state, config, backup_cmd, 10, "raw", web_server)
    
    # Verify backup - use BASIC _execute_command (no recursion!)
    verify_cmd = f'sudo test -e {qbackup}; rc=$?; ' \
                f'if [ $rc -eq 0 ]; then echo __BACKUP_OK__; else echo __BACKUP_FAIL__; fi'
    verify_res = await _execute_command(shared_state, config, verify_cmd, 5, "raw", web_server)
    v_payload = json.loads(verify_res[0].text)
    v_raw = v_payload.get("raw_output", "").replace("\r", " ")
    
    backup_ok_count = v_raw.count("__BACKUP_OK__")
    backup_fail_count = v_raw.count("__BACKUP_FAIL__")
    
    if backup_ok_count >= 2:
        return {
            "status": "success",
            "backup_created": True,
            "file_path": file_path,
            "backup_path": backup_path
        }
    elif backup_fail_count >= 2:
        return {
            "status": "failed",
            "backup_created": False,
            "file_path": file_path,
            "backup_path": backup_path,
            "error": "Backup verification failed"
        }
    else:
        return {
            "status": "failed",
            "backup_created": False,
            "file_path": file_path,
            "backup_path": backup_path,
            "error": f"Unexpected verification result: {v_raw}"
        }


async def _check_command_status(shared_state, config, command_id: str, output_mode: str) -> list[types.TextContent]:
    """Check status of a command"""
    state = shared_state.command_registry.get(command_id)
    
    if not state:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Command ID not found"}, indent=2)
        )]
    
    if state.is_completed():
        output = shared_state.buffer.buffer.get_text(
            start=state.buffer_start_line,
            end=state.buffer_end_line
        )
        
        output_data = format_output(
            command=state.command,
            output=output,
            status=state.status,
            output_mode=output_mode,
            config=config
        )
        
        result = {
            "command_id": command_id,
            "status": state.status,
            "duration": state.duration(),
            **output_data
        }
    else:
        result = {
            "command_id": command_id,
            "status": state.status,
            "duration": state.duration(),
            "message": "Command still executing"
        }
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_command_output(shared_state, command_id: str, raw: bool) -> list[types.TextContent]:
    """Get command output (filtered or raw)"""
    state = shared_state.command_registry.get(command_id)
    
    if not state:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Command ID not found"}, indent=2)
        )]
    
    end_line = state.buffer_end_line if state.is_completed() else None
    output = shared_state.buffer.buffer.get_text(
        start=state.buffer_start_line,
        end=end_line
    )
    
    if raw:
        result = {
            "command_id": command_id,
            "raw_output": output,
            "line_count": output.count('\n'),
            "size_kb": len(output) / 1024
        }
    else:
        filtered = shared_state.filter.filter_output(state.command, output)
        result = {
            "command_id": command_id,
            "filtered_output": filtered
        }
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def _cancel_command(shared_state, command_id: str) -> list[types.TextContent]:
    """Cancel a running command"""
    state = shared_state.command_registry.get(command_id)
    
    if not state:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "Command ID not found"}, indent=2)
        )]
    
    if not state.is_running():
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Command not running (status: {state.status})"}, indent=2)
        )]
    
    shared_state.ssh_manager.send_interrupt()
    await asyncio.sleep(0.5)
    
    buffer_end_line = len(shared_state.buffer.buffer.lines)
    state.mark_killed(buffer_end_line)
    
    result = {
        "command_id": command_id,
        "action": "cancelled",
        "message": "Sent Ctrl+C signal to command"
    }
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def _list_commands(shared_state, status_filter: str = None) -> list[types.TextContent]:
    """List all commands"""
    if status_filter:
        commands = shared_state.command_registry.get_by_status(status_filter)
    else:
        commands = shared_state.command_registry.get_all()
    
    result = {
        "commands": [
            {
                "command_id": cmd.command_id,
                "command": cmd.command,
                "status": cmd.status,
                "duration": cmd.duration()
            }
            for cmd in commands
        ]
    }
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
