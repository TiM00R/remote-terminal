#!/bin/bash
# WiFi Setup and Configuration Diagnostics
# Created from conversation #1 (2025-11-21)
# Goal: Investigate wifi setup and configuration
# Status: Success

echo "=== WiFi Diagnostics Script ==="
echo "Started: $(date)"
echo ""

# Section 1: Network Interfaces
echo "=== [1/7] Network Interfaces Overview ==="
ip link show
echo ""

# Section 2: WiFi Interface Details
echo "=== [2/7] WiFi Interface IP Configuration ==="
# Note: Replace 'wlp3s0' with your actual wifi interface name if different
WIFI_INTERFACE=$(ip link show | grep -oP 'wlp\w+|wlan\w+' | head -1)
if [ -z "$WIFI_INTERFACE" ]; then
    echo "No WiFi interface found!"
else
    echo "WiFi Interface: $WIFI_INTERFACE"
    ip addr show $WIFI_INTERFACE
fi
echo ""

# Section 3: WiFi Signal and Connection Status
echo "=== [3/7] WiFi Signal and Connection Status ==="
if [ ! -z "$WIFI_INTERFACE" ]; then
    iwconfig $WIFI_INTERFACE
fi
echo ""

# Section 4: NetworkManager Status
echo "=== [4/7] NetworkManager Service Status ==="
systemctl status NetworkManager --no-pager
echo ""

# Section 5: Connection Profiles
echo "=== [5/7] NetworkManager Connection Profiles ==="
nmcli connection show
echo ""

# Section 6: Available WiFi Networks
echo "=== [6/7] Available WiFi Networks ==="
nmcli device wifi list
echo ""

# Section 7: Routing and DNS
echo "=== [7/7] Routing Table ==="
ip route show
echo ""
echo "=== DNS Configuration ==="
cat /etc/resolv.conf
echo ""
echo "=== DNS Resolver Status ==="
resolvectl status
echo ""

echo "=== Diagnostics Complete ==="
echo "Completed: $(date)"
