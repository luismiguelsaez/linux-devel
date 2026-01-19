#!/usr/bin/env python3
"""
SMS to Telegram Forwarder
Monitors ModemManager for incoming SMS and forwards to Telegram
"""

import subprocess
import json
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import httpx

# Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
MODEM_INDEX = 0
CHECK_INTERVAL = 30  # seconds for periodic check
SMS_STORAGE_FILE = Path("/var/lib/sms-forwarder/processed_sms.json")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SMSForwarder:
    def __init__(self):
        self.processed_sms = self._load_processed_sms()
        self.http_client = httpx.AsyncClient()
        
    def _load_processed_sms(self) -> set:
        """Load set of already processed SMS IDs"""
        SMS_STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if SMS_STORAGE_FILE.exists():
            with open(SMS_STORAGE_FILE) as f:
                return set(json.load(f))
        return set()
    
    def _save_processed_sms(self):
        """Save processed SMS IDs"""
        # Keep only last 1000 IDs to prevent unbounded growth
        recent_ids = list(self.processed_sms)[-1000:]
        with open(SMS_STORAGE_FILE, 'w') as f:
            json.dump(recent_ids, f)
    
    def get_modem_path(self) -> str:
        """Get the modem object path"""
        result = subprocess.run(
            ['mmcli', '-L', '-J'],
            capture_output=True, text=True
        )
        modems = json.loads(result.stdout)
        if modems.get('modem-list'):
            return modems['modem-list'][MODEM_INDEX]
        raise RuntimeError("No modem found")
    
    def get_sms_list(self, modem_path: str) -> list:
        """Get list of SMS messages on the modem"""
        modem_num = modem_path.split('/')[-1]
        result = subprocess.run(
            ['mmcli', '-m', modem_num, '--messaging-list-sms', '-J'],
            capture_output=True, text=True
        )
        data = json.loads(result.stdout)
        return data.get('modem', {}).get('messaging', {}).get('sms', [])
    
    def get_sms_content(self, sms_path: str) -> dict:
        """Get content of a specific SMS"""
        sms_num = sms_path.split('/')[-1]
        result = subprocess.run(
            ['mmcli', '-s', sms_num, '-J'],
            capture_output=True, text=True
        )
        return json.loads(result.stdout).get('sms', {})
    
    def delete_sms(self, modem_path: str, sms_path: str):
        """Delete SMS from modem"""
        modem_num = modem_path.split('/')[-1]
        subprocess.run(
            ['mmcli', '-m', modem_num, '--messaging-delete-sms', sms_path],
            capture_output=True
        )
    
    async def send_to_telegram(self, sender: str, text: str, timestamp: str):
        """Send SMS content to Telegram"""
        message = (
            f"📱 *New SMS*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"*From:* `{sender}`\n"
            f"*Time:* {timestamp}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{text}"
        )
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"SMS forwarded to Telegram from {sender}")
        except Exception as e:
            logger.error(f"Failed to send to Telegram: {e}")
            raise
    
    async def process_sms(self):
        """Check for new SMS and forward to Telegram"""
        try:
            modem_path = self.get_modem_path()
            sms_list = self.get_sms_list(modem_path)
            
            for sms_path in sms_list:
                if sms_path in self.processed_sms:
                    continue
                
                sms = self.get_sms_content(sms_path)
                content = sms.get('content', {})
                
                # Only process received SMS
                if sms.get('properties', {}).get('state') != 'received':
                    continue
                
                sender = content.get('number', 'Unknown')
                text = content.get('text', '')
                timestamp = content.get('timestamp', datetime.now().isoformat())
                
                await self.send_to_telegram(sender, text, timestamp)
                
                # Mark as processed and delete from modem
                self.processed_sms.add(sms_path)
                self._save_processed_sms()
                self.delete_sms(modem_path, sms_path)
                
        except Exception as e:
            logger.error(f"Error processing SMS: {e}")
    
    async def run_periodic(self):
        """Run periodic SMS check"""
        while True:
            await self.process_sms()
            await asyncio.sleep(CHECK_INTERVAL)


class DBusSMSMonitor:
    """Monitor SMS via DBus signals for real-time notifications"""
    
    def __init__(self, forwarder: SMSForwarder):
        self.forwarder = forwarder
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        
    def setup_signal_handler(self):
        """Set up DBus signal handler for incoming SMS"""
        self.bus.add_signal_receiver(
            self.on_sms_added,
            signal_name="Added",
            dbus_interface="org.freedesktop.ModemManager1.Modem.Messaging",
            path_keyword="path"
        )
        logger.info("DBus SMS signal handler registered")
    
    def on_sms_added(self, sms_path, received, path=None):
        """Handle new SMS signal"""
        if received:
            logger.info(f"New SMS received: {sms_path}")
            # Trigger async processing
            asyncio.create_task(self.forwarder.process_sms())


async def main():
    forwarder = SMSForwarder()
    
    # Set up DBus monitoring for real-time notifications
    try:
        monitor = DBusSMSMonitor(forwarder)
        monitor.setup_signal_handler()
        logger.info("Real-time SMS monitoring enabled via DBus")
    except Exception as e:
        logger.warning(f"DBus monitoring not available: {e}")
        logger.info("Falling back to periodic polling only")
    
    # Run periodic check as backup
    logger.info(f"Starting periodic SMS check every {CHECK_INTERVAL}s")
    await forwarder.run_periodic()


if __name__ == "__main__":
    asyncio.run(main())
