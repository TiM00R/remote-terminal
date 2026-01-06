"""
Machine ID Helper Functions
Fetch and validate machine IDs from remote servers
"""

import re
import time
import logging
import asyncio

logger = logging.getLogger(__name__)


async def fetch_machine_id_from_server(shared_state, web_server, host: str, port: int, user: str,
                                       force_check: bool = False) -> tuple[str, str, str]:
    """
    Fetch machine_id and hostname from server with retry logic and caching.

    This function handles the complete machine identity workflow:
    - Checks cache first (unless force_check=True)
    - Reads machine_id from remote /etc/machine-id with retry logic
    - Validates machine_id format
    - Creates fallback ID if reading fails
    - Caches valid machine_ids
    - Returns machine_id, identity_status, and hostname

    Args:
        shared_state: SharedTerminalState instance
        web_server: Web terminal server for command execution
        host: Server hostname/IP
        port: Server SSH port
        user: SSH username
        force_check: Force re-read even if cached

    Returns:
        Tuple of (machine_id, identity_status, hostname, warning_message)
        - machine_id: The machine ID (valid or fallback)
        - identity_status: "cached", "verified", "refreshed", or "unavailable"
        - hostname: Remote hostname
        - warning_message: Error message if fallback ID used, None otherwise
    """
    from tools.tools_commands import _execute_command
    import json

    # Generic pattern for internal commands
    GENERIC_PROMPT = r'^[^@\s:]+@[A-Za-z0-9.-]+:[^$#]*[$#]\s*$'

    machine_id = None
    identity_status = "unknown"
    hostname = ""
    warning_message = None

    # Check cache first (unless force check requested)
    if not force_check:
        cached_id = shared_state.get_cached_machine_id(host, port, user)
        if cached_id and shared_state.is_valid_machine_id(cached_id):
            machine_id = cached_id
            identity_status = "cached"
            logger.info(f"Using cached machine_id: {machine_id[:16]}...")

    # Fetch machine_id from server if not cached or force requested
    if machine_id is None or force_check:
        # Try up to 2 times to get valid machine_id
        for attempt in range(1, 3):
            try:
                logger.info(f"Fetching machine_id from server (attempt {attempt}/2)")

                # Use execute_command for reliable output reading
                cmd = "cat /etc/machine-id 2>/dev/null || cat /var/lib/dbus/machine-id 2>/dev/null || echo 'UNKNOWN'"
                result = await _execute_command(shared_state, shared_state.config, cmd, 5, "raw",
                                                web_server, custom_prompt_pattern=GENERIC_PROMPT)

                # Parse machine_id from output
                result_json = json.loads(result[0].text)
                output = result_json.get("raw_output", "")

                # Look for machine-id in output
                candidate_id = None
                lines = output.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    # machine-id is 32 hex characters
                    if re.match(r'^[a-f0-9]{32}$', line):
                        candidate_id = line
                        break

                # Validate the candidate ID
                if candidate_id and shared_state.is_valid_machine_id(candidate_id):
                    machine_id = candidate_id
                    identity_status = "verified" if not force_check else "refreshed"
                    logger.info(f"Valid machine_id retrieved: {machine_id[:16]}...")
                    break  # Success! Exit retry loop
                else:
                    if candidate_id:
                        logger.warning(f"Attempt {attempt}/2: Invalid machine_id retrieved: {candidate_id}")
                    else:
                        logger.warning(f"Attempt {attempt}/2: No machine_id found in output")

                    if attempt < 2:
                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Attempt {attempt}/2: Error retrieving machine_id: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)

        # After 2 attempts, check if we got valid machine_id
        if not machine_id or not shared_state.is_valid_machine_id(machine_id):
            # Create fallback ID
            machine_id = f"unknown-{host}-{int(time.time())}"
            identity_status = "unavailable"
            warning_message = "Failed to retrieve valid machine_id after 2 attempts. Commands will NOT be saved to database."
            logger.error(f"Using fallback machine_id: {machine_id}")
        else:
            # Cache the valid machine_id
            shared_state.cache_machine_id(host, port, user, machine_id)

    # Get hostname using execute_command
    try:
        result = await _execute_command(shared_state, shared_state.config, "hostname", 5, "raw",
                                        web_server, custom_prompt_pattern=GENERIC_PROMPT)
        result_json = json.loads(result[0].text)
        output = result_json.get("raw_output", "")

        lines = output.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('hostname') and '@' not in line:
                hostname = line
                logger.info(f"Detected hostname: {hostname}")
                break
    except Exception as e:
        logger.error(f"Could not get hostname: {e}")

    return machine_id, identity_status, hostname, warning_message
