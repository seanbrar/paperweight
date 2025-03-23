"""Module for sending email notifications about processed papers.

This module handles the creation and sending of email notifications about relevant papers
that have been processed. It includes functionality for composing email content and
sending emails through SMTP servers.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email_notification(subject, body, config):
    """Send an email notification using the configured SMTP server.

    Args:
        subject: The subject line of the email.
        body: The body text of the email.
        config: Configuration dictionary containing email settings.

    Raises:
        smtplib.SMTPException: If there is an error sending the email.
    """
    from_email = config["email"]["from"]
    from_password = config["email"]["password"]
    to_email = config["email"]["to"]
    smtp_server = config["email"]["smtp_server"]
    smtp_port = config["email"]["smtp_port"]

    # Create the email
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    # Send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        logger.info("Email notification sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}", exc_info=True)
        raise


def compile_and_send_notifications(papers, config):
    """Compile paper information and send email notifications.

    Args:
        papers: List of dictionaries containing paper data.
        config: Configuration dictionary containing email and notification settings.

    Returns:
        bool: True if notifications were sent successfully, False otherwise.
    """
    if not papers:
        logger.info("No papers to send notifications for.")
        return

    sort_order = config.get("email", {}).get("sort_order", "relevance")

    if sort_order == "alphabetical":
        papers = sorted(papers, key=lambda x: x["title"].lower())
    elif sort_order == "publication_time":
        papers = sorted(papers, key=lambda x: x["date"], reverse=True)
    # For 'relevance' or any other value, we keep the existing order (already sorted by relevance)

    subject = "New Papers from ArXiv"
    body = "Here are the latest papers:\n\n"
    for paper in papers:
        body += f"Title: {paper['title']}\n"
        body += f"Date: {paper['date']}\n"
        body += f"Summary: {paper['summary']}\n"
        body += f"Link: {paper['link']}\n"
        body += f"Relevance Score: {paper['relevance_score']:.2f}\n\n"

    success = send_email_notification(subject, body, config)
    return success
