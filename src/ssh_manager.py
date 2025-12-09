"""
SSH Manager
Handles SSH connections and command execution with automatic reconnection
Version 3.0 - Multi-Server Support
"""

import paramiko
import socket
import threading
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command execution"""
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    command: str


class SSHManager:
    """
    Manages SSH connection to remote machine with automatic reconnection
    """
    
    def __init__(self, host: str = "", user: str = "", password: str = "", port: int = 22,
                 keepalive_interval: int = 30, reconnect_attempts: int = 3,
                 connection_timeout: int = 10):
        """
        Initialize SSH Manager
        
        Args:
            host: Remote host address (can be empty for multi-server mode)
            user: Username for authentication (can be empty for multi-server mode)
            password: Password for authentication (can be empty for multi-server mode)
            port: SSH port (default 22)
            keepalive_interval: Seconds between keepalive packets
            reconnect_attempts: Number of reconnection attempts
            connection_timeout: Connection timeout in seconds
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.keepalive_interval = keepalive_interval
        self.reconnect_attempts = reconnect_attempts
        self.connection_timeout = connection_timeout
        
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.connected = False
        self.reconnecting = False
        
        self._output_callback: Optional[Callable[[str], None]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()
        self._sftp = None  
        
    def reconfigure(self, host: str, user: str, password: str, port: int = 22) -> None:
        """
        Reconfigure connection parameters (disconnect first if connected)
        
        Args:
            host: New remote host address
            user: New username
            password: New password
            port: New SSH port
        """
        if self.connected:
            self.disconnect()
        
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        logger.info(f"SSH connection reconfigured for {user}@{host}:{port}")
        
    def connect(self, host: str = None, user: str = None, password: str = None, port: int = None) -> bool:
        """
        Establish SSH connection
        
        Args:
            host: Remote host (optional, uses configured if not provided)
            user: Username (optional, uses configured if not provided)
            password: Password (optional, uses configured if not provided)
            port: SSH port (optional, uses configured if not provided)
        
        Returns:
            True if connection successful, False otherwise
        """
        # Allow override of connection parameters
        if host is not None:
            self.host = host
        if user is not None:
            self.user = user
        if password is not None:
            self.password = password
        if port is not None:
            self.port = port
        
        try:
            logger.info(f"Connecting to {self.user}@{self.host}:{self.port}")
            
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                timeout=self.connection_timeout,
                look_for_keys=False,
                allow_agent=False
            )
            
            # Set keepalive
            transport = self.client.get_transport()
            if transport:
                transport.set_keepalive(self.keepalive_interval)
            
            # Get interactive shell
            self.shell = self.client.invoke_shell(
                term='xterm-256color',
                width=120,
                height=40
            )
            
            self.connected = True
            logger.info("SSH connection established")
            
            # Start output reader thread BEFORE clearing initial output
            # This ensures the initial prompt is captured
            self._start_reader()
            
            # Wait for initial output (welcome message + prompt)
            time.sleep(0.5)
            
            # The reader thread will automatically capture and send
            # the initial output including the prompt to the callback
            # No need to manually clear it here anymore
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> None:
        """Close SSH connection"""
        logger.info("Disconnecting SSH")
        
        # ADD THESE 9 LINES (START)
        # Close SFTP client if exists
        if self._sftp is not None:
            try:
                self._sftp.close()
                logger.info("SFTP client closed")
            except Exception as e:
                logger.warning(f"Error closing SFTP client: {e}")
            finally:
                self._sftp = None
        # ADD THESE 9 LINES (END)
        
        self._stop_reader.set()
        
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)
        
        if self.shell:
            try:
                self.shell.close()
            except:
                pass
            self.shell = None
        
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        
        self.connected = False
        logger.info("SSH disconnected")
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to remote machine
        
        Returns:
            True if reconnection successful
        """
        if self.reconnecting:
            return False
        
        self.reconnecting = True
        logger.info("Attempting reconnection...")
        
        self.disconnect()
        
        for attempt in range(self.reconnect_attempts):
            logger.info(f"Reconnection attempt {attempt + 1}/{self.reconnect_attempts}")
            time.sleep(2 ** attempt)  # Exponential backoff
            
            if self.connect():
                self.reconnecting = False
                logger.info("Reconnection successful")
                return True
        
        self.reconnecting = False
        logger.error("Reconnection failed after all attempts")
        return False
    
    def resize_pty(self, cols: int, rows: int) -> bool:
        """
        Resize the pseudo-terminal
        
        Args:
            cols: Number of columns
            rows: Number of rows
            
        Returns:
            True if resize successful, False otherwise
        """
        if not self.connected or not self.shell:
            logger.warning("Cannot resize PTY: not connected")
            return False
        
        try:
            self.shell.resize_pty(width=cols, height=rows)
            logger.debug(f"PTY resized to {cols}x{rows}")
            return True
        except Exception as e:
            logger.error(f"Failed to resize PTY: {e}")
            return False
    
    def execute_command(self, command: str, timeout: int = 30) -> CommandResult:
        """
        Execute command and wait for completion
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            
        Returns:
            CommandResult with output and status
        """
        if not self.connected or not self.shell:
            raise Exception("Not connected to remote machine")
        
        start_time = time.time()
        
        try:
            # Send command
            self.shell.send(command + '\n')
            
            # Wait for command to complete (simple implementation)
            # In production, should use more sophisticated completion detection
            time.sleep(0.5)
            
            output = ""
            while self.shell.recv_ready():
                chunk = self.shell.recv(8192).decode('utf-8', errors='replace')
                output += chunk
                time.sleep(0.1)
            
            duration = time.time() - start_time
            
            return CommandResult(
                stdout=output,
                stderr="",
                exit_code=0,
                duration=duration,
                command=command
            )
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            duration = time.time() - start_time
            return CommandResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration=duration,
                command=command
            )
     
    # This methode is not used
    def execute_simple(self, command: str, timeout: int = 10) -> str:
        """
        Execute command synchronously using separate channel
        Does NOT interfere with the interactive shell
        """
        if not self.connected or not self.client:
            raise Exception("Not connected")
        
        try:
            # Log sanitized version (NEW CODE)
            ## safe_cmd = self._sanitize_command_for_log(command)
            logger.info(f"Executing simple command: {command}")
            # END NEW CODE
            # Use exec_command which creates a SEPARATE channel
            # This doesn't interfere with the interactive shell
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # Read output
            output = stdout.read().decode('utf-8', errors='replace')
            
            return output
            
        except Exception as e:
            logger.error(f"execute_simple failed: {e}")
            return ""        
    
    def _sanitize_command_for_log(self, command: str) -> str:
        """
        Remove password from command before logging
        
        Args:
            command: Command that may contain password
            
        Returns:
            Sanitized command for logging
        """
        if self.password and self.password in command:
            return command.replace(self.password, "***PASSWORD***")
        return command
                
        
    def send_input(self, text: str) -> None:
        """
        Send input to shell (for interactive commands)
        
        This properly handles command echoing by sending the command text first,
        then the newline separately, so the echo appears on the same line as the prompt.
        
        Args:
            text: Text to send (can include newline)
        """
        if not self.connected or not self.shell:
            raise Exception("Not connected to remote machine")
        
        # If text ends with newline, send command first, then newline
        if text.endswith('\n'):
            command = text[:-1]  # Remove the trailing newline
            if command:
                # Send command text (gets echoed on same line as prompt)
                self.shell.send(command)
                time.sleep(0.05)  # Small delay for echo
            # Now send the newline (executes command)
            self.shell.send('\n')
        else:
            # Just send as-is (for things like Tab character)
            self.shell.send(text)
    
    def send_interrupt(self) -> None:
        """Send Ctrl+C interrupt signal"""
        if not self.connected or not self.shell:
            raise Exception("Not connected to remote machine")
        
        # Send Ctrl+C (ASCII 3)
        self.shell.send('\x03')
    
    def set_output_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set callback function for output streaming
        
        Args:
            callback: Function to call with output chunks
        """
        self._output_callback = callback
    
    def _start_reader(self) -> None:
        """Start background thread to read shell output"""
        self._stop_reader.clear()
        self._reader_thread = threading.Thread(
            target=self._read_output,
            daemon=True
        )
        self._reader_thread.start()
    
    def _read_output(self) -> None:
        """
        Background thread function to continuously read shell output
        
        FIXED: Uses blocking read with timeout instead of recv_ready() polling.
        This ensures small packets (like shell prompts) are captured immediately.
        """
        logger.debug("Output reader thread started")
        
        while not self._stop_reader.is_set() and self.connected:
            try:
                if self.shell:
                    # Set timeout on channel - blocks up to 0.5s waiting for data
                    self.shell.settimeout(0.5)
                    
                    try:
                        # Blocking read - returns immediately when data arrives
                        # This captures prompts and all output reliably
                        chunk = self.shell.recv(8192).decode('utf-8', errors='replace')
                        if chunk and self._output_callback:
                            self._output_callback(chunk)
                    except socket.timeout:
                        # No data for 0.5s - normal for idle terminal
                        # Loop continues to check stop flag
                        pass
                        
            except Exception as e:
                logger.error(f"Error reading output: {e}")
                if not self.reconnect():
                    break
        
        logger.debug("Output reader thread stopped")
    
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.connected and self.client and self.client.get_transport() and \
               self.client.get_transport().is_active()
    
    def get_connection_info(self) -> dict:
        """Get connection information"""
        return {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'connected': self.connected,
            'reconnecting': self.reconnecting
        }


    def get_sftp(self) -> paramiko.SFTPClient:
        """
        Get SFTP client from existing SSH connection.
        Creates a new SFTP client if needed or if the existing one is closed.
        
        Returns:
            paramiko.SFTPClient: Active SFTP client
            
        Raises:
            RuntimeError: If SSH not connected
        """
        if not self.is_connected():
            raise RuntimeError("SSH not connected. Use connect() first.")
        
        # Create new SFTP client if needed
        if self._sftp is None or self._sftp.get_channel().closed:
            logger.info("Creating new SFTP client")
            self._sftp = self.client.open_sftp()
        
        return self._sftp
    