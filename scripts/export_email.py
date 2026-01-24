import requests
import html2text
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Configuration
MAILPIT_API_URL = "http://localhost:8025/api/v1"
EXPORT_DIR = Path("artifacts/emails")

def ensure_export_dir():
    if not EXPORT_DIR.exists():
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def get_latest_message():
    try:
        # Get list of messages (default limit is 50, which is fine)
        response = requests.get(f"{MAILPIT_API_URL}/messages")
        response.raise_for_status()
        data = response.json()
        
        messages = data.get("messages", [])
        if not messages:
            return None
        
        return messages[0]  # First one is the latest
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Mailpit. Is it running?")
        print("   Run: docker compose up -d")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        sys.exit(1)

def get_message_content(message_id):
    try:
        response = requests.get(f"{MAILPIT_API_URL}/message/{message_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching message content: {e}")
        sys.exit(1)

def format_as_markdown(message):
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0  # No wrapping
    
    headers = message.get("Headers", {})
    subject = headers.get("Subject", ["(No Subject)"])[0]
    from_addr = headers.get("From", ["(Unknown)"])[0]
    to_addr = headers.get("To", ["(Unknown)"])[0]
    date_str = headers.get("Date", [datetime.now().isoformat()])[0]
    
    # Prefer HTML, fallback to Text
    html_body = message.get("HTML")
    text_body = message.get("Text")
    
    if html_body:
        body_content = h.handle(html_body)
    elif text_body:
        body_content = f"```text\n{text_body}\n```"
    else:
        body_content = "(No content)"

    markdown_output = f"""---
Subject: {subject}
From:    {from_addr}
To:      {to_addr}
Date:    {date_str}
ID:      {message['ID']}
---

# {subject}

{body_content}
"""
    return markdown_output

def save_email(markdown_content, message_id):
    ensure_export_dir()
    
    # Create a nice filename
    # e.g., email_20230101_120000_abc123.md
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"email_{timestamp}_{message_id}.md"
    filepath = EXPORT_DIR / filename
    
    with open(filepath, "w") as f:
        f.write(markdown_content)
    
    return filepath

if __name__ == "__main__":
    print("🔍 Fetching latest email from Mailpit...")
    
    latest_msg_summary = get_latest_message()
    
    if not latest_msg_summary:
        print("📭 Mailpit is empty! No emails to export.")
        print("   Try running: python scripts/verify_email_setup.py")
        sys.exit(0)
    
    msg_id = latest_msg_summary["ID"]
    print(f"📥 Found message: {latest_msg_summary.get('Subject')} (ID: {msg_id})")
    
    full_message = get_message_content(msg_id)
    markdown_content = format_as_markdown(full_message)
    saved_path = save_email(markdown_content, msg_id)
    
    print(f"✅ Saved to: {saved_path}")
    print(f"\nPro tip: View it with 'code {saved_path}'")
