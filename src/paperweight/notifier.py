"""Notification and digest rendering helpers.

paperweight's default delivery is a deterministic stdout digest. Atom feed and
email delivery are optional adapters.
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


def _sort_papers(papers: List[Dict[str, Any]], sort_order: str) -> List[Dict[str, Any]]:
    if sort_order == "alphabetical":
        return sorted(papers, key=lambda x: x.get("title", "").lower())
    if sort_order == "publication_time":
        return sorted(papers, key=lambda x: x.get("date"), reverse=True)
    return list(papers)


def _format_paper_date(paper: Dict[str, Any]) -> str:
    value = paper.get("date")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def render_text_digest(
    papers: List[Dict[str, Any]],
    *,
    sort_order: str = "relevance",
    heading: str = "paperweight digest",
) -> str:
    """Render a deterministic plain-text digest."""
    if not papers:
        return "paperweight digest\n\nNo matching papers."

    ordered = _sort_papers(papers, sort_order)
    lines = [heading, ""]

    for idx, paper in enumerate(ordered, start=1):
        score = paper.get("relevance_score", paper.get("triage_score", 0.0))
        lines.append(f"{idx}. {paper.get('title', 'Untitled')}")
        lines.append(f"   Date: {_format_paper_date(paper)}")
        lines.append(f"   Score: {score:.2f}")
        if paper.get("triage_rationale"):
            lines.append(f"   Why: {paper.get('triage_rationale')}")
        lines.append(f"   Link: {paper.get('link', '')}")
        lines.append(f"   Summary: {(paper.get('summary') or '').strip()}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_atom_feed(
    papers: List[Dict[str, Any]],
    *,
    sort_order: str = "relevance",
    feed_title: str = "paperweight",
    feed_id: str = "https://github.com/seanbrar/paperweight",
    feed_link: str = "https://github.com/seanbrar/paperweight",
) -> str:
    """Render an Atom feed from processed papers."""
    ns = "http://www.w3.org/2005/Atom"
    ET.register_namespace("", ns)
    feed = ET.Element(f"{{{ns}}}feed")

    ET.SubElement(feed, f"{{{ns}}}title").text = feed_title
    ET.SubElement(feed, f"{{{ns}}}id").text = feed_id
    ET.SubElement(feed, f"{{{ns}}}link", {"href": feed_link, "rel": "self"})
    ET.SubElement(feed, f"{{{ns}}}updated").text = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    ordered = _sort_papers(papers, sort_order)
    for paper in ordered:
        entry = ET.SubElement(feed, f"{{{ns}}}entry")
        link = paper.get("link", "")
        title = paper.get("title", "Untitled")
        summary = (paper.get("summary") or "").strip()
        score = paper.get("relevance_score", 0.0)
        rationale = (paper.get("triage_rationale") or "").strip()
        date_text = _format_paper_date(paper)
        updated = f"{date_text}T00:00:00Z" if len(date_text) == 10 else date_text

        ET.SubElement(entry, f"{{{ns}}}id").text = link or title
        ET.SubElement(entry, f"{{{ns}}}title").text = title
        ET.SubElement(entry, f"{{{ns}}}updated").text = updated
        if link:
            ET.SubElement(entry, f"{{{ns}}}link", {"href": link, "rel": "alternate"})
        ET.SubElement(entry, f"{{{ns}}}summary").text = summary
        ET.SubElement(entry, f"{{{ns}}}content", {"type": "text"}).text = (
            f"Score: {score:.2f}\nWhy: {rationale}\nLink: {link}\nSummary: {summary}"
        )

    xml_bytes = ET.tostring(feed, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")


def write_output(content: str, output_path: str | None = None) -> None:
    """Write digest/feed content to file or stdout."""
    if output_path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("Wrote output to %s", target)
    else:
        print(content, end="")


def send_email_notification(subject, body, config):
    """Send an email notification using the configured SMTP server.

    Args:
        subject: The subject line of the email.
        body: The body text of the email.
        config: Configuration dictionary containing email settings.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    from_email = config["email"]["from"]
    from_password = config["email"].get("password")
    to_email = config["email"]["to"]
    smtp_server = config["email"]["smtp_server"]
    smtp_port = config["email"]["smtp_port"]
    use_tls = config["email"].get("use_tls", True)
    use_auth = config["email"].get("use_auth", True)

    # Create the email
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    # Send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        if use_tls:
            server.starttls()
        if use_auth and from_password:
            server.login(from_email, from_password)
        elif use_auth and not from_password:
            logger.warning("SMTP auth enabled but no password provided; skipping login.")
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        logger.info("Email notification sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}", exc_info=True)
        return False


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
        return False

    sort_order = config.get("email", {}).get("sort_order", "relevance")
    papers = _sort_papers(papers, sort_order)
    subject = "New Papers from ArXiv"
    body = render_text_digest(papers, sort_order=sort_order, heading="New Papers from ArXiv")
    success = send_email_notification(subject, body, config)
    return success
