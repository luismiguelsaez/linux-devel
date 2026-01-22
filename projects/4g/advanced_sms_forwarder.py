#!/usr/bin/env python3
"""
EC25 LTE Modem Telegram Bot - Complete Version
With SMS and Call Detection
"""

import serial
import time
import logging
import logging.handlers
import json
import os
import subprocess
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
MODEM_PORT = '/dev/ttyUSB2'
BAUDRATE = 115200
CHECK_INTERVAL = 30
AUTHORIZED_USERS_FILE = '/var/lib/ec25-bot/authorized_users.json'
SEEN_MESSAGES_FILE = '/var/lib/ec25-bot/seen_messages.json'
LOG_FILE = '/tmp/sms_bot.log'

os.makedirs(os.path.dirname(AUTHORIZED_USERS_FILE), exist_ok=True)

# Setup logging to file with rotation
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler with rotation (max 10MB, keep 5 old files)
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Console handler (optional, for systemd journal)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Also configure root logger for telegram library logs
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)


class SeenMessagesManager:
    """Manage seen messages with persistence"""
    
    def __init__(self, filepath=SEEN_MESSAGES_FILE):
        self.filepath = filepath
        self.seen = self.load_seen()
    
    def load_seen(self):
        """Load seen messages from file"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"Error loading seen messages: {e}")
        return set()
    
    def save_seen(self):
        """Save seen messages to file"""
        try:
            with open(self.filepath, 'w') as f:
                json.dump(list(self.seen), f)
        except Exception as e:
            logger.error(f"Error saving seen messages: {e}")
    
    def mark_seen(self, msg_id):
        """Mark message as seen"""
        self.seen.add(msg_id)
        self.save_seen()
    
    def is_seen(self, msg_id):
        """Check if message was seen"""
        return msg_id in self.seen
    
    def clear(self):
        """Clear all seen messages"""
        self.seen.clear()
        self.save_seen()


class UserManager:
    """Manage authorized users"""
    
    def __init__(self, filepath=AUTHORIZED_USERS_FILE):
        self.filepath = filepath
        self.users = self.load_users()
    
    def load_users(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"Error loading users: {e}")
        return set()
    
    def save_users(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(list(self.users), f)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
    
    def add_user(self, chat_id):
        self.users.add(chat_id)
        self.save_users()
    
    def is_authorized(self, chat_id):
        return chat_id in self.users
    
    def get_all_users(self):
        return list(self.users)


class CallMonitor:
    """Monitor for incoming calls in background"""
    
    def __init__(self, baudrate=115200):
        self.baudrate = baudrate
        self.ser = None
        self.monitoring = False
        self.thread = None
        self.callback = None
        self.port = None
    
    def find_available_port(self):
        """Find an available port that's not being used by main modem"""
        import glob
        
        # Get all ttyUSB ports
        all_ports = sorted(glob.glob('/dev/ttyUSB*'))
        
        if not all_ports:
            logger.error("No ttyUSB ports found")
            return None
        
        logger.info(f"Available ports for call monitoring: {all_ports}")
        
        # Try each port to find one that responds to AT
        # Prefer higher numbered ports (less likely to be used for data)
        for port in reversed(all_ports):
            try:
                logger.info(f"Testing {port} for call monitoring...")
                test_ser = serial.Serial(port, self.baudrate, timeout=1)
                time.sleep(0.3)
                test_ser.write(b'AT\r\n')
                time.sleep(0.5)
                response = test_ser.read(test_ser.in_waiting).decode('utf-8', errors='ignore')
                test_ser.close()
                
                if 'OK' in response:
                    logger.info(f"Port {port} responds to AT commands - using for call monitoring")
                    return port
                else:
                    logger.debug(f"Port {port} no AT response: {repr(response)}")
            except Exception as e:
                logger.debug(f"Port {port} failed: {e}")
                continue
        
        # If no port responds, just use the last one
        if all_ports:
            logger.warning(f"No port responded to AT, using {all_ports[-1]}")
            return all_ports[-1]
        
        return None
    
    def set_callback(self, callback):
        """Set callback function to call when call is detected"""
        self.callback = callback
    
    def start(self):
        """Start monitoring in background thread"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Call monitoring thread started")
    
    def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        logger.info("Call monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        retry_delay = 10
        
        while self.monitoring:
            try:
                # Find available port
                if not self.port:
                    self.port = self.find_available_port()
                    if not self.port:
                        logger.error("No port available for call monitoring")
                        time.sleep(retry_delay)
                        continue
                
                # Connect to modem
                logger.info(f"Connecting call monitor to {self.port}...")
                self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
                time.sleep(0.5)
                
                # Enable caller ID
                self.ser.write(b'AT+CLIP=1\r\n')
                time.sleep(0.5)
                response = self.ser.read(self.ser.in_waiting)
                logger.info(f"CLIP enabled on {self.port}: {repr(response)}")
                
                logger.info(f"Call monitor active on {self.port}")
                
                # Monitor for RING and CLIP
                buffer = ""
                while self.monitoring:
                    if self.ser.in_waiting:
                        data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                        buffer += data
                        
                        # Check for incoming call indicators
                        if 'RING' in buffer or '+CLIP:' in buffer:
                            logger.info(f"Call detected: {repr(buffer)}")
                            self._handle_call(buffer)
                            buffer = ""  # Clear buffer after handling
                    
                    time.sleep(0.5)
                    
            except serial.SerialException as e:
                logger.error(f"Serial error in call monitor: {e}")
                if self.ser:
                    try:
                        self.ser.close()
                    except:
                        pass
                self.ser = None
                
                # If port disappeared, reset and try to find again
                if "could not open port" in str(e) or "device reports readiness" in str(e):
                    logger.warning("Port lost, will try to find new port")
                    self.port = None
                
                if self.monitoring:
                    logger.info(f"Retrying call monitor in {retry_delay}s...")
                    time.sleep(retry_delay)
                    
            except Exception as e:
                logger.error(f"Unexpected error in call monitor: {e}", exc_info=True)
                if self.ser:
                    try:
                        self.ser.close()
                    except:
                        pass
                
                if self.monitoring:
                    time.sleep(retry_delay)
    
    def _handle_call(self, data):
        """Parse and handle incoming call"""
        caller_id = "Unknown"
        
        # Try to extract caller ID from +CLIP
        if '+CLIP:' in data:
            try:
                # +CLIP: "+34612345678",145,"",0,"",0
                clip_part = data.split('+CLIP:')[1].split('\r')[0]
                caller_id = clip_part.split(',')[0].strip().strip('"')
                logger.info(f"Parsed caller ID: {caller_id}")
            except Exception as e:
                logger.error(f"Error parsing caller ID: {e}")
        
        # Call the callback if set
        if self.callback:
            try:
                self.callback(caller_id)
            except Exception as e:
                logger.error(f"Error in call callback: {e}")


class EC25Modem:
    """EC25 Modem interface with improved connection handling"""
    
    def __init__(self, port=MODEM_PORT, baudrate=BAUDRATE, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
    
    def find_working_port(self):
        """Try to find which ttyUSB port responds to AT commands"""
        ports_to_try = ['/dev/ttyUSB2', '/dev/ttyUSB3', '/dev/ttyUSB1', '/dev/ttyUSB0']
        
        for port in ports_to_try:
            try:
                test_ser = serial.Serial(port, self.baudrate, timeout=1)
                time.sleep(0.3)
                test_ser.write(b'AT\r\n')
                time.sleep(0.5)
                response = test_ser.read(test_ser.in_waiting).decode('utf-8', errors='ignore')
                test_ser.close()
                
                if 'OK' in response:
                    logger.info(f"Found working AT port for modem: {port}")
                    return port
            except Exception as e:
                logger.debug(f"Port {port} failed: {e}")
                continue
        
        return None
    
    def kill_blocking_processes(self):
        """Kill processes that might be blocking the port"""
        try:
            subprocess.run(['pkill', 'screen'], stderr=subprocess.DEVNULL)
            time.sleep(0.3)
        except:
            pass
    
    def connect(self):
        """Connect to modem with auto port detection"""
        try:
            self.kill_blocking_processes()
            
            working_port = self.find_working_port()
            if working_port:
                self.port = working_port
            
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(0.5)
            
            self._send_command('AT', wait_time=0.5)
            self._send_command('AT+CMGF=1', wait_time=0.5)
            self._send_command('AT+CSCS="GSM"', wait_time=0.5)
            
            logger.debug(f"Connected to modem on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to modem: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from modem"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                logger.debug("Disconnected from modem")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
    
    def _send_command(self, command, wait_time=1):
        """Send AT command and return response"""
        if not self.ser or not self.ser.is_open:
            logger.error("Serial port not open")
            return "Error: Modem not connected"
        
        try:
            self.ser.reset_input_buffer()
            self.ser.write((command + '\r\n').encode())
            time.sleep(wait_time)
            response = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
            logger.debug(f"Command: {command}, Response: {repr(response[:100])}")
            return response
        except Exception as e:
            logger.error(f"Error sending command '{command}': {e}")
            return f"Error: {str(e)}"
    
    def get_all_messages_with_status(self):
        """Get ALL messages (read and unread) with full details"""
        messages = []
        
        for storage in ["SM", "ME"]:
            self._send_command(f'AT+CPMS="{storage}","{storage}","{storage}"')
            response = self._send_command('AT+CMGL="ALL"', wait_time=2)
            
            if '+CMGL:' in response:
                lines = response.split('\r\n')
                i = 0
                while i < len(lines):
                    if lines[i].startswith('+CMGL:'):
                        try:
                            parts = lines[i].split(',')
                            if len(parts) >= 3:
                                index = parts[0].split(':')[1].strip()
                                status = parts[1].strip('"')
                                sender = parts[2].strip('"')
                                
                                timestamp = ""
                                if len(parts) >= 5:
                                    timestamp = parts[4].strip('"')
                                
                                if i + 1 < len(lines) and lines[i + 1].strip():
                                    text = lines[i + 1].strip()
                                    
                                    messages.append({
                                        'storage': storage,
                                        'index': index,
                                        'status': status,
                                        'sender': sender,
                                        'timestamp': timestamp,
                                        'text': text,
                                        'id': f"{storage}_{index}_{sender}_{timestamp}"
                                    })
                        except Exception as e:
                            logger.error(f"Error parsing message line: {e}")
                    i += 1
        
        logger.info(f"Found {len(messages)} total messages")
        return messages
    
    def list_all_messages(self):
        """List all messages (formatted for display)"""
        result = ""
        for storage in ["SM", "ME"]:
            self._send_command(f'AT+CPMS="{storage}","{storage}","{storage}"')
            result += f"=== {storage} Storage ===\n"
            response = self._send_command('AT+CMGL="ALL"', wait_time=2)
            result += response + "\n\n"
        return result if result.strip() else "No messages found"
    
    def send_sms(self, number, message):
        """Send SMS"""
        self._send_command(f'AT+CMGS="{number}"', wait_time=0.5)
        self.ser.write((message + '\x1A').encode())
        time.sleep(2)
        response = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
        return response
    
    def delete_message(self, index, storage="SM"):
        """Delete message"""
        self._send_command(f'AT+CPMS="{storage}","{storage}","{storage}"')
        return self._send_command(f'AT+CMGD={index}')
    
    def answer_call(self):
        """Answer incoming call"""
        return self._send_command('ATA')
    
    def hangup_call(self):
        """Hangup call"""
        return self._send_command('ATH')
    
    def reject_call(self):
        """Reject incoming call"""
        return self._send_command('AT+CHUP')
    
    def get_signal_strength(self):
        """Get signal strength"""
        response = self._send_command('AT+CSQ', wait_time=1)
        
        if '+CSQ:' in response:
            try:
                rssi_part = response.split('+CSQ:')[1].split('\r')[0].strip()
                rssi = int(rssi_part.split(',')[0].strip())
                
                if rssi == 99:
                    return "No signal"
                elif rssi >= 20:
                    return f"Excellent (RSSI: {rssi})"
                elif rssi >= 15:
                    return f"Good (RSSI: {rssi})"
                elif rssi >= 10:
                    return f"Fair (RSSI: {rssi})"
                else:
                    return f"Poor (RSSI: {rssi})"
            except Exception as e:
                logger.error(f"Error parsing signal: {e}")
                return f"Raw response: {response}"
        
        return f"No signal data (raw: {response})"
    
    def get_registration(self):
        """Get network registration"""
        response = self._send_command('AT+CREG?', wait_time=1)
        if '+CREG:' in response:
            return response.split('\r\n')[0]
        return response
    
    def get_operator(self):
        """Get current operator"""
        response = self._send_command('AT+COPS?', wait_time=1)
        if '+COPS:' in response:
            return response.split('\r\n')[0]
        return response


# Global instances
modem = EC25Modem()
user_manager = UserManager()
seen_manager = SeenMessagesManager()
call_monitor = None
telegram_app = None


def authorized_only(func):
    """Decorator for authorization check"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not user_manager.is_authorized(chat_id):
            await update.message.reply_text("Unauthorized. Contact administrator.")
            logger.warning(f"Unauthorized access from {chat_id}")
            return
        return await func(update, context)
    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    chat_id = update.effective_chat.id
    
    if not user_manager.is_authorized(chat_id):
        user_manager.add_user(chat_id)
        logger.info(f"New user authorized: {chat_id}")
    
    welcome_msg = """EC25 Modem Telegram Bot

📨 SMS Commands:
/list - List all SMS
/send <number> <message> - Send SMS
/delete <storage> <index> - Delete SMS
  Storage: SM (SIM) or ME (Modem)

📞 Call Commands:
/answer - Answer incoming call
/hangup - Hangup current call
/reject - Reject incoming call

📡 Status:
/signal - Signal strength
/network - Network info
/storage - Storage info

🔧 Other:
/clear - Clear seen messages cache
/help - This message

📬 Automatic notifications for SMS and calls!
"""
    await update.message.reply_text(welcome_msg)


