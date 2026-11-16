"""
modules/email_handler.py — JARVIS Gmail Email Sender
=====================================================
Sends emails via Gmail's SMTP server using STARTTLS. Credentials are
loaded from the .env file (GMAIL_ADDRESS, GMAIL_APP_PASSWORD). The
handler gracefully warns if credentials are missing and returns
JARVIS-style confirmation strings from compose_and_send().
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


class EmailHandler:
    """
    Gmail email sender using SMTP with STARTTLS.

    Uses a Gmail App Password (NOT the account password). App passwords
    are generated at: https://myaccount.google.com/apppasswords
    Two-factor authentication must be enabled on the Gmail account.
    """

    def __init__(self) -> None:
        """
        Initialize the email handler with credentials from config.

        Logs a warning if either credential is missing so the user knows
        email features won't work until the .env file is populated.
        """
        self._address = config.GMAIL_ADDRESS
        self._password = config.GMAIL_APP_PASSWORD

        if not self.is_configured():
            logger.warning(
                "Email is not configured. Add GMAIL_ADDRESS and "
                "GMAIL_APP_PASSWORD to D:\\JARVIS\\.env to enable email features."
            )
        else:
            logger.info(f"Email handler ready. From address: {self._address}")

    def is_configured(self) -> bool:
        """
        Check whether Gmail credentials are configured in the .env file.

        Returns:
            bool: True if both GMAIL_ADDRESS and GMAIL_APP_PASSWORD are non-empty.
        """
        return bool(self._address and self._password)

    def send(self, to: str, subject: str, body: str) -> bool:
        """
        Send a plain-text email via Gmail SMTP.

        Args:
            to (str): Recipient email address.
            subject (str): Email subject line.
            body (str): Plain text email body.

        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """
        if not self.is_configured():
            logger.error("Cannot send email: credentials not configured.")
            return False

        if not to or not to.strip():
            logger.error("Cannot send email: recipient address is empty.")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self._address
            msg["To"] = to.strip()
            msg["Subject"] = subject.strip() if subject else "(No Subject)"
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._address, self._password)
                server.sendmail(self._address, to.strip(), msg.as_string())

            logger.info(f"Email sent successfully to {to}. Subject: '{subject}'")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "SMTP authentication failed. Verify your Gmail App Password in .env."
            )
            return False
        except smtplib.SMTPRecipientsRefused:
            logger.error(f"Recipient refused by SMTP server: {to}")
            return False
        except smtplib.SMTPException as exc:
            logger.error(f"SMTP error sending to {to}: {exc}", exc_info=True)
            return False
        except OSError as exc:
            logger.error(f"Network error sending email: {exc}", exc_info=True)
            return False
        except Exception as exc:
            logger.error(f"Unexpected email send error: {exc}", exc_info=True)
            return False

    def compose_and_send(self, entities: dict) -> str:
        """
        Extract email fields from intent entities and send the email.

        Args:
            entities (dict): Entity dict from IntentClassifier with keys:
                'to', 'subject', 'body', 'to_name'.

        Returns:
            str: JARVIS-style confirmation or error message.
        """
        to = entities.get("to", "").strip()
        subject = entities.get("subject", "").strip() or "Message from JARVIS"
        body = entities.get("body", "").strip()
        to_name = entities.get("to_name", "").strip()

        if not to:
            return "I don't have a recipient address, sir. Please specify who to send the email to."

        if not body:
            return "I don't have any content for the email, sir. Please tell me what to write."

        success = self.send(to=to, subject=subject, body=body)

        if success:
            recipient_display = to_name if to_name else to
            return f"Email sent to {recipient_display}, sir."
        else:
            return (
                "I was unable to send the email, sir. "
                "Please check your Gmail credentials in the .env file."
            )

    def read_inbox(self, count: int = 5) -> str:
        """Alias for read_emails to maintain compatibility with intent dispatchers."""
        return self.read_emails(count)

    def read_emails(self, count: int = 5) -> str:
        """
        Connect to Gmail via IMAP and fetch the subjects of the most recent emails.
        """
        import imaplib
        import email
        from email.header import decode_header

        if not self.is_configured():
            return "I cannot access your inbox, sir. Credentials are missing."

        try:
            # Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self._address, self._password)
            mail.select("inbox")

            # Search for all emails
            status, messages = mail.search(None, "ALL")
            if status != "OK":
                return "I couldn't search the inbox, sir."

            # Get the list of message IDs and take the last 'count'
            message_ids = messages[0].split()
            if not message_ids:
                return "Your inbox is empty, sir."

            latest_ids = message_ids[-count:]
            latest_ids.reverse()

            results = []
            for m_id in latest_ids:
                status, msg_data = mail.fetch(m_id, "(RFC822)")
                if status != "OK":
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        # pylint: disable=unsubscriptable-object
                        msg = email.message_from_bytes(response_part[1])
                        raw_sub = msg.get("Subject") or "No Subject"
                        subject_text = ""
                        for part, enc in decode_header(raw_sub):
                            if isinstance(part, bytes):
                                subject_text += part.decode(enc or "utf-8", errors="replace")
                            else:
                                subject_text += str(part)
                        sender = msg.get("From", "Unknown Sender")
                        results.append(f"From {sender}: {subject_text}")
            
            mail.close()
            mail.logout()

            if not results:
                return "I couldn't retrieve any recent emails, sir."
            
            report = "Sir, here are your most recent emails:\n" + "\n".join(results)
            return report

        except Exception as exc:
            logger.error(f"IMAP error: {exc}", exc_info=True)
            return "I encountered an error while reading your inbox, sir."

