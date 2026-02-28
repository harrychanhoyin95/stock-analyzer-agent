import os
import smtplib
from email.mime.text import MIMEText

from langchain_core.tools import tool

@tool
def send_email(to: str, subject: str, body: str) -> dict:
    """Send a plain text email via Gmail SMTP.

    Use this tool to email analysis results to the user. Compose the subject
    and body yourself based on the analysis you have already done — do not
    ask the user what to write.

    Subject format: "[YYYY-MM-DD] [Stock/Topic] Summary"
    Example subject: "2026-02-28 AAPL 1-Month Summary"

    Body: Write the full plain text analysis as the email body. Use the
    results from tools you have already called in this conversation.

    Args:
        to: Recipient email address. Ask the user for this if not provided.
        subject: Agent-generated subject line following the format above.
        body: Agent-generated plain text analysis. Do not ask the user for this.

    Returns:
        Dict with 'result' on success or 'error' on failure.
    """
    
    sender = os.getenv("GMAIL_SENDER")
    password = os.getenv("GMAIL_APP_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = os.getenv("SMTP_PORT", 465)

    if not sender or not password:
        missing = []
        if not sender:
            missing.append("GMAIL_SENDER")
        if not password:
            missing.append("GMAIL_APP_PASSWORD")
        return {"error": f"Missing environment variables: {', '.join(missing)}"}

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, to, msg.as_string())
    except smtplib.SMTPException as e:
        return {"error": str(e)}

    return {"result": f"Email sent to {to}"}
