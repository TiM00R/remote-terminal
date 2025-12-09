"""
Utility Functions
Common helper functions for the remote terminal application
"""

import re
import time
from datetime import datetime
from typing import List, Optional, Tuple
from pathlib import Path


def strip_ansi_codes(text: str) -> str:
    """
    Remove ANSI escape codes from text
    
    Args:
        text: Text containing ANSI codes
        
    Returns:
        Clean text without ANSI codes
    """
    # Remove OSC sequences (Operating System Command) like terminal titles
    # Pattern: ESC ] number ; text BEL
    # The "0;" at the start of prompt is from this
    text = re.sub(r'\x1B\]0;[^\x07]*\x07', '', text)
    text = re.sub(r'\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)', '', text)
    
    # Remove CSI sequences (colors, cursor movement, etc.)
    # Pattern: ESC [ parameters letter
    text = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)
    
    # Remove other escape sequences
    text = re.sub(r'\x1B[@-Z\\-_]', '', text)
    
    # Remove bell character
    text = text.replace('\x07', '')
    
    # Remove any remaining control characters except newline, tab, carriage return
    # This will catch any stray escape sequences we missed
    cleaned = []
    for char in text:
        code = ord(char)
        if code >= 32 or char in '\n\t\r':
            cleaned.append(char)
    
    return ''.join(cleaned)


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "45.2s", "2m 15s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_bytes(bytes_count: int) -> str:
    """
    Format byte count in human-readable format
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 KB", "2.3 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def split_lines(text: str) -> List[str]:
    """
    Split text into lines, handling different line endings
    
    Args:
        text: Text to split
        
    Returns:
        List of lines
    """
    # Handle \r\n, \r, and \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text.split('\n')


def extract_head_tail(text: str, head_lines: int = 30, tail_lines: int = 20) -> Tuple[str, int, bool]:
    """
    Extract head and tail lines from text
    
    Args:
        text: Full text
        head_lines: Number of lines from start
        tail_lines: Number of lines from end
        
    Returns:
        Tuple of (extracted_text, total_lines, was_truncated)
    """
    lines = split_lines(text)
    total = len(lines)
    
    if total <= (head_lines + tail_lines):
        return text, total, False
    
    head = '\n'.join(lines[:head_lines])
    tail = '\n'.join(lines[-tail_lines:])
    omitted = total - head_lines - tail_lines
    
    result = f"{head}\n\n[... {omitted} lines omitted ...]\n\n{tail}"
    return result, total, True


def expand_path(path: str) -> Path:
    """
    Expand user home directory and resolve path
    
    Args:
        path: Path string (may contain ~)
        
    Returns:
        Resolved Path object
    """
    return Path(path).expanduser().resolve()


def timestamp_now() -> str:
    """
    Get current timestamp in ISO format
    
    Returns:
        ISO formatted timestamp string
    """
    return datetime.utcnow().isoformat()


def timestamp_local() -> str:
    """
    Get current local timestamp
    
    Returns:
        Formatted local timestamp
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_error_output(text: str, error_patterns: List[str]) -> bool:
    """
    Check if text contains error patterns (context-aware)
    Uses improved error detection from error_check_helper
    
    Args:
        text: Text to check
        error_patterns: List of error patterns to look for
        
    Returns:
        True if error pattern found (with proper context)
    """
    # Use the improved context-aware error detection from error_check_helper
    from error_check_helper import check_for_errors
    
    error_summary = check_for_errors(text, error_patterns)
    return error_summary is not None


def count_lines(text: str) -> int:
    """
    Count number of lines in text
    
    Args:
        text: Text to count
        
    Returns:
        Number of lines
    """
    return len(split_lines(text))


def extract_error_context(output: str, error_lines: int = 20) -> str:
    """
    Extract error context from command output
    
    Args:
        output: Full command output
        error_lines: Number of lines to include around error
        
    Returns:
        Error context
    """
    lines = split_lines(output)
    
    # Find lines with common error indicators
    error_indicators = ['error', 'failed', 'cannot', 'denied', 'fatal']
    error_line_indices = []
    
    for i, line in enumerate(lines):
        if any(indicator in line.lower() for indicator in error_indicators):
            error_line_indices.append(i)
    
    if not error_line_indices:
        # No specific error found, return last N lines
        return '\n'.join(lines[-error_lines:])
    
    # Get context around first error
    first_error = error_line_indices[0]
    start = max(0, first_error - error_lines // 2)
    end = min(len(lines), first_error + error_lines // 2)
    
    return '\n'.join(lines[start:end])


def sanitize_output(text: str) -> str:
    """
    Sanitize output for safe display
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
    """
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove other control characters except newline, tab, carriage return
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
    
    return text


def detect_command_type(command: str) -> str:
    """
    Detect command type for smart filtering
    
    Args:
        command: Command string
        
    Returns:
        Command type identifier
    """
    command_lower = command.lower().strip()
    
    # Installation commands
    if any(cmd in command_lower for cmd in ['apt install', 'yum install', 'pip install', 'npm install']):
        return 'install'
    
    # System info commands
    if any(cmd in command_lower for cmd in ['df', 'free', 'uptime', 'uname', 'hostname']):
        return 'system_info'
    
    # Network commands
    if any(cmd in command_lower for cmd in ['ip addr', 'ip route', 'netstat', 'ss', 'ifconfig']):
        return 'network'
    
    # File listing
    if command_lower.startswith('ls') or command_lower.startswith('find') or 'tree' in command_lower:
        return 'file_listing'
    
    # File viewing
    if any(cmd in command_lower for cmd in ['cat', 'less', 'more', 'head', 'tail']):
        return 'file_viewing'
    
    # Log search
    if any(cmd in command_lower for cmd in ['grep', 'awk', 'sed']):
        return 'log_search'
    
    return 'generic'


def format_command_prompt(user: str, host: str, path: str = "~") -> str:
    """
    Format command prompt string
    
    Args:
        user: Username
        host: Hostname
        path: Current path
        
    Returns:
        Formatted prompt
    """
    return f"{user}@{host}:{path}$ "


def parse_ls_output(output: str) -> dict:
    """
    Parse ls -la output into structured data
    
    Args:
        output: ls command output
        
    Returns:
        Dictionary with file statistics
    """
    lines = split_lines(output)
    stats = {
        'total_items': 0,
        'directories': 0,
        'files': 0,
        'total_size': 0
    }
    
    for line in lines[1:]:  # Skip first line (total)
        if not line.strip():
            continue
        
        parts = line.split()
        if len(parts) < 9:
            continue
        
        stats['total_items'] += 1
        
        # Check if directory (first char is 'd')
        if line.startswith('d'):
            stats['directories'] += 1
        else:
            stats['files'] += 1
        
        # Try to get file size (5th column)
        try:
            stats['total_size'] += int(parts[4])
        except (ValueError, IndexError):
            pass
    
    return stats


class Timer:
    """Simple timer context manager"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
    
    def elapsed(self) -> float:
        """Get elapsed time"""
        if self.duration is not None:
            return self.duration
        elif self.start_time is not None:
            return time.time() - self.start_time
        return 0.0



# ========== MACHINE ID HELPER (Bug Fix) ==========

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
