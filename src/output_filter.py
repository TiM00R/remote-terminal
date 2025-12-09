"""
Smart Output Filter
Intelligently filters command output to minimize token usage
"""

import logging
import re
from typing import Optional, Dict, List
from utils import (
    count_lines, extract_head_tail, is_error_output,
    detect_command_type, parse_ls_output, format_bytes
)

logger = logging.getLogger(__name__)


class SmartOutputFilter:
    """
    Filters command output intelligently based on command type and length
    """
    
    def __init__(self, thresholds: Optional[Dict[str, int]] = None,
                 truncation: Optional[Dict[str, int]] = None,
                 error_patterns: Optional[List[str]] = None,
                 auto_send_errors: bool = True):
        """
        Initialize Smart Output Filter
        
        Args:
            thresholds: Line thresholds for different command types
            truncation: Truncation settings (head/tail lines)
            error_patterns: Patterns to detect errors
            auto_send_errors: Auto send error output to Claude
        """
        self.thresholds = thresholds or {
            'system_info': 50,
            'network_info': 100,
            'file_listing': 50,
            'file_viewing': 100,
            'install': 100,
            'generic': 50
        }
        
        self.truncation = truncation or {
            'head_lines': 30,
            'tail_lines': 20
        }
        
        self.error_patterns = error_patterns or [
            'ERROR', 'FAILED', 'FATAL', 'Cannot',
            'Permission denied', 'No such file', 'command not found'
        ]
        
        self.auto_send_errors = auto_send_errors
    
    def should_send(self, command: str, output: str) -> bool:
        """
        Determine if output should be sent to Claude
        
        Args:
            command: Command that was executed
            output: Command output
            
        Returns:
            True if should send to Claude
        """
        # Always send errors
        if self.auto_send_errors and is_error_output(output, self.error_patterns):
            logger.debug("Output contains errors, will send to Claude")
            return True
        
        # Check command type and line count
        cmd_type = detect_command_type(command)
        line_count = count_lines(output)
        threshold = self.thresholds.get(cmd_type, self.thresholds['generic'])
        
        # Don't send very verbose output
        if line_count > threshold * 2:
            logger.debug(f"Output too verbose ({line_count} lines), will not auto-send")
            return False
        
        return True
    
    def filter_output(self, command: str, output: str) -> str:
        """
        Filter output based on command type and length
        
        Args:
            command: Command that was executed
            output: Full command output
            
        Returns:
            Filtered/summarized output
        """
        if not output or not output.strip():
            return "[No output]"
        
        # Detect command type
        cmd_type = detect_command_type(command)
        line_count = count_lines(output)
        
        # Check if contains errors
        has_errors = is_error_output(output, self.error_patterns)
        
        # Get threshold for this command type
        threshold = self.thresholds.get(cmd_type, self.thresholds['generic'])
        
        logger.debug(f"Filtering: cmd_type={cmd_type}, lines={line_count}, "
                    f"threshold={threshold}, has_errors={has_errors}")
        
        # If has errors, always include error context
        if has_errors:
            return self._filter_with_errors(command, output, cmd_type)
        
        # If within threshold, send full output
        if line_count <= threshold:
            return output
        
        # Otherwise, apply smart filtering based on command type
        return self._apply_smart_filter(command, output, cmd_type, line_count)
    
    def _filter_with_errors(self, command: str, output: str, cmd_type: str) -> str:
        """
        Filter output that contains errors
        
        Args:
            command: Command executed
            output: Full output
            cmd_type: Command type
            
        Returns:
            Filtered output with error context
        """
        lines = output.split('\n')
        
        # Find error lines
        error_indices = []
        for i, line in enumerate(lines):
            if is_error_output(line, self.error_patterns):
                error_indices.append(i)
        
        if not error_indices:
            # No specific error line found, return last portion
            return self._truncate_output(output)
        
        # Get context around first error
        first_error = error_indices[0]
        context_lines = 10
        start = max(0, first_error - context_lines)
        end = min(len(lines), first_error + context_lines)
        
        error_context = '\n'.join(lines[start:end])
        
        result = f"[Error detected in command output]\n"
        result += f"Command: {command}\n"
        result += f"Total output lines: {len(lines)}\n"
        result += f"\nError context:\n{error_context}"
        
        return result
    
    def _apply_smart_filter(self, command: str, output: str, 
                           cmd_type: str, line_count: int) -> str:
        """
        Apply smart filtering based on command type
        
        Args:
            command: Command executed
            output: Full output
            cmd_type: Command type
            line_count: Number of lines
            
        Returns:
            Filtered output
        """
        if cmd_type == 'install':
            return self._filter_installation(command, output, line_count)
        
        elif cmd_type == 'file_listing':
            return self._filter_file_listing(command, output, line_count)
        
        elif cmd_type == 'file_viewing':
            return self._filter_file_viewing(command, output, line_count)
        
        elif cmd_type == 'system_info':
            return self._filter_system_info(command, output, line_count)
        
        elif cmd_type == 'network':
            return self._filter_network_info(command, output, line_count)
        
        elif cmd_type == 'log_search':
            return self._filter_log_search(command, output, line_count)
        
        else:
            return self._truncate_output(output)
    
    def _filter_installation(self, command: str, output: str, line_count: int) -> str:
        """Filter installation command output"""
        # Installations can be very verbose, provide summary
        result = f"[Installation Output Summary]\n"
        result += f"Command: {command}\n"
        result += f"Total lines: {line_count}\n\n"
        
        # Get first and last few lines
        filtered, _, _ = extract_head_tail(output, 15, 15)
        result += filtered
        
        return result
    
    def _filter_file_listing(self, command: str, output: str, line_count: int) -> str:
        """Filter file listing output (ls, find, tree)"""
        if 'ls' in command.lower() and ('-l' in command or '-la' in command):
            # Parse ls output for summary
            stats = parse_ls_output(output)
            
            result = f"[File Listing Summary]\n"
            result += f"Total items: {stats['total_items']}\n"
            result += f"Directories: {stats['directories']}\n"
            result += f"Files: {stats['files']}\n"
            result += f"Total size: {format_bytes(stats['total_size'])}\n\n"
            
            # Include first few entries
            filtered, _, _ = extract_head_tail(output, 20, 10)
            result += filtered
            
            return result
        
        # For other file listings, use truncation
        return self._truncate_output(output)
    
    def _filter_file_viewing(self, command: str, output: str, line_count: int) -> str:
        """Filter file viewing output (cat, less, more)"""
        result = f"[File Content]\n"
        result += f"Total lines: {line_count}\n\n"
        
        # Show head and tail
        filtered, _, _ = extract_head_tail(
            output,
            self.truncation['head_lines'],
            self.truncation['tail_lines']
        )
        result += filtered
        
        return result
    
    def _filter_system_info(self, command: str, output: str, line_count: int) -> str:
        """Filter system info output (df, free, uptime)"""
        # System info is usually already concise, just truncate if too long
        if line_count <= self.thresholds['system_info']:
            return output
        
        return self._truncate_output(output)
    
    def _filter_network_info(self, command: str, output: str, line_count: int) -> str:
        """Filter network info output"""
        # Network info can be verbose, truncate
        return self._truncate_output(output)
    
    def _filter_log_search(self, command: str, output: str, line_count: int) -> str:
        """Filter log search output (grep, awk, sed)"""
        # Determine number of matches
        result = f"[Search Results]\n"
        result += f"Matches found: {line_count}\n"
        
        if line_count > 50:
            result += f"\nShowing first 25 and last 25 matches:\n\n"
            filtered, _, _ = extract_head_tail(output, 25, 25)
            result += filtered
        else:
            result += f"\n{output}"
        
        return result
    
    def _truncate_output(self, output: str) -> str:
        """Generic truncation for any output"""
        filtered, total_lines, was_truncated = extract_head_tail(
            output,
            self.truncation['head_lines'],
            self.truncation['tail_lines']
        )
        
        if was_truncated:
            result = f"[Output truncated - {total_lines} total lines]\n\n"
            result += filtered
            return result
        
        return output
    
    def get_summary(self, command: str, output: str) -> dict:
        """
        Get summary statistics about command output
        
        Args:
            command: Command executed
            output: Command output
            
        Returns:
            Dictionary with summary statistics
        """
        return {
            'command': command,
            'command_type': detect_command_type(command),
            'line_count': count_lines(output),
            'char_count': len(output),
            'has_errors': is_error_output(output, self.error_patterns),
            'should_send': self.should_send(command, output)
        }
