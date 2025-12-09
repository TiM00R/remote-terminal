"""
Command State Management
Tracks individual command execution state including timing, status, and buffer positions
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import time


@dataclass
class CommandState:
    """
    Represents the state of a single command execution
    
    Attributes:
        command_id: Unique identifier (format: cmd_DDMMHHMMS)
        command: Full command text
        status: Current status ("running", "completed", "cancelled", "killed", "backgrounded", "timeout_still_running", "max_timeout")
        start_time: Unix timestamp when command started
        end_time: Unix timestamp when command completed (None if running)
        timeout: Timeout in seconds
        expected_prompt: Prompt pattern to detect completion
        buffer_start_line: Line number in buffer where output starts
        buffer_end_line: Line number where output ends (None if running)
        prompt_changed: True if command changes prompt (sudo su, ssh, etc.)
        new_prompt_pattern: New prompt pattern if changed
    """
    command_id: str
    command: str
    status: str = "running"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    timeout: int = 30
    expected_prompt: str = ""
    buffer_start_line: int = 0
    buffer_end_line: Optional[int] = None
    prompt_changed: bool = False
    new_prompt_pattern: Optional[str] = None
    
    def duration(self) -> float:
        """Get command duration in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def is_running(self) -> bool:
        """
        Check if command is still running or should continue monitoring
        
        CRITICAL: Returns True for both "running" AND "timeout_still_running"
        This ensures monitoring continues after timeout until:
        - Prompt detected (completed/cancelled)
        - User calls cancel_command() (killed)
        - Max timeout reached (max_timeout)
        """
        return self.status in ["running", "timeout_still_running"]
    
    def is_completed(self) -> bool:
        """Check if command completed successfully"""
        return self.status == "completed"
    
    def is_cancelled(self) -> bool:
        """Check if command was cancelled (Ctrl+C detected)"""
        return self.status == "cancelled"
    
    def is_timeout(self) -> bool:
        """Check if command exceeded timeout"""
        return self.status == "timeout_still_running"
    
    def mark_completed(self, buffer_end_line: int):
        """Mark command as completed successfully"""
        self.status = "completed"
        self.end_time = time.time()
        self.buffer_end_line = buffer_end_line
    
    def mark_cancelled(self, buffer_end_line: int):
        """Mark command as cancelled (Ctrl+C detected in output)"""
        self.status = "cancelled"
        self.end_time = time.time()
        self.buffer_end_line = buffer_end_line
    
    def mark_killed(self, buffer_end_line: int):
        """Mark command as killed via cancel_command() tool"""
        self.status = "killed"
        self.end_time = time.time()
        self.buffer_end_line = buffer_end_line
    
    def mark_timeout(self):
        """Mark command as timed out but still running (monitoring continues)"""
        self.status = "timeout_still_running"
        # Don't set end_time - command still running, monitoring continues
    
    def mark_max_timeout(self, buffer_end_line: int):
        """Mark command as exceeding maximum monitoring time"""
        self.status = "max_timeout"
        self.end_time = time.time()
        self.buffer_end_line = buffer_end_line
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "command_id": self.command_id,
            "command": self.command,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration(),
            "timeout": self.timeout,
            "expected_prompt": self.expected_prompt,
            "buffer_start_line": self.buffer_start_line,
            "buffer_end_line": self.buffer_end_line,
            "prompt_changed": self.prompt_changed
        }


def generate_command_id() -> str:
    """
    Generate unique command ID with timestamp
    Format: cmd_DDMMHHMMS (Day-Month-Hour-Minute-Second)
    Example: cmd_2810145523 = Oct 28, 14:55:23
    
    Returns:
        Command ID string
    """
    now = datetime.now()
    return f"cmd_{now.strftime('%d%m%H%M%S')}"


class CommandRegistry:
    """
    Registry to track all command executions
    Manages command history with automatic cleanup
    """
    
    def __init__(self, max_commands: int = 50):
        """
        Initialize command registry
        
        Args:
            max_commands: Maximum number of completed commands to keep
        """
        self.commands: dict[str, CommandState] = {}
        self.max_commands = max_commands
    
    def add(self, command_state: CommandState) -> None:
        """Add command to registry"""
        self.commands[command_state.command_id] = command_state
        self.cleanup_if_needed()
    
    def get(self, command_id: str) -> Optional[CommandState]:
        """Get command by ID"""
        return self.commands.get(command_id)
    
    def remove(self, command_id: str) -> bool:
        """Remove command from registry"""
        if command_id in self.commands:
            del self.commands[command_id]
            return True
        return False
    
    def get_running(self) -> list[CommandState]:
        """Get all running commands"""
        return [
            cmd for cmd in self.commands.values()
            if cmd.is_running()
        ]
    
    def get_completed(self) -> list[CommandState]:
        """Get all completed commands"""
        return [
            cmd for cmd in self.commands.values()
            if cmd.is_completed()
        ]
    
    def get_all(self) -> list[CommandState]:
        """Get all commands"""
        return list(self.commands.values())
    
    def get_by_status(self, status: str) -> list[CommandState]:
        """Get commands by status"""
        return [
            cmd for cmd in self.commands.values()
            if cmd.status == status
        ]
    
    def cleanup_if_needed(self) -> None:
        """Remove old completed commands if exceeding max limit"""
        completed = [
            cmd for cmd in self.commands.values()
            if cmd.status in ["completed", "cancelled", "killed", "max_timeout"]
        ]
        
        if len(completed) > self.max_commands:
            # Sort by end_time, remove oldest
            completed.sort(key=lambda x: x.end_time or 0)
            to_remove = completed[:-self.max_commands]
            
            for cmd in to_remove:
                del self.commands[cmd.command_id]
    
    def cleanup_all_completed(self) -> int:
        """Remove all completed/cancelled/killed commands"""
        to_remove = [
            cmd_id for cmd_id, cmd in self.commands.items()
            if cmd.status in ["completed", "cancelled", "killed", "max_timeout"]
        ]
        
        for cmd_id in to_remove:
            del self.commands[cmd_id]
        
        return len(to_remove)
    
    def get_stats(self) -> dict:
        """Get registry statistics"""
        statuses = {}
        for cmd in self.commands.values():
            statuses[cmd.status] = statuses.get(cmd.status, 0) + 1
        
        return {
            "total_commands": len(self.commands),
            "by_status": statuses,
            "max_commands": self.max_commands
        }
