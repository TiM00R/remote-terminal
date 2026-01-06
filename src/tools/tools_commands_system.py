"""
Command System Operations - Sudo and Backup
Pre-authentication and backup creation for file-modifying commands
"""

import asyncio
import json
import time
import logging
import re
import shlex
from datetime import datetime
from .decorators import requires_connection
from .tools_commands_execution import _execute_command

logger = logging.getLogger(__name__)


@requires_connection
async def pre_authenticate_sudo(shared_state, config, web_server, command: str,
                                database=None, hosts_manager=None) -> dict:
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