@authorized_only
async def list_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all messages"""
    await update.message.reply_text("Fetching messages...")
    
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem.list_all_messages()
        modem.disconnect()
        
        if len(result) > 4000:
            chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(result)
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")


@authorized_only
async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send SMS"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /send <number> <message>")
        return
    
    number = context.args[0]
    message = ' '.join(context.args[1:])
    
    await update.message.reply_text(f"Sending SMS to {number}...")
    logger.info(f"User {update.effective_chat.id} sending SMS to {number}")
    
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem.send_sms(number, message)
        modem.disconnect()
        
        if 'OK' in result:
            await update.message.reply_text(f"SMS sent to {number}")
            logger.info(f"SMS sent successfully to {number}")
        else:
            await update.message.reply_text(f"Failed to send:\n{result}")
            logger.error(f"Failed to send SMS to {number}: {result}")
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")
        logger.error(f"Exception sending SMS: {e}")


@authorized_only
async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete message"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /delete <storage> <index>\nStorage: SM or ME")
        return
    
    storage = context.args[0].upper()
    index = context.args[1]
    
    if storage not in ["SM", "ME"]:
        await update.message.reply_text("Storage must be SM (SIM) or ME (Modem)")
        return
    
    logger.info(f"User {update.effective_chat.id} deleting message {storage}[{index}]")
    
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem.delete_message(index, storage)
        modem.disconnect()
        
        if 'OK' in result:
            await update.message.reply_text(f"Deleted from {storage}[{index}]")
            logger.info(f"Message {storage}[{index}] deleted successfully")
        else:
            await update.message.reply_text(f"Failed to delete:\n{result}")
            logger.error(f"Failed to delete {storage}[{index}]: {result}")
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")
        logger.error(f"Exception deleting message: {e}")


@authorized_only
async def answer_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer incoming call"""
    logger.info(f"User {update.effective_chat.id} answering call")
    
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem.answer_call()
        modem.disconnect()
        
        if 'OK' in result:
            await update.message.reply_text("Call answered")
            logger.info("Call answered successfully")
        else:
            await update.message.reply_text(f"Answer result:\n{result}")
            logger.warning(f"Answer call result: {result}")
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")
        logger.error(f"Exception answering call: {e}")


