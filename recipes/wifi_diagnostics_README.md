# WiFi Diagnostics Recipe

**Created from:** Conversation #1 (2025-11-21)  
**Goal:** Investigate wifi setup and configuration  
**Status:** Success  
**Server:** OBD Server (obd@10.0.60.24)

## Overview

This recipe performs comprehensive WiFi diagnostics on Linux systems using NetworkManager. It checks:
- Network interfaces
- WiFi connection status and signal strength
- NetworkManager service status
- Saved connection profiles
- Available WiFi networks
- Routing configuration
- DNS setup

## Usage

### Basic Usage
```bash
bash wifi_diagnostics.sh
```

### With Output Logging
```bash
bash wifi_diagnostics.sh | tee wifi_diagnostics_output.txt
```

### With Sudo (for detailed NetworkManager logs)
```bash
sudo bash wifi_diagnostics.sh
```

## What to Expect

The script will output 7 sections:

1. **Network Interfaces** - Shows all network interfaces (ethernet, wifi, loopback, docker)
2. **WiFi Interface IP** - Detailed IP configuration of the WiFi interface
3. **WiFi Signal Status** - Connection quality, signal level, bit rate
4. **NetworkManager Status** - Service status and recent log entries
5. **Connection Profiles** - Saved WiFi networks and their UUIDs
6. **Available Networks** - WiFi networks in range with signal strength
7. **Routing and DNS** - Routing table, DNS servers, resolver status

## Original Conversation Results

The original investigation found:
- WiFi interface: `wlp3s0`
- Connected network: `CAPECOD` (10.0.60.24/24)
- Signal strength: Good (-45 dBm, 65/70 quality)
- Security: WPA2-PSK
- DNS: Using systemd-resolved (127.0.0.53)
- Additional saved profile: `ZIM-WIFI` (not connected)

## Requirements

- Linux with NetworkManager
- `ip`, `iwconfig`, `nmcli`, `resolvectl` commands
- WiFi hardware

## Notes

- Script auto-detects WiFi interface name (wlp3s0, wlan0, etc.)
- No modifications are made - diagnostics only
- Safe to run on any Linux system with NetworkManager
