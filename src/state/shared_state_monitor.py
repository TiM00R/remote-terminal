"""
Command monitoring for shared terminal state
Background monitoring of command execution
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


def monitor_command(command_id: str, shared_state):
    """
    Background thread to monitor command completion

    CRITICAL: Continues monitoring even after timeout until:
    - Prompt detected (completed/cancelled)
    - cancel_command() called (killed)
    - Max monitoring time reached (1 hour)

    Detects Ctrl+C (^C in output) and marks as cancelled vs completed

    Args:
        command_id: Command ID to monitor
        shared_state: SharedTerminalState instance
    """
    state = shared_state.command_registry.get(command_id)
    if not state:
        logger.error(f"Command {command_id} not found in registry")
        return

    check_interval = shared_state.config.command_execution.check_interval
    prompt_pattern = state.expected_prompt
    max_monitoring_time = shared_state.config.command_execution.max_timeout

    logger.debug(f"Monitoring command {command_id}: {state.command[:50]}...")

    # CRITICAL: Continue monitoring while is_running() returns True
    # This includes both "running" and "timeout_still_running" states

    # Add this BEFORE the while loop starts
    last_sudo_response_line_count = 0  # Track buffer size when we last responded to sudo

    while state.is_running():
        time.sleep(check_interval)

        # NEW CODE - Check for sudo password prompt
        if shared_state.prompt_detector.is_sudo_prompt(shared_state.buffer.buffer):
            current_line_count = len(shared_state.buffer.buffer.lines)

            # Only respond if buffer has grown since last response (new prompt, not same one)
            if current_line_count > last_sudo_response_line_count:
                if shared_state.ssh_manager.password:
                    logger.info(f"Auto-responding to sudo password prompt, current_line_count={current_line_count}, last_sudo_response_line_count={last_sudo_response_line_count} ")
                    shared_state.ssh_manager.shell.send(shared_state.ssh_manager.password + '\n')
                    last_sudo_response_line_count = current_line_count  # Remember this line count
                    time.sleep(0.5)  # Wait for password to be processed
                    continue  # Skip to next iteration
        # END NEW CODE

        # Check for max monitoring time (1 hour default)
        if state.duration() >= max_monitoring_time:
            buffer_end_line = len(shared_state.buffer.buffer.lines)
            state.mark_max_timeout(buffer_end_line)
            logger.warning(f"Command {command_id} exceeded max monitoring time ({max_monitoring_time}s)")
            break

        # Check for prompt in buffer
        try:
            # Run async check in sync context
            loop = asyncio.new_event_loop()
            completed, reason = loop.run_until_complete(
                shared_state.prompt_detector.check_completion(
                    shared_state.buffer,
                    prompt_pattern
                )
            )
            loop.close()

            if completed:
                # Prompt detected! Check if it was due to Ctrl+C
                buffer_end_line = len(shared_state.buffer.buffer.lines)

                # Check recent output for ^C (Ctrl+C character)
                # Get last few lines before prompt
                recent_output = shared_state.buffer.buffer.get_text(
                    start=max(0, buffer_end_line - 5),
                    end=buffer_end_line
                )

                # Also check current_output (partial line with prompt)
                if hasattr(shared_state.buffer.buffer, 'current_output'):
                    recent_output += shared_state.buffer.buffer.current_output

                # Detect Ctrl+C in output
                if '^C' in recent_output:
                    # Command was interrupted with Ctrl+C
                    state.mark_cancelled(buffer_end_line)
                    logger.info(f"Command {command_id} cancelled (Ctrl+C detected) after {state.duration():.1f}s")
                else:
                    # Command completed naturally
                    state.mark_completed(buffer_end_line)
                    logger.info(f"Command {command_id} completed ({reason}) after {state.duration():.1f}s")
                break

        except Exception as e:
            logger.error(f"Error monitoring command {command_id}: {e}")
            break

    logger.debug(f"Stopped monitoring command {command_id} (status: {state.status})")
