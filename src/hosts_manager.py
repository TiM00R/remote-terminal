"""
Host Configuration Manager
Manages multiple server configurations
"""

import yaml
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ServerHost:
    """Single server configuration"""
    name: str
    host: str
    user: str
    password: str
    port: int = 22
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def matches_identifier(self, identifier: str) -> bool:
        """Check if this server matches name, IP, or tag"""
        identifier_lower = identifier.lower()
        return (
            self.name.lower() == identifier_lower or
            self.host.lower() == identifier_lower or
            identifier_lower in [tag.lower() for tag in self.tags]
        )


class HostsManager:
    """Manages multiple server configurations"""
    
    def __init__(self, hosts_file: str = "hosts.yaml"):
        self.hosts_file = Path(hosts_file)
        self.servers: List[ServerHost] = []
        self.default_server: Optional[str] = None
        self.current_server: Optional[ServerHost] = None
        self.load()
    
    def load(self) -> None:
        """Load hosts from YAML file"""
        if not self.hosts_file.exists():
            logger.warning(f"Hosts file not found: {self.hosts_file}")
            self._create_default_hosts_file()
            return
        
        try:
            with open(self.hosts_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # Load servers
            servers_data = data.get('servers', [])
            self.servers = []
            for server_data in servers_data:
                # Ensure tags is a list
                tags = server_data.get('tags', [])
                if isinstance(tags, str):
                    tags = [tags]
                server_data['tags'] = tags
                self.servers.append(ServerHost(**server_data))
            
            # Load default server
            self.default_server = data.get('default_server')
            
            logger.info(f"Loaded {len(self.servers)} servers from {self.hosts_file}")
            
        except Exception as e:
            logger.error(f"Error loading hosts: {e}", exc_info=True)
            self.servers = []
    
    def save(self) -> None:
        """Save current hosts to YAML file"""
        data = {
            'servers': [
                {
                    'name': s.name,
                    'host': s.host,
                    'user': s.user,
                    'password': s.password,
                    'port': s.port,
                    'description': s.description,
                    'tags': s.tags
                }
                for s in self.servers
            ],
            'default_server': self.default_server
        }
        
        try:
            with open(self.hosts_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved {len(self.servers)} servers to {self.hosts_file}")
        except Exception as e:
            logger.error(f"Error saving hosts: {e}", exc_info=True)
    
    def _create_default_hosts_file(self) -> None:
        """Create default hosts.yaml with example"""
        default_data = {
            'servers': [
                {
                    'name': 'Example Server',
                    'host': '127.0.0.1',
                    'user': 'user',
                    'password': 'password',
                    'port': 22,
                    'description': 'Example server configuration - replace with your server details',
                    'tags': ['example']
                }
            ],
            'default_server': None  # No auto-connect until configured
        }
        
        try:
            with open(self.hosts_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_data, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Created default hosts file: {self.hosts_file}")
            self.load()
        except Exception as e:
            logger.error(f"Error creating default hosts file: {e}", exc_info=True)
    
    def list_servers(self) -> List[Dict]:
        """Get list of all servers (for MCP tool)"""
        return [
            {
                'name': s.name,
                'host': s.host,
                'user': s.user,
                'port': s.port,
                'description': s.description,
                'tags': s.tags,
                'is_current': s == self.current_server
            }
            for s in self.servers
        ]
    
    def find_server(self, identifier: str) -> Optional[ServerHost]:
        """Find server by name, IP, or tag"""
        for server in self.servers:
            if server.matches_identifier(identifier):
                return server
        return None
    
    def add_server(self, name: str, host: str, user: str, 
                   password: str, port: int = 22, 
                   description: str = "", tags: List[str] = None) -> ServerHost:
        """Add a new server configuration"""
        # Check for duplicate name
        if self.find_server(name):
            raise ValueError(f"Server '{name}' already exists")
        
        server = ServerHost(
            name=name,
            host=host,
            user=user,
            password=password,
            port=port,
            description=description,
            tags=tags or []
        )
        
        self.servers.append(server)
        self.save()
        logger.info(f"Added server: {name}")
        return server
    
    def remove_server(self, identifier: str) -> bool:
        """Remove a server by name or host"""
        server = self.find_server(identifier)
        if not server:
            return False
        
        self.servers.remove(server)
        
        # Clear current if it was the removed server
        if self.current_server == server:
            self.current_server = None
        
        # Clear default if it was the removed server
        if self.default_server == server.name:
            self.default_server = None
        
        self.save()
        logger.info(f"Removed server: {server.name}")
        return True
    
    def update_server(self, identifier: str, **kwargs) -> Optional[ServerHost]:
        """Update a server's properties"""
        server = self.find_server(identifier)
        if not server:
            return None
        
        # Update provided fields
        for key, value in kwargs.items():
            if hasattr(server, key) and value is not None:
                setattr(server, key, value)
        
        self.save()
        logger.info(f"Updated server: {server.name}")
        return server
    
    def set_current(self, identifier: str) -> Optional[ServerHost]:
        """Set the current server for connection"""
        server = self.find_server(identifier)
        if server:
            self.current_server = server
            logger.info(f"Current server set to: {server.name}")
        return server
    
    def get_current(self) -> Optional[ServerHost]:
        """Get current server"""
        return self.current_server
    
    def get_default(self) -> Optional[ServerHost]:
        """Get default server"""
        if self.default_server:
            return self.find_server(self.default_server)
        return None
    
    def set_default(self, identifier: str) -> bool:
        """Set default server for auto-connect"""
        server = self.find_server(identifier)
        if server:
            self.default_server = server.name
            self.save()
            logger.info(f"Default server set to: {server.name}")
            return True
        return False
