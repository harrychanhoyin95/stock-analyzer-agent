import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from langchain_core.tools import tool


@tool
def send_email(to: str, subject: str, body: str, chart_path: str = "") -> dict:
    """Send an HTML email with an optional chart attachment via Gmail SMTP.

    Use this tool to email analysis results to the user. Compose the subject
    and body yourself based on the analysis you have already done — do not
    ask the user what to write.

    Subject format: "[YYYY-MM-DD] [Stock/Topic] Summary"
    Example subject: "2026-02-28 AAPL 1-Month Summary"

    Body: Write the full analysis as an HTML string. Use these elements:
    - <h2> for section headers (e.g. Top Gainers, Stock Analysis, News)
    - <table> for tabular data with <th> headers and <td> cells
    - style="color:green" / style="color:red" for positive/negative changes
    - <b> for key metric labels
    - <p> for analysis paragraphs
    - Use inline CSS only — no <style> blocks

    Chart: If you called generate_chart, pass its chart_path here.
    The chart will be attached as a PNG image to the email.

    Args:
        to: Recipient email address. Ask the user for this if not provided.
        subject: Agent-generated subject line following the format above.
        body: Agent-generated HTML analysis. Do not ask the user for this.
        chart_path: Optional path to a chart PNG from generate_chart.

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

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    msg.attach(MIMEText(body, "html"))

    if chart_path and os.path.exists(chart_path):
        with open(chart_path, "rb") as f:
            img_data = f.read()
        attachment = MIMEImage(img_data, name="chart.png")
        msg.attach(attachment)
        os.unlink(chart_path)

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, to, msg.as_string())
    except smtplib.SMTPException as e:
        return {"error": str(e)}

    return {"result": f"Email sent to {to}"}
