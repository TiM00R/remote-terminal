"""
Command Execution - Core execution logic
Low-level command execution without pre-auth, backup, or database saving
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from mcp import types
from command_state import CommandState, generate_command_id
from shared_state import monitor_command
from output.output_formatter import format_output

logger = logging.getLogger(__name__)


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
