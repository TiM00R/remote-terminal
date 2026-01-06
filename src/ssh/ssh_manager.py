"""
SSH Manager
Handles SSH connections and command execution with automatic reconnection
Version 3.0 - Multi-Server Support
"""

import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Import from split modules
from .ssh_connection import SSHConnection
from .ssh_commands import SSHCommandExecutor, CommandResult
from .ssh_io import SSHInputOutput


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
        # Create connection handler
        self._connection = SSHConnection(
            host=host,
            user=user,
            password=password,
            port=port,
            keepalive_interval=keepalive_interval,
            reconnect_attempts=reconnect_attempts,
            connection_timeout=connection_timeout
        )

        # Create command executor
        self._command_executor = SSHCommandExecutor(self._connection)

        # Create I/O handler
        self._io = SSHInputOutput(self._connection)

    # Delegate connection properties
    @property
    def host(self):
        return self._connection.host

    @host.setter
    def host(self, value):
        self._connection.host = value

    @property
    def user(self):
        return self._connection.user

    @user.setter
    def user(self, value):
        self._connection.user = value

    @property
    def password(self):
        return self._connection.password

    @password.setter
    def password(self, value):
        self._connection.password = value

    @property
    def port(self):
        return self._connection.port

    @port.setter
    def port(self, value):
        self._connection.port = value

    @property
    def client(self):
        return self._connection.client

    @property
    def shell(self):
        return self._connection.shell

    @property
    def connected(self):
        return self._connection.connected

    @property
    def reconnecting(self):
        return self._connection.reconnecting

    # Delegate connection methods
    def reconfigure(self, host: str, user: str, password: str, port: int = 22) -> None:
        """Reconfigure connection parameters"""
        return self._connection.reconfigure(host, user, password, port)

    def connect(self, host: str = None, user: str = None, password: str = None, port: int = None) -> bool:
        """Establish SSH connection"""
        result = self._connection.connect(host, user, password, port)
        if result:
            # Start output reader thread AFTER connection
            self._io.start_reader()
        return result

    def disconnect(self) -> None:
        """Close SSH connection"""
        self._io.stop_reader()
        self._connection.disconnect()

    def reconnect(self) -> bool:
        """Attempt to reconnect"""
        return self._connection.reconnect()

    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self._connection.is_connected()

    def get_connection_info(self) -> dict:
        """Get connection information"""
        return self._connection.get_connection_info()

    def get_sftp(self):
        """Get SFTP client"""
        return self._connection.get_sftp()

    def resize_pty(self, cols: int, rows: int) -> bool:
        """Resize the pseudo-terminal"""
        return self._connection.resize_pty(cols, rows)

    # Delegate command execution methods
    def execute_command(self, command: str, timeout: int = 30) -> CommandResult:
        """Execute command and wait for completion"""
        return self._command_executor.execute_command(command, timeout)

    def execute_simple(self, command: str, timeout: int = 10) -> str:
        """Execute command using separate channel"""
        return self._command_executor.execute_simple(command, timeout)

    # Delegate I/O methods
    def send_input(self, text: str) -> None:
        """Send input to shell"""
        self._io.send_input(text)

    def send_interrupt(self) -> None:
        """Send Ctrl+C interrupt signal"""
        self._io.send_interrupt()

    def set_output_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback function for output streaming"""
        self._io.set_output_callback(callback)
