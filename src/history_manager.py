"""
History Manager
Handles command history persistence and navigation
"""

import json
import logging
from pathlib import Path
from typing import List, Optional
from collections import deque

logger = logging.getLogger(__name__)


class HistoryManager:
    """
    Manages command history with persistence and navigation
    """
    
    def __init__(self, history_file: str = "~/.remote_terminal_history",
                 max_commands: int = 1000, enabled: bool = True):
        """
        Initialize History Manager
        
        Args:
            history_file: Path to history file
            max_commands: Maximum number of commands to keep
            enabled: Whether history is enabled
        """
        self.history_file = Path(history_file).expanduser()
        self.max_commands = max_commands
        self.enabled = enabled
        
        self.commands: deque = deque(maxlen=max_commands)
        self.current_index: int = -1
        self.temp_command: str = ""  # Temporary storage for partial command
        
    def load(self) -> bool:
        """
        Load history from file
        
        Returns:
            True if loaded successfully
        """
        if not self.enabled:
            logger.debug("History disabled, skipping load")
            return False
        
        if not self.history_file.exists():
            logger.debug(f"History file not found: {self.history_file}")
            return False
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.commands = deque(data.get('commands', []), maxlen=self.max_commands)
            
            logger.info(f"Loaded {len(self.commands)} commands from history")
            return True
            
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save history to file
        
        Returns:
            True if saved successfully
        """
        if not self.enabled:
            logger.debug("History disabled, skipping save")
            return False
        
        try:
            # Create directory if it doesn't exist
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'commands': list(self.commands),
                'max_commands': self.max_commands
            }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.commands)} commands to history")
            return True
            
        except Exception as e:
            logger.error(f"Error saving history: {e}")
            return False
    
    def add(self, command: str) -> None:
        """
        Add command to history
        
        Args:
            command: Command to add
        """
        if not self.enabled:
            return
        
        # Don't add empty commands or duplicates of the last command
        command = command.strip()
        if not command:
            return
        
        if self.commands and self.commands[-1] == command:
            return
        
        self.commands.append(command)
        self.reset_navigation()
        
        logger.debug(f"Added to history: {command}")
    
    def get_previous(self, current_input: str = "") -> Optional[str]:
        """
        Navigate to previous command in history
        
        Args:
            current_input: Current input to save temporarily
            
        Returns:
            Previous command or None
        """
        if not self.enabled or not self.commands:
            return None
        
        # Save current input on first up arrow press
        if self.current_index == -1:
            self.temp_command = current_input
            self.current_index = len(self.commands)
        
        if self.current_index > 0:
            self.current_index -= 1
            return self.commands[self.current_index]
        
        return None
    
    def get_next(self) -> Optional[str]:
        """
        Navigate to next command in history
        
        Returns:
            Next command or None (returns to temp command at end)
        """
        if not self.enabled or not self.commands:
            return None
        
        if self.current_index == -1:
            return None
        
        if self.current_index < len(self.commands) - 1:
            self.current_index += 1
            return self.commands[self.current_index]
        else:
            # Reached the end, return to temporary command
            cmd = self.temp_command
            self.reset_navigation()
            return cmd
    
    def reset_navigation(self) -> None:
        """Reset navigation state"""
        self.current_index = -1
        self.temp_command = ""
    
    def search(self, pattern: str) -> List[str]:
        """
        Search history for commands matching pattern
        
        Args:
            pattern: Search pattern (case-insensitive)
            
        Returns:
            List of matching commands
        """
        if not self.enabled or not pattern:
            return []
        
        pattern_lower = pattern.lower()
        return [cmd for cmd in self.commands if pattern_lower in cmd.lower()]
    
    def get_last_n(self, n: int = 10) -> List[str]:
        """
        Get last N commands from history
        
        Args:
            n: Number of commands to retrieve
            
        Returns:
            List of last N commands
        """
        if not self.enabled:
            return []
        
        return list(self.commands)[-n:]
    
    def clear(self) -> None:
        """Clear all history"""
        self.commands.clear()
        self.reset_navigation()
        logger.info("History cleared")
    
    def get_all(self) -> List[str]:
        """Get all commands in history"""
        return list(self.commands)
    
    def get_count(self) -> int:
        """Get total number of commands in history"""
        return len(self.commands)
    
    def get_stats(self) -> dict:
        """
        Get history statistics
        
        Returns:
            Dictionary with statistics
        """
        return {
            'total_commands': len(self.commands),
            'max_commands': self.max_commands,
            'enabled': self.enabled,
            'history_file': str(self.history_file),
            'current_index': self.current_index
        }
