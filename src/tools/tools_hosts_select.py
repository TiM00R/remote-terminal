"""
Server Selection and Connection
Server selection with machine ID detection and conversation management
"""

import re
import time
import asyncio
import logging
import json
from mcp import types
from tools.tools_commands import _execute_command

logger = logging.getLogger(__name__)


async def _select_server(shared_state, hosts_manager, database, web_server, identifier: str,
                        force_identity_check: bool = False) -> list[types.TextContent]:
    """Select and connect to a server - Phase 1 Enhanced with conversation workflow and machine_id retry logic"""

    # Generic pattern for internal commands
    GENERIC_PROMPT = r'^[^@\s:]+@[A-Za-z0-9.-]+:[^$#]*[$#]\s*$'

    srv = hosts_manager.find_server(identifier)

    if not srv:
        return [types.TextContent(
            type="text",
            text=f"Server not found: {identifier}. Use list_servers to see available servers."
        )]

    # PHASE 1: Conversation management on server switch
    if database and database.is_connected():
        # Get current machine ID
        old_machine_id = shared_state.current_machine_id

        # Pause active conversation on old machine (if any)
        if old_machine_id:
            active_conv_id = shared_state.get_active_conversation_for_server(old_machine_id)
            if active_conv_id:
                shared_state.pause_conversation(old_machine_id)
                logger.info(f"Paused conversation {active_conv_id} on old server")

    # Set as current
    hosts_manager.set_current(identifier)

    # Disconnect current connection if any
    if shared_state.is_connected():
        shared_state.ssh_manager.disconnect()

    # Connect to new server
    success = shared_state.ssh_manager.connect(
        host=srv.host,
        user=srv.user,
        password=srv.password,
        port=srv.port
    )

    if not success or not shared_state.ssh_manager.connect():
    ##if not success:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Failed to connect to {identifier}"})
        )]

    # Wait for welcome message to fully arrive before fetching machine_id
    time.sleep(1.0)

    # ========== GET MACHINE_ID AND HOSTNAME WITH RETRY LOGIC ==========
    host = srv.host
    port = srv.port
    user = srv.user

    machine_id = None
    identity_status = "unknown"
    previous_machine_id = None
    hostname = ""
    machine_id_warning = None

    # Check cache first (unless force check requested)
    if not force_identity_check:
        cached_id = shared_state.get_cached_machine_id(host, port, user)
        # Only use cached ID if it's valid
        if cached_id and shared_state.is_valid_machine_id(cached_id):
            machine_id = cached_id
            identity_status = "cached"
            logger.info(f"Using cached machine_id: {machine_id[:16]}...")

    # Fetch machine_id from server if not cached or force requested
    if machine_id is None or force_identity_check:
        if force_identity_check and machine_id:
            previous_machine_id = shared_state.get_cached_machine_id(host, port, user)

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
                    identity_status = "verified" if not force_identity_check else "refreshed"
                    logger.info(f"Valid machine_id retrieved: {machine_id[:16]}...")
                    break  # Success! Exit retry loop
                else:
                    if candidate_id:
                        logger.warning(f"Attempt {attempt}/2: Invalid machine_id retrieved: {candidate_id}")
                    else:
                        logger.warning(f"Attempt {attempt}/2: No machine_id found in output")

                    if attempt < 2:
                        # Wait before retry
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
            machine_id_warning = "Failed to retrieve valid machine_id after 2 attempts. Commands will NOT be saved to database."
            logger.error(f"Using fallback machine_id: {machine_id}")
            # DO NOT cache fallback IDs
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


    # Update database with machine_id (only if valid)
    if database and database.is_connected():
        if shared_state.is_valid_machine_id(machine_id):
            # Returns machine_id (or None on error)
            stored_machine_id = database.get_or_create_server(
                machine_id=machine_id,
                host=host,
                user=user,
                port=port,
                hostname=hostname,
                description=srv.description or '',
                tags=', '.join(srv.tags) if srv.tags else ''
            )

            if stored_machine_id:
                shared_state.set_current_server(stored_machine_id)
            else:
                logger.error("Failed to store machine_id in database")
        else:
            # Fallback ID - don't save to database
            logger.warning("Skipping database save for fallback machine_id")
            shared_state.set_current_server(None)
    # ========== END ==========

    # Update prompt detector with new credentials
    shared_state.update_credentials(user=user, host=hostname if hostname else host)

    # Clear conversation mode for new server (user must choose)
    shared_state.clear_conversation_mode()

    # # Send newline to get fresh prompt with welcome message
    # time.sleep(0.3)
    # shared_state.ssh_manager.send_input('\n')
    # time.sleep(0.2)

    # Build response with open conversations and machine identity
    response_data = {
        "connected": True,
        "server_name": srv.name,
        "server_host": f"{host}:{port}",
        "user": user,
        "hostname": hostname,
        "machine_id": machine_id[:16] + "..." if len(machine_id) > 16 else machine_id,
        "identity_status": identity_status,
        "open_conversations": []
    }

    # Add warning if fallback ID is used
    if machine_id_warning:
        response_data["machine_id_warning"] = machine_id_warning
        response_data["database_tracking"] = "disabled"
    else:
        response_data["database_tracking"] = "enabled"

    # Add identity change warning if detected
    if force_identity_check and previous_machine_id and previous_machine_id != machine_id:
        response_data["identity_changed"] = True
        response_data["previous_machine_id"] = previous_machine_id[:16] + "..."
        response_data["warning"] = "Machine identity changed! This is a different physical machine."

    # PHASE 1: Check for conversations on new server (only if valid machine_id)
    if database and database.is_connected() and shared_state.is_valid_machine_id(machine_id):
        # Get both active and paused conversations
        active_conv = database.get_active_conversation(machine_id)
        paused_convs = database.get_paused_conversations(machine_id)

        # Combine into open_conversations list
        if active_conv:
            response_data["open_conversations"].append({
                "id": active_conv['id'],
                "status": "in_progress",
                "goal": active_conv['goal_summary'],
                "started_at": str(active_conv['started_at'])
            })

        for conv in paused_convs:
            response_data["open_conversations"].append({
                "id": conv['id'],
                "status": "paused",
                "goal": conv['goal_summary'],
                "started_at": str(conv['started_at'])
            })

    # Return structured response
    return [types.TextContent(
        type="text",
        text=json.dumps(response_data, indent=2)
    )]
