# EC25 LTE Modem Installation Guide for Arch Linux

This guide covers the complete setup of a Quectel EC25 LTE modem on Arch Linux, including hardware setup, network connectivity, and SMS functionality.

## Table of Contents
1. [Hardware Setup](#hardware-setup)
2. [Software Installation](#software-installation)
3. [Initial Modem Detection](#initial-modem-detection)
4. [Network Configuration](#network-configuration)
5. [SMS Configuration](#sms-configuration)
6. [Troubleshooting](#troubleshooting)
7. [Automation Scripts](#automation-scripts)

---

## Hardware Setup

### Antenna Connections

The EC25 has 3 antenna connectors:

- **MAIN** - Primary LTE antenna (REQUIRED)
- **DIV** - Diversity antenna (recommended for better performance)
- **GNSS** - GPS/GLONASS antenna (optional)

**Minimum setup**: Connect one 4G antenna to the **MAIN** connector.

**Recommended setup**: Connect antennas to both **MAIN** and **DIV** for improved signal quality and data throughput.

### SIM Card Installation

1. Power off the modem
2. Insert SIM card (micro-SIM or nano-SIM with adapter)
3. Ensure proper orientation (notch alignment)
4. Verify SIM is fully seated

### Power Requirements

The EC25 can draw up to **2A during operation**, especially during:
- Network search/registration
- Data transmission
- Initial enumeration

**Important**: Use a powered USB hub if connecting to Raspberry Pi or if experiencing disconnection issues.

---

## Software Installation

### Install Required Packages
```bash
# Install modem management tools
sudo pacman -S modemmanager libqmi libmbim usb_modeswitch

# Install serial communication tools
sudo pacman -S minicom screen picocom

# Install Python for SMS scripting (optional)
sudo pacman -S python-pyserial
```

### Load Kernel Modules
```bash
# Load required modules
sudo modprobe qmi_wwan
sudo modprobe cdc_wdm
sudo modprobe option
sudo modprobe usb_wwan

# Make modules load automatically on boot
sudo tee /etc/modules-load.d/ec25.conf <<EOF
qmi_wwan
cdc_wdm
option
usb_wwan
EOF
```

### Configure User Permissions
```bash
# Add your user to uucp group
sudo usermod -aG uucp $USER

# Apply group membership (or log out/in)
newgrp uucp
```

---

## Initial Modem Detection

### Verify USB Detection
```bash
# Check if modem is detected
lsusb | grep -i quectel
# Expected: Bus 001 Device XXX: ID 2c7c:0125 Quectel Wireless Solutions Co., Ltd. EC25 LTE modem

# Check for serial ports
ls -l /dev/ttyUSB*
# Expected: /dev/ttyUSB0, /dev/ttyUSB1, /dev/ttyUSB2, /dev/ttyUSB3

# Check for QMI device
ls -l /dev/cdc-wdm0

# View kernel messages
dmesg | grep -i quectel
```

### Port Functions

The EC25 typically creates 4 USB serial ports:
- **/dev/ttyUSB0** - DM (Diagnostic)
- **/dev/ttyUSB1** - GNSS/GPS
- **/dev/ttyUSB2** - AT commands (primary)
- **/dev/ttyUSB3** - AT commands (secondary)

---

## Network Configuration

### Step 1: Test Basic Communication

Connect to the modem using screen (typically ttyUSB2 or ttyUSB3):
```bash
screen /dev/ttyUSB2 115200
```

Test basic AT commands:
```
AT                    # Should return OK
AT+CPIN?              # Check SIM status (should return READY)
AT+CSQ                # Check signal quality (>10 is good)
AT+CREG?              # Check registration (0,1 or 0,5 means registered)
AT+COPS?              # Check operator
```

**To exit screen**: Press `Ctrl+A`, then `K`, then `Y`

### Step 2: Configure USB Network Mode

Set the modem to QMI mode:
```bash
screen /dev/ttyUSB2 115200
```
```
AT+QCFG="usbnet"           # Check current mode
AT+QCFG="usbnet",0         # Set to QMI mode (0=QMI, 1=ECM, 2=MBIM)
AT+CFUN=1,1                # Reboot modem to apply changes
```

Wait 15-20 seconds for the modem to reboot.

### Step 3: Disable ModemManager (Recommended)

ModemManager can interfere with manual configuration. Disable it:
```bash
# Stop and disable ModemManager
sudo systemctl stop ModemManager
sudo systemctl disable ModemManager
sudo systemctl mask ModemManager

# Kill qmi-proxy if running
sudo pkill qmi-proxy
```

### Step 4: Fix Device Permissions
```bash
# Change permissions on cdc-wdm0
sudo chmod 666 /dev/cdc-wdm0

# Create permanent udev rule
sudo tee /etc/udev/rules.d/99-quectel.conf <<'EOF'
SUBSYSTEM=="usbmisc", ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0125", GROUP="uucp", MODE="0660"
EOF

sudo udevadm control --reload-rules
```

### Step 5: Disable USB Autosuspend

Prevent the modem from being suspended:
```bash
# Disable USB autosuspend globally
echo 'options usbcore autosuspend=-1' | sudo tee /etc/modprobe.d/disable-usb-autosuspend.conf

# Or for specific device (replace 1-13 with your device path from dmesg)
echo -1 | sudo tee /sys/bus/usb/devices/1-13/power/autosuspend
```

### Step 6: Start Network Connection
```bash
# Start network connection (replace APN with your carrier's APN)
sudo qmicli -d /dev/cdc-wdm0 --wds-start-network="apn=your.apn.here,ip-type=4" --client-no-release-cid

# Note the returned CID and Packet Data Handle for later
```

### Step 7: Configure Network Interface
```bash
# Find your network interface name
ip link show | grep -E "wwan|wwp"
# Expected: wwp0s20f0u13i4 or wwan0

# Set interface to raw IP mode (replace with your interface name)
echo Y | sudo tee /sys/class/net/wwp0s20f0u13i4/qmi/raw_ip

# Bring interface down and up
sudo ip link set wwp0s20f0u13i4 down
sudo ip link set wwp0s20f0u13i4 up

# Get network settings from modem
sudo qmicli -d /dev/cdc-wdm0 --wds-get-current-settings
```

### Step 8: Apply Network Configuration

Using the settings from the previous command:
```bash
# Configure IP address (use values from qmicli output)
sudo ip addr add 10.xx.xx.xx/29 dev wwp0s20f0u13i4

# Add default route
sudo ip route add default via 10.xx.xx.xx dev wwp0s20f0u13i4

# Set MTU
sudo ip link set wwp0s20f0u13i4 mtu 1430

# Configure DNS
sudo bash -c 'cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF'
```

### Step 9: Test Connectivity
```bash
# Test with IP
ping -c 4 8.8.8.8

# Test with DNS
ping -c 4 google.com

# Test with specific interface
ping -I wwp0s20f0u13i4 -c 4 8.8.8.8
```

### Common APNs by Carrier

| Carrier | Country | APN |
|---------|---------|-----|
| Vodafone | Spain | vodafone.es |
| Movistar | Spain | movistar.es |
| Orange | Spain | internet |
| Lowi | Spain | lowi.vodafone.es or lowi.private.omv.es |
| AT&T | USA | broadband |
| T-Mobile | USA | fast.t-mobile.com |
| Verizon | USA | vzwinternet |

---

## SMS Configuration

### Using AT Commands

Connect to the modem:
```bash
screen /dev/ttyUSB2 115200
```

Basic SMS commands:
```
AT+CMGF=1                      # Set SMS to text mode
AT+CSCS="GSM"                  # Set character set
AT+CNMI=2,1,0,0,0              # Configure new message notifications

# List messages
AT+CMGL="ALL"                  # List all messages
AT+CMGL="REC UNREAD"           # List unread messages
AT+CMGR=1                      # Read message at index 1

# Send SMS
AT+CMGS="+34612345678"         # Replace with destination number
> Type your message here       # After >, type message
<Ctrl+Z>                       # Press Ctrl+Z to send

# Delete SMS
AT+CMGD=1                      # Delete message at index 1

# Check storage
AT+CPMS?                       # Check SMS storage status
AT+CPMS="SM","SM","SM"         # Use SIM storage
AT+CPMS="ME","ME","ME"         # Use modem storage
```

### Python SMS Script

Create `/usr/local/bin/ec25_sms.py`:
```python
#!/usr/bin/env python3
import serial
import time
import sys

class EC25_SMS:
    def __init__(self, port='/dev/ttyUSB2', baudrate=115200, timeout=1):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(0.5)
        self._send_command('AT+CMGF=1')  # Text mode
        self._send_command('AT+CSCS="GSM"')  # Character set
        
    def _send_command(self, command, wait_time=1):
        """Send AT command and return response"""
        self.ser.write((command + '\r\n').encode())
        time.sleep(wait_time)
        response = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
        return response
    
    def list_all_storage_locations(self):
        """List messages from all storage locations"""
        result = ""
        
        # Check SIM
        self._send_command('AT+CPMS="SM","SM","SM"')
        result += "=== Messages in SIM (SM) ===\n"
        result += self._send_command('AT+CMGL="ALL"', wait_time=2) + "\n"
        
        # Check Modem Memory
        self._send_command('AT+CPMS="ME","ME","ME"')
        result += "\n=== Messages in Modem Memory (ME) ===\n"
        result += self._send_command('AT+CMGL="ALL"', wait_time=2) + "\n"
        
        return result
    
    def read_sms(self, index):
        """Read SMS at specific index"""
        response = self._send_command(f'AT+CMGR={index}')
        return response
    
    def send_sms(self, number, message):
        """Send SMS to number"""
        self._send_command(f'AT+CMGS="{number}"', wait_time=0.5)
        self.ser.write((message + '\x1A').encode())  # Ctrl+Z to send
        time.sleep(2)
        response = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
        return response
    
    def delete_sms(self, index):
        """Delete SMS at index"""
        response = self._send_command(f'AT+CMGD={index}')
        return response
    
    def get_signal_strength(self):
        """Get signal strength"""
        response = self._send_command('AT+CSQ')
        return response
    
    def list_storage_info(self):
        """Check SMS storage info"""
        response = self._send_command('AT+CPMS?')
        return response
    
    def close(self):
        self.ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  list - List all SMS from all storage")
        print("  read <index> - Read SMS at index")
        print("  send <number> <message> - Send SMS")
        print("  delete <index> - Delete SMS")
        print("  storage - Check storage status")
        print("  signal - Check signal strength")
        sys.exit(1)
    
    command = sys.argv[1]
    modem = EC25_SMS()
    
    try:
        if command == "list":
            print(modem.list_all_storage_locations())
        
        elif command == "read" and len(sys.argv) > 2:
            index = sys.argv[2]
            print(modem.read_sms(index))
        
        elif command == "send" and len(sys.argv) > 3:
            number = sys.argv[2]
            message = ' '.join(sys.argv[3:])
            print(f"Sending to {number}: {message}")
            result = modem.send_sms(number, message)
            print(result)
        
        elif command == "delete" and len(sys.argv) > 2:
            index = sys.argv[2]
            print(modem.delete_sms(index))
        
        elif command == "storage":
            print(modem.list_storage_info())
        
        elif command == "signal":
            print(modem.get_signal_strength())
        
        else:
            print("Invalid command or missing arguments")
    
    finally:
        modem.close()
```

Make it executable:
```bash
chmod +x /usr/local/bin/ec25_sms.py
```

Usage:
```bash
# List all messages
python /usr/local/bin/ec25_sms.py list

# Send SMS
python /usr/local/bin/ec25_sms.py send "+34612345678" "Hello from EC25"

# Read message at index 1
python /usr/local/bin/ec25_sms.py read 1

# Delete message
python /usr/local/bin/ec25_sms.py delete 1

# Check signal
python /usr/local/bin/ec25_sms.py signal

# Check storage
python /usr/local/bin/ec25_sms.py storage
```

---

## Troubleshooting

### Modem Not Detected

**Symptoms**: No ttyUSB devices or lsusb doesn't show Quectel device

**Solutions**:
1. Check physical USB connection
2. Try different USB port (preferably USB 3.0)
3. Use powered USB hub if on Raspberry Pi
4. Check for power issues (modem draws up to 2A)
5. Verify kernel modules are loaded: `lsmod | grep -E "qmi_wwan|cdc_wdm|option"`

### SIM Not Detected

**Symptoms**: `AT+CPIN?` returns `SIM not inserted` or error

**Solutions**:
1. Remove and reinsert SIM card
2. Verify SIM orientation (notch alignment)
3. Test SIM in another device
4. Check SIM size (micro-SIM or nano-SIM with adapter)
5. Reset modem: `AT+CFUN=1,1`

### Network Registration Failed

**Symptoms**: `AT+CREG?` returns `+CREG: 0,0` (not registered)

**Solutions**:
1. Check signal strength: `AT+CSQ` (should be >10)
2. Verify antenna connections (MAIN is required)
3. Check SIM is activated and has service
4. Scan for networks: `AT+COPS=?` (takes 30-60 seconds)
5. Force network selection: `AT+COPS=0`
6. Check network mode: `AT+QCFG="nwscanmode"` and set to auto: `AT+QCFG="nwscanmode",0,1`

### No Internet Connectivity

**Symptoms**: Network starts but ping fails

**Solutions**:
1. Verify interface is up: `ip link show wwp0s20f0u13i4`
2. Check IP assignment: `ip addr show wwp0s20f0u13i4`
3. Verify routing: `ip route show`
4. Check DNS: `cat /etc/resolv.conf`
5. Test with IP directly: `ping 8.8.8.8`
6. Verify APN is correct for your carrier
7. Check data connection: `AT+CGACT?` and activate: `AT+CGACT=1,1`

### QMI Timeout Errors

**Symptoms**: `qmicli` commands timeout

**Solutions**:
1. Kill qmi-proxy: `sudo pkill qmi-proxy`
2. Stop ModemManager: `sudo systemctl stop ModemManager`
3. Check permissions: `ls -l /dev/cdc-wdm0`
4. Reset modem via AT commands: `AT+CFUN=0` then `AT+CFUN=1`
5. Try ECM mode instead: `AT+QCFG="usbnet",1` then `AT+CFUN=1,1`

### Modem Keeps Disconnecting

**Symptoms**: USB device repeatedly disconnects/reconnects

**Solutions**:
1. **Use powered USB hub** (most common fix)
2. Disable USB autosuspend (see Network Configuration Step 5)
3. Connect to AC power if on laptop
4. Use USB 3.0 port for better power delivery
5. Check for loose connections

### SMS Not Working

**Symptoms**: Cannot send/receive SMS

**Solutions**:
1. Verify SIM supports SMS: `AT+CPIN?` should return `READY`
2. Check text mode: `AT+CMGF=1`
3. Check storage: `AT+CPMS?`
4. Try different storage: `AT+CPMS="ME","ME","ME"`
5. Ensure no screen sessions are blocking: `sudo pkill screen`

### Port Access Denied

**Symptoms**: Python script or screen can't access /dev/ttyUSB*

**Solutions**:
1. Kill blocking processes: `sudo lsof /dev/ttyUSB*`
2. Kill screen sessions: `sudo pkill screen`
3. Add user to uucp group: `sudo usermod -aG uucp $USER`
4. Check permissions: `ls -l /dev/ttyUSB*`

---

## Automation Scripts

### Automatic Connection on Boot

Create connection script `/usr/local/bin/ec25-connect.sh`:
```bash
#!/bin/bash
# EC25 Modem Connection Script

# Configuration
APN="your.apn.here"
INTERFACE="wwp0s20f0u13i4"  # Update with your interface name
QMI_DEVICE="/dev/cdc-wdm0"

# Wait for modem to be ready
sleep 10

# Start network connection
qmicli -d $QMI_DEVICE --wds-start-network="apn=$APN,ip-type=4" --client-no-release-cid &

# Wait for connection
sleep 5

# Get network settings
SETTINGS=$(qmicli -d $QMI_DEVICE --wds-get-current-settings)

# Extract settings (simplified - adjust for your needs)
IP=$(echo "$SETTINGS" | grep "IPv4 address:" | awk '{print $3}')
GATEWAY=$(echo "$SETTINGS" | grep "IPv4 gateway" | awk '{print $4}')
DNS1=$(echo "$SETTINGS" | grep "IPv4 primary DNS:" | awk '{print $4}')
MTU=$(echo "$SETTINGS" | grep "MTU:" | awk '{print $2}')

# Configure interface
ip link set $INTERFACE up
ip addr add ${IP}/29 dev $INTERFACE
ip route add default via $GATEWAY dev $INTERFACE
ip link set $INTERFACE mtu $MTU

# Set DNS
cat > /etc/resolv.conf << EOF
nameserver $DNS1
nameserver 8.8.8.8
EOF

echo "EC25 modem connected successfully"
```

Make executable:
```bash
sudo chmod +x /usr/local/bin/ec25-connect.sh
```

Create systemd service `/etc/systemd/system/ec25-modem.service`:
```ini
[Unit]
Description=EC25 LTE Modem Connection
After=network.target
Wants=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ec25-connect.sh
RemainAfterExit=yes
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ec25-modem.service
sudo systemctl start ec25-modem.service

# Check status
sudo systemctl status ec25-modem.service
```

### SMS Monitor Script

Create `/usr/local/bin/sms-monitor.py`:
```python
#!/usr/bin/env python3
import serial
import time
import re

class SMSMonitor:
    def __init__(self, port='/dev/ttyUSB2'):
        self.ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(0.5)
        # Configure for new message notifications
        self._send_command('AT+CMGF=1')
        self._send_command('AT+CNMI=2,1,0,0,0')
        print("Monitoring for new SMS... Press Ctrl+C to stop")
    
    def _send_command(self, command):
        self.ser.write((command + '\r\n').encode())
        time.sleep(0.5)
        self.ser.read(self.ser.in_waiting)
    
    def monitor(self):
        buffer = ""
        try:
            while True:
                if self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Check for new SMS notification
                    if '+CMT:' in buffer:
                        print("\n--- New SMS Received ---")
                        print(buffer)
                        buffer = ""
                
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopping monitor...")
            self.ser.close()

if __name__ == "__main__":
    monitor = SMSMonitor()
    monitor.monitor()
```

Make executable:
```bash
chmod +x /usr/local/bin/sms-monitor.py
```

Run:
```bash
python /usr/local/bin/sms-monitor.py
```

---

## Useful AT Commands Reference

### Network Commands
```
AT+CREG?              # Check network registration
AT+COPS?              # Check current operator
AT+COPS=?             # Scan available networks (slow)
AT+COPS=0             # Automatic network selection
AT+CSQ                # Signal quality (>10 is good, >15 is excellent)
AT+QNWINFO            # Network info (band, channel, etc.)
AT+QENG="servingcell" # Detailed serving cell info
```

### Configuration Commands
```
AT+CGDCONT?           # View PDP contexts
AT+CGDCONT=1,"IP","apn.here"  # Set APN
AT+CGACT?             # Check PDP context activation
AT+CGACT=1,1          # Activate PDP context
AT+QCFG="usbnet"      # Check USB network mode
AT+QCFG="nwscanmode"  # Check network scan mode
AT+CFUN?              # Check functionality level
AT+CFUN=1,1           # Full reset
```

### Modem Information
```
ATI                   # Modem info
AT+CGMI               # Manufacturer
AT+CGMM               # Model
AT+CGMR               # Firmware version
AT+CGSN               # IMEI
AT+QCCID              # SIM ICCID
```

### SMS Commands
```
AT+CMGF=1             # Text mode
AT+CMGL="ALL"         # List all messages
AT+CMGR=<index>       # Read message
AT+CMGS="<number>"    # Send message
AT+CMGD=<index>       # Delete message
AT+CPMS?              # Storage info
```

---

## Additional Resources

- **Quectel EC25 Hardware Design**: Official hardware integration guide
- **Quectel EC25 AT Commands Manual**: Complete AT command reference
- **qmicli Documentation**: `man qmicli` or [freedesktop.org](https://www.freedesktop.org/software/libqmi/man/latest/)
- **Arch Linux Wiki - Mobile Broadband**: [wiki.archlinux.org](https://wiki.archlinux.org/title/Mobile_broadband_modem)

---

## Notes

- The interface state showing `UNKNOWN` is normal for cellular point-to-point connections
- Sent SMS messages are typically not stored by the modem
- New received messages may appear in modem memory (ME) instead of SIM (SM)
- Signal strength varies by location - consider external antennas for better reception
- Some carriers require specific network modes or bands - check with your provider

---

**Last Updated**: January 2026
**Tested On**: Arch Linux with kernel 6.x
**Modem**: Quectel EC25 (USB ID: 2c7c:0125)
