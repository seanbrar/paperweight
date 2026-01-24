import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import yaml
import time
import sys
from pathlib import Path

# Configuration
CONFIG_PATH = Path("config.yaml")
MAILPIT_API_URL = "http://localhost:8025/api/v1/messages"
MAILPIT_WEB_URL = "http://localhost:8025"

def load_config():
    if not CONFIG_PATH.exists():
        print(f"❌ Config file not found: {CONFIG_PATH}")
        sys.exit(1)
    
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def send_test_email(config):
    smtp_config = config.get("notifier", {}).get("email", {})
    
    # Override for testing if not set to localhost
    smtp_server = smtp_config.get("smtp_server")
    smtp_port = smtp_config.get("smtp_port")
    
    if smtp_server != "localhost" or smtp_port != 1025:
        print(f"⚠️  Config is configured for {smtp_server}:{smtp_port}")
        print("ℹ️  For this test, we will force connection to localhost:1025 (Mailpit)")
        smtp_server = "localhost"
        smtp_port = 1025

    sender = smtp_config.get("from", "test@example.com")
    recipient = smtp_config.get("to", "user@example.com")
    
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Paperweight Validation Test"
    
    body = """
    <h1>Paperweight Email Setup Verification</h1>
    <p>If you are reading this, the email delivery pipeline is working correctly!</p>
    <ul>
        <li><b>Server:</b> Mailpit</li>
        <li><b>Time:</b> {}</li>
    </ul>
    """.format(time.strftime("%Y-%m-%d %H:%M:%S"))
    
    msg.attach(MIMEText(body, "html"))
    
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.sendmail(sender, recipient, msg.as_string())
        print(f"✅ Email sent to {recipient} via {smtp_server}:{smtp_port}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def verify_receipt():
    print("🔍 Checking Mailpit for the message...")
    # Give Mailpit a moment to index
    time.sleep(1)
    
    try:
        response = requests.get(MAILPIT_API_URL)
        response.raise_for_status()
        data = response.json()
        
        messages = data.get("messages", [])
        if not messages:
            print("❌ No messages found in Mailpit.")
            return False
            
        # Look for our most recent message
        latest = messages[0]
        if latest.get("Subject") == "Paperweight Validation Test":
            print("✅ Email verified in Mailpit!")
            print(f"🔗 View it here: {MAILPIT_WEB_URL}/view/{latest['ID']}")
            return True
        else:
            print(f"⚠️  Found a message, but subject matches '{latest.get('Subject')}'")
            return False
            
    except Exception as e:
        print(f"❌ Failed to verify with Mailpit API: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Paperweight Email Validation...")
    
    config = load_config()
    
    if send_test_email(config):
        if verify_receipt():
            print("\n🎉 SUCCESS: Email system is fully operational locally.")
        else:
            sys.exit(1)
    else:
        sys.exit(1)
