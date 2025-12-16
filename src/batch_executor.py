"""
Batch Script Execution - Main Orchestrator
===========================================
Orchestrates batch script execution using existing MCP functions.
NO database integration - pure execution workflow.

Workflow:
1. Pre-authenticate sudo if script contains sudo
2. Upload script to remote server
3. Set executable permissions (no sudo needed - file in /tmp)
4. Execute script with output logging
5. Download log file to local machine
6. Parse output and return structured response
"""

import tempfile
import os
import json
from typing import Optional, Callable, Dict, Any

from batch_parser import parse_script_output
from batch_helpers import (
    generate_script_paths,
    ensure_local_log_directory,
    get_first_lines,
    get_last_lines,
    format_execution_time
)


async def execute_script_content(
    script_content: str,
    description: str,
    timeout: int = 300,
    output_mode: str = "auto",
    upload_file_func: Optional[Callable] = None,
    download_file_func: Optional[Callable] = None,
    execute_command_func: Optional[Callable] = None,
    preauth_sudo_func: Optional[Callable] = None,
    local_log_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute multi-command batch script on remote server.
    
    Args:
        script_content: Full bash script content
        description: Human-readable description of what script does
        timeout: Maximum execution time in seconds (default: 300)
        output_mode: Output format - "auto", "full", "summary" (default: "auto")
        upload_file_func: Function to upload files (injected)
        download_file_func: Function to download files (injected)
        execute_command_func: Function to execute commands (injected, async)
        preauth_sudo_func: Function to pre-authenticate sudo (injected, async)
        local_log_dir: Local directory for logs (uses ~/mcp_batch_logs if None)
        
    Returns:
        dict with execution results:
        - status: "completed", "failed", "timeout", "interrupted"
        - description: Original description
        - local_log_file: Path to local log file
        - remote_script_file: Path to remote script file
        - remote_log_file: Path to remote log file
        - execution_time_seconds: Execution duration
        - exit_code: Script exit code
        - steps_completed: "X/Y" format
        - error_detected: boolean
        - error_summary: string or None
        - output_preview: dict with first/last lines
        - full_output: complete output (if output_mode="full")
    
    NOTE: AI is blocked during execution. Parsing happens AFTER completion.
    """
    
    # Validate required functions are provided
    if not all([upload_file_func, download_file_func, execute_command_func]):
        return {
            "status": "failed",
            "error": "Required functions not provided (upload, download, execute)"
        }
    
    # Generate unique file paths (uses user's home directory if local_log_dir not specified)
    paths = generate_script_paths(local_log_dir=local_log_dir)
    remote_script = paths["remote_script"]
    remote_log = paths["remote_log"]
    local_log = paths["local_log"]
    
    try:
        # Ensure local log directory exists
        ensure_local_log_directory(local_log)
        
        # STEP 0: Pre-authenticate sudo if script contains sudo commands
        if 'sudo' in script_content and preauth_sudo_func:
            preauth_result = await preauth_sudo_func(script_content)
            if preauth_result.get("status") == "failed":
                return {
                    "status": "failed",
                    "error": f"Sudo pre-authentication failed: {preauth_result.get('error')}",
                    "description": description
                }
        
        # STEP 1: Upload script to remote server
        temp_script_path = _write_temp_script(script_content)
        try:
            upload_result = upload_file_func(
                local_path=temp_script_path,
                remote_path=remote_script
            )
            if not upload_result.get("success", True):
                raise Exception(f"Upload failed: {upload_result.get('error')}")
        finally:
            # Clean up temp file
            if os.path.exists(temp_script_path):
                os.unlink(temp_script_path)
        
        # STEP 2: Set executable permissions (no sudo - file in /tmp owned by user)
        chmod_result = await execute_command_func(
            command=f"chmod +x {remote_script}",
            timeout=10,
            output_mode="minimal"
        )
        
        # Parse chmod result (it's a JSON string from _execute_command)
        if isinstance(chmod_result, str):
            chmod_result = json.loads(chmod_result)
        
        if chmod_result.get("status") not in ["completed", "success"]:
            raise Exception(f"chmod failed: {chmod_result.get('error', 'Unknown error')}")
        
        # STEP 3: Execute script
        # - Monitors terminal buffer continuously
        # - User sees live output
        # - AI blocked until completion
        # - Output captured in buffer AND written to log file
        exec_result = await execute_command_func(
            command=f"bash {remote_script} 2>&1 | tee {remote_log}",
            timeout=timeout,
            output_mode=output_mode
        )
        
        # Parse exec result
        if isinstance(exec_result, str):
            exec_result = json.loads(exec_result)
        
        # STEP 4: Download log file to local machine
        download_result = download_file_func(
            remote_path=remote_log,
            local_path=local_log
        )
        if not download_result.get("success", True):
            # Log download failed, but we have output from exec_result
            print(f"Warning: Log download failed: {download_result.get('error')}")
        
        # STEP 5: Parse output (POST-EXECUTION parsing)
        # Read from downloaded log file (source of truth)
        try:
            with open(local_log, 'r', encoding='utf-8', errors='replace') as f:
                output = f.read()
        except Exception as e:
            # Fallback to exec_result output if log file read fails
            output = exec_result.get("output", exec_result.get("raw_output", ""))
        
        parsed = parse_script_output(output)
        
        # Build structured response
        return {
            "status": exec_result.get("status", "completed"),
            "description": description,
            
            # File paths
            "local_log_file": local_log,
            "remote_script_file": remote_script,
            "remote_log_file": remote_log,
            
            # Execution metadata
            "execution_time_seconds": exec_result.get("duration", 0),
            "execution_time_formatted": format_execution_time(
                exec_result.get("duration", 0)
            ),
            "exit_code": exec_result.get("exit_code"),
            
            # Parsed results (from post-execution analysis of log file)
            "steps_completed": parsed["steps_completed"],
            "error_detected": parsed["error_detected"],
            "error_summary": parsed["error_summary"],
            "all_complete": parsed["all_complete"],
            
            # Output preview
            "output_preview": {
                "first_lines": get_first_lines(output, 10),
                "last_lines": get_last_lines(output, 10),
                "total_lines": parsed["total_lines"]
            },
            
            # Full output (if requested or small enough)
            "full_output": output if output_mode == "full" else None
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "description": description,
            "local_log_file": local_log,
            "remote_script_file": remote_script,
            "remote_log_file": remote_log
        }


def _write_temp_script(script_content: str) -> str:
    """
    Write script content to temporary file with Unix line endings.
    
    Args:
        script_content: Script text
        
    Returns:
        Path to temporary file
    """
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.sh',
        delete=False,
        encoding='utf-8',
        newline='\n'  # Force Unix line endings (LF only)
    ) as f:
        f.write(script_content)
        return f.name


def build_script_from_commands(commands: list, description: str = "Diagnostics") -> str:
    """
    Helper to create a batch diagnostic script from command list.
    
    Args:
        commands: List of dicts with 'description' and 'command' keys
        description: Overall script description
        
    Returns:
        Complete bash script with proper markers
        
    Example:
        commands = [
            {"description": "Network interfaces", "command": "ip link show"},
            {"description": "Routing table", "command": "ip route show"}
        ]
        script = build_script_from_commands(commands)
    """
    lines = [
        "#!/bin/bash",
        "# Auto-generated diagnostic script",
        f"# Description: {description}",
        "",
        "set -e",  # Exit on error
        "set -o pipefail",  # Catch pipe failures
        ""
    ]
    
    total_steps = len(commands)
    
    for i, cmd_info in enumerate(commands, 1):
        step_desc = cmd_info.get("description", f"Step {i}")
        command = cmd_info.get("command", "")
        
        lines.extend([
            f'echo "=== [STEP {i}/{total_steps}] {step_desc} ==="',
            command,
            f'echo "[STEP_{i}_COMPLETE]"',
            ""
        ])
    
    lines.append('echo "[ALL_DIAGNOSTICS_COMPLETE]"')
    
    return '\n'.join(lines)
