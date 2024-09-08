import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

def send_email_notification(subject, body, config):
    from_email = config['email']['from']
    from_password = config['email']['password']
    to_email = config['email']['to']
    smtp_server = config['email']['smtp_server']
    smtp_port = config['email']['smtp_port']

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # Send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def compile_and_send_notifications(papers, config):
    subject = "New Papers from ArXiv"
    body = "Here are the latest papers:\n\n"
    for paper in papers:
        body += f"Title: {paper['title']}\n"
        body += f"Date: {paper['date']}\n"
        body += f"Summary: {paper['summary']}\n"
        body += f"Link: {paper['link']}\n\n"

    send_email_notification(subject, body, config)