@authorized_only
async def hangup_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hangup current call"""
    logger.info(f"User {update.effective_chat.id} hanging up call")
    
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem.hangup_call()
        modem.disconnect()
        
        if 'OK' in result:
            await update.message.reply_text("Call ended")
            logger.info("Call ended successfully")
        else:
            await update.message.reply_text(f"Hangup result:\n{result}")
            logger.warning(f"Hangup call result: {result}")
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")
        logger.error(f"Exception hanging up call: {e}")


@authorized_only
async def reject_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject incoming call"""
    logger.info(f"User {update.effective_chat.id} rejecting call")
    
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem.reject_call()
        modem.disconnect()
        
        if 'OK' in result:
            await update.message.reply_text("Call rejected")
            logger.info("Call rejected successfully")
        else:
            await update.message.reply_text(f"Reject result:\n{result}")
            logger.warning(f"Reject call result: {result}")
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")
        logger.error(f"Exception rejecting call: {e}")


@authorized_only
async def signal_strength(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check signal strength"""
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem.get_signal_strength()
        modem.disconnect()
        await update.message.reply_text(f"Signal: {result}")
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")


@authorized_only
async def network_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get network information"""
    await update.message.reply_text("Fetching network info...")
    
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = "Network Information:\n\n"
        result += modem.get_registration() + "\n"
        result += modem.get_operator() + "\n"
        result += "Signal: " + modem.get_signal_strength()
        modem.disconnect()
        
        await update.message.reply_text(result)
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")


@authorized_only
async def storage_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get storage information"""
    if not modem.connect():
        await update.message.reply_text("Failed to connect to modem")
        return
    
    try:
        result = modem._send_command('AT+CPMS?')
        modem.disconnect()
        await update.message.reply_text(f"Storage Info:\n{result}")
    except Exception as e:
        modem.disconnect()
        await update.message.reply_text(f"Error: {str(e)}")


@authorized_only
async def clear_seen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear seen messages cache"""
    seen_manager.clear()
    logger.info(f"User {update.effective_chat.id} cleared seen messages cache")
    await update.message.reply_text("Cleared seen messages cache. You'll be notified about all existing messages on next check.")


def handle_incoming_call(caller_id):
    """Handle incoming call notification"""
    logger.info(f"Incoming call from: {caller_id}")
    
    text = f"""📞 Incoming Call

From: {caller_id}

Use /answer to answer
Use /reject to reject
Use /hangup to hangup
"""
    
    # Send notification to all authorized users
    if telegram_app:
        for chat_id in user_manager.get_all_users():
            try:
                import asyncio
                # Create task in the event loop
                asyncio.create_task(
                    telegram_app.bot.send_message(chat_id=chat_id, text=text)
                )
                logger.info(f"Sent call notification to user {chat_id}")
            except Exception as e:
                logger.error(f"Error sending call notification to {chat_id}: {e}")


async def check_new_messages(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check for new messages"""
    logger.info("=== Checking for new SMS ===")
    
    if not modem.connect():
        logger.warning("Failed to connect for message check")
        return
    
    try:
        messages = modem.get_all_messages_with_status()
        logger.info(f"Retrieved {len(messages)} messages from modem")
        
        new_count = 0
        for msg in messages:
            msg_id = msg['id']
            
            if not seen_manager.is_seen(msg_id):
                logger.info(f"New message detected: {msg_id}")
                new_count += 1
                
                text = f"""📩 New SMS

From: {msg['sender']}
Storage: {msg['storage']} [{msg['index']}]
Status: {msg['status']}
Time: {msg['timestamp']}

{msg['text']}
"""
                for chat_id in user_manager.get_all_users():
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=text)
                        logger.info(f"Sent SMS notification to user {chat_id}")
                    except Exception as e:
                        logger.error(f"Error sending SMS notification to {chat_id}: {e}")
                
                seen_manager.mark_seen(msg_id)
        
        if new_count == 0:
            logger.debug("No new messages")
        else:
            logger.info(f"Notified about {new_count} new messages")
            
    except Exception as e:
        logger.error(f"Error in message check: {e}", exc_info=True)
    finally:
        modem.disconnect()


def main():
    """Start the bot"""
    global telegram_app, call_monitor
    
    logger.info("=" * 60)
    logger.info("EC25 Telegram Bot Starting")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Authorized users file: {AUTHORIZED_USERS_FILE}")
    logger.info(f"Seen messages file: {SEEN_MESSAGES_FILE}")
    logger.info("=" * 60)
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app = application
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("list", list_messages))
    application.add_handler(CommandHandler("send", send_message))
    application.add_handler(CommandHandler("delete", delete_message))
    application.add_handler(CommandHandler("answer", answer_call))
    application.add_handler(CommandHandler("hangup", hangup_call))
    application.add_handler(CommandHandler("reject", reject_call))
    application.add_handler(CommandHandler("signal", signal_strength))
    application.add_handler(CommandHandler("network", network_info))
    application.add_handler(CommandHandler("storage", storage_info))
    application.add_handler(CommandHandler("clear", clear_seen))
    
    logger.info("Registered all command handlers")
    
    # Background job for checking messages
    application.job_queue.run_repeating(
        check_new_messages,
        interval=CHECK_INTERVAL,
        first=10
    )
    logger.info(f"Started SMS check job (interval: {CHECK_INTERVAL}s)")
    
    # Start call monitoring with auto port detection
    call_monitor = CallMonitor()
    call_monitor.set_callback(handle_incoming_call)
    call_monitor.start()
    
    logger.info("Starting EC25 Telegram Bot with SMS and call detection...")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if call_monitor:
            call_monitor.stop()
        logger.info("EC25 Telegram Bot stopped")


if __name__ == '__main__':
    main()
