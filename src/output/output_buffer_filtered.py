"""
Filtered Output Buffer
Extends basic buffer with smart filtering and command tracking
FIXED: Adjust command_start_line when buffer overflows
"""

import logging
from typing import List, Optional
from .output_buffer_base import OutputBuffer, OutputLine

logger = logging.getLogger(__name__)


class FilteredBuffer:
    """
    Extension of OutputBuffer with smart filtering for Claude
    """

    def __init__(self, max_lines: int = 1000, output_filter=None):
        """
        Initialize Filtered Buffer

        Args:
            max_lines: Maximum number of lines to keep
            output_filter: SmartOutputFilter instance
        """
        self.buffer = OutputBuffer(max_lines)
        self.filter = output_filter
        self.last_command = ""
        self.command_start_line_absolute = 0  # Absolute line number (total lines added)

    def start_command(self, command: str) -> None:
        """
        Mark the start of a new command

        CRITICAL: This marks where command tracking begins.
        - command_start_line will contain the command echo line (with old prompt)
        - Real command output starts at command_start_line + 1
        - This ensures we only check for NEW prompt in command output, not old prompt

        Args:
            command: Command being executed
        """
        self.last_command = command
        # Store ABSOLUTE line number (total lines ever added)
        self.command_start_line_absolute = self.buffer.total_lines_added
        logger.debug(f"start_command: '{command}' at absolute line {self.command_start_line_absolute}")

    @property
    def command_start_line(self) -> int:
        """
        Get command start line relative to current buffer

        FIXED: Adjusts for buffer overflow by subtracting dropped lines
        Returns:
            Line index relative to current buffer (0-based)
        """
        buffer_offset = self.buffer.get_buffer_offset()
        relative_start = self.command_start_line_absolute - buffer_offset
        
        # Ensure it's within valid range
        if relative_start < 0:
            logger.warning(f"command_start_line would be negative ({relative_start}), clamping to 0")
            return 0
        if relative_start >= len(self.buffer.lines):
            logger.warning(f"command_start_line ({relative_start}) >= buffer size ({len(self.buffer.lines)})")
            return len(self.buffer.lines) - 1 if self.buffer.lines else 0
            
        return relative_start

    def add(self, text: str) -> List[OutputLine]:
        """Add text to buffer"""
        return self.buffer.add(text)

    def get_command_output(self) -> str:
        """
        Get output from last command

        Returns:
            Command output as string
        """
        start_line = self.command_start_line
        
        if start_line >= len(self.buffer.lines):
            return ""

        return self.buffer.get_text(start=start_line)

    def get_filtered_output(self, command: Optional[str] = None) -> str:
        """
        Get filtered output for sending to Claude

        Args:
            command: Command that was executed (uses last_command if None)

        Returns:
            Filtered output string
        """
        if not self.filter:
            return self.get_command_output()

        cmd = command or self.last_command
        output = self.get_command_output()

        return self.filter.filter_output(cmd, output)

    def should_send_to_claude(self, command: str, output: str) -> bool:
        """
        Determine if output should be sent to Claude

        Args:
            command: Command that was executed
            output: Command output

        Returns:
            True if should send to Claude
        """
        if not self.filter:
            return True

        return self.filter.should_send(command, output)

    def clear(self) -> None:
        """Clear buffer and reset command tracking"""
        self.buffer.clear()
        self.last_command = ""
        self.command_start_line_absolute = 0

    def get_last_n(self, n: int = 100) -> List[OutputLine]:
        """Get last N lines"""
        return self.buffer.get_last_n(n)

    def get_all(self) -> List[OutputLine]:
        """Get all lines"""
        return self.buffer.get_all()

    def mark_lines(self, start: int, end: int) -> int:
        """Mark lines for Claude"""
        return self.buffer.mark_lines(start, end)

    def get_marked(self) -> List[OutputLine]:
        """Get marked lines"""
        return self.buffer.get_marked()

    def unmark_all(self) -> None:
        """Unmark all lines"""
        self.buffer.unmark_all()

    def get_stats(self) -> dict:
        """Get buffer statistics"""
        stats = self.buffer.get_stats()
        stats.update({
            'last_command': self.last_command,
            'command_start_line_absolute': self.command_start_line_absolute,
            'command_start_line_relative': self.command_start_line,
            'filter_enabled': self.filter is not None
        })
        return stats
