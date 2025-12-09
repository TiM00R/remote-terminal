"""
Output Buffer
Manages terminal output with scrollback and filtering
"""

import logging
from collections import deque
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OutputLine:
    """Represents a single line of terminal output"""
    
    def __init__(self, text: str, timestamp: Optional[datetime] = None):
        self.text = text
        self.timestamp = timestamp or datetime.now()
        self.marked = False  # For marking lines to send to Claude
    
    def __str__(self) -> str:
        return self.text
    
    def __repr__(self) -> str:
        return f"OutputLine('{self.text[:50]}...', marked={self.marked})"


class OutputBuffer:
    """
    Manages terminal output with scrollback buffer
    """
    
    def __init__(self, max_lines: int = 1000):
        """
        Initialize Output Buffer
        
        Args:
            max_lines: Maximum number of lines to keep in buffer
        """
        self.max_lines = max_lines
        self.lines: deque[OutputLine] = deque(maxlen=max_lines)
        self.current_output = ""  # Accumulates output until newline
        
    def add(self, text: str) -> List[OutputLine]:
        """
        Add text to buffer
        
        Args:
            text: Text to add (may contain multiple lines)
            
        Returns:
            List of newly created OutputLine objects
        """
        new_lines = []
        self.current_output += text
        
        # Process complete lines
        while '\n' in self.current_output:
            line_text, self.current_output = self.current_output.split('\n', 1)
            line = OutputLine(line_text)
            self.lines.append(line)
            new_lines.append(line)
        
        return new_lines
    
    def flush(self) -> Optional[OutputLine]:
        """
        Flush any remaining partial line
        
        Returns:
            OutputLine if there was partial content, None otherwise
        """
        if self.current_output:
            line = OutputLine(self.current_output)
            self.lines.append(line)
            self.current_output = ""
            return line
        return None
    
    def get_last_n(self, n: int = 100) -> List[OutputLine]:
        """
        Get last N lines from buffer
        
        Args:
            n: Number of lines to retrieve
            
        Returns:
            List of OutputLine objects
        """
        return list(self.lines)[-n:]
    
    def get_all(self) -> List[OutputLine]:
        """Get all lines in buffer"""
        return list(self.lines)
    
    def get_text(self, start: int = 0, end: Optional[int] = None) -> str:
        """
        Get text from buffer
        
        Args:
            start: Start line index
            end: End line index (None for all)
            
        Returns:
            Concatenated text
        """
        lines_list = list(self.lines)[start:end]
        return '\n'.join(line.text for line in lines_list)
    
    def clear(self) -> None:
        """Clear all buffer contents"""
        self.lines.clear()
        self.current_output = ""
        logger.debug("Output buffer cleared")
    
    def mark_lines(self, start: int, end: int) -> int:
        """
        Mark lines for Claude analysis
        
        Args:
            start: Start line index
            end: End line index
            
        Returns:
            Number of lines marked
        """
        lines_list = list(self.lines)
        count = 0
        
        for i in range(start, min(end, len(lines_list))):
            if i >= 0:
                lines_list[i].marked = True
                count += 1
        
        logger.debug(f"Marked {count} lines")
        return count
    
    def unmark_all(self) -> None:
        """Unmark all lines"""
        for line in self.lines:
            line.marked = False
    
    def get_marked(self) -> List[OutputLine]:
        """Get all marked lines"""
        return [line for line in self.lines if line.marked]
    
    def get_stats(self) -> dict:
        """
        Get buffer statistics
        
        Returns:
            Dictionary with statistics
        """
        return {
            'total_lines': len(self.lines),
            'max_lines': self.max_lines,
            'marked_lines': sum(1 for line in self.lines if line.marked),
            'partial_line_length': len(self.current_output)
        }


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
        self.command_start_line = 0
        
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
        self.command_start_line = len(self.buffer.lines)
        logger.debug(f"start_command: '{command}' at line {self.command_start_line}")
    
    def add(self, text: str) -> List[OutputLine]:
        """Add text to buffer"""
        return self.buffer.add(text)
    
    def get_command_output(self) -> str:
        """
        Get output from last command
        
        Returns:
            Command output as string
        """
        if self.command_start_line >= len(self.buffer.lines):
            return ""
        
        return self.buffer.get_text(start=self.command_start_line)
    
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
        self.command_start_line = 0
    
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
            'command_start_line': self.command_start_line,
            'filter_enabled': self.filter is not None
        })
        return stats
