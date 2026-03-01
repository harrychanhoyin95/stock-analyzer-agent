import os
import smtplib

import pytest

from tools.send_email import send_email


class TestSendEmailUnit:
    def test_missing_both_env_vars_returns_error(self, monkeypatch):
        monkeypatch.delenv("GMAIL_SENDER", raising=False)
        monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

        result = send_email.invoke({"to": "test@example.com", "subject": "S", "body": "<p>hi</p>"})

        assert "error" in result
        assert "GMAIL_SENDER" in result["error"]
        assert "GMAIL_APP_PASSWORD" in result["error"]

    def test_happy_path_no_chart_sends_email(self, monkeypatch, mocker):
        monkeypatch.setenv("GMAIL_SENDER", "sender@gmail.com")
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

        mock_smtp = mocker.patch("tools.send_email.smtplib.SMTP_SSL")

        result = send_email.invoke({"to": "recv@example.com", "subject": "S", "body": "<p>hi</p>"})

        mock_smtp.return_value.__enter__.return_value.sendmail.assert_called_once()
        assert result == {"result": "Email sent to recv@example.com"}

    def test_chart_path_exists_attaches_and_deletes_file(self, monkeypatch, mocker, tmp_path):
        monkeypatch.setenv("GMAIL_SENDER", "sender@gmail.com")
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

        chart = tmp_path / "chart.png"
        chart.write_bytes(b"\x89PNG\r\n\x1a\n")

        mocker.patch("tools.send_email.smtplib.SMTP_SSL")

        send_email.invoke({
            "to": "recv@example.com",
            "subject": "S",
            "body": "<p>hi</p>",
            "chart_path": str(chart),
        })

        assert not chart.exists()

    def test_chart_path_missing_sends_without_attachment(self, monkeypatch, mocker):
        monkeypatch.setenv("GMAIL_SENDER", "sender@gmail.com")
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

        mocker.patch("tools.send_email.smtplib.SMTP_SSL")

        result = send_email.invoke({
            "to": "recv@example.com",
            "subject": "S",
            "body": "<p>hi</p>",
            "chart_path": "/nonexistent/chart.png",
        })

        assert result == {"result": "Email sent to recv@example.com"}

    def test_smtp_exception_returns_error(self, monkeypatch, mocker):
        monkeypatch.setenv("GMAIL_SENDER", "sender@gmail.com")
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

        mock_smtp = mocker.patch("tools.send_email.smtplib.SMTP_SSL")
        mock_smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad credentials")

        result = send_email.invoke({"to": "recv@example.com", "subject": "S", "body": "<p>hi</p>"})

        assert "error" in result
