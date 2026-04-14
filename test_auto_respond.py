"""
test_auto_respond.py – Unit tests for sentiment analysis & auto-reply pipeline.

Run:
    python -m pytest test_auto_respond.py -v
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ── Sentiment Analyzer ────────────────────────────────────────────────────────

@pytest.fixture
def _mock_openai_classify():
    """Patch the OpenAI call inside sentiment_analyzer."""
    with patch("skills.utils.sentiment_analyzer._get_client") as mock_client:
        yield mock_client


def _make_openai_response(content: str):
    """Build a fake OpenAI chat completion response."""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestSentimentAnalyzer:
    def test_classify_negative(self, _mock_openai_classify):
        from skills.utils.sentiment_analyzer import classify_email

        _mock_openai_classify.return_value.chat.completions.create.return_value = (
            _make_openai_response(
                json.dumps(
                    {
                        "category": "NEGATIVE",
                        "confidence": 0.95,
                        "reason": "The sender complains about a delayed shipment.",
                    }
                )
            )
        )
        result = classify_email(
            subject="Where is my order??",
            body="I ordered 2 weeks ago and still nothing. This is unacceptable.",
            sender="angry@customer.com",
        )
        assert result["category"] == "NEGATIVE"
        assert result["confidence"] >= 0.9

    def test_classify_positive(self, _mock_openai_classify):
        from skills.utils.sentiment_analyzer import classify_email

        _mock_openai_classify.return_value.chat.completions.create.return_value = (
            _make_openai_response(
                json.dumps(
                    {
                        "category": "POSITIVE",
                        "confidence": 0.88,
                        "reason": "Customer praises excellent service.",
                    }
                )
            )
        )
        result = classify_email(
            subject="Thank you!",
            body="Your team was fantastic – everything arrived perfectly.",
            sender="happy@customer.com",
        )
        assert result["category"] == "POSITIVE"

    def test_classify_compliance(self, _mock_openai_classify):
        from skills.utils.sentiment_analyzer import classify_email

        _mock_openai_classify.return_value.chat.completions.create.return_value = (
            _make_openai_response(
                json.dumps(
                    {
                        "category": "COMPLIANCE",
                        "confidence": 0.91,
                        "reason": "Sender raises GDPR data deletion request.",
                    }
                )
            )
        )
        result = classify_email(
            subject="GDPR data deletion request",
            body="Under GDPR Article 17, I request deletion of all my personal data.",
            sender="user@eu-domain.com",
        )
        assert result["category"] == "COMPLIANCE"

    def test_classify_fallback_on_bad_json(self, _mock_openai_classify):
        from skills.utils.sentiment_analyzer import classify_email

        _mock_openai_classify.return_value.chat.completions.create.return_value = (
            _make_openai_response("This is not valid JSON at all")
        )
        result = classify_email(subject="Hey", body="Just checking in", sender="a@b.com")
        assert result["category"] == "NEUTRAL"
        assert result["confidence"] == 0.0


# ── Email Templates ───────────────────────────────────────────────────────────

class TestEmailTemplates:
    def test_render_negative_template(self):
        from skills.utils.email_templates import render_template

        rendered = render_template(
            "NEGATIVE",
            sender="angry@customer.com",
            subject="Where is my order??",
            reason="Delayed shipment",
        )
        assert rendered is not None
        assert "We're on it" in rendered["subject"]
        assert "apologise" in rendered["body"].lower() or "apologi" in rendered["body"].lower()
        assert "Where is my order??" in rendered["subject"]

    def test_render_positive_template(self):
        from skills.utils.email_templates import render_template

        rendered = render_template(
            "POSITIVE",
            sender="happy@customer.com",
            subject="Great work!",
        )
        assert rendered is not None
        assert "Thank you" in rendered["subject"]
        assert "Great work!" in rendered["subject"]

    def test_render_compliance_template(self):
        from skills.utils.email_templates import render_template

        rendered = render_template(
            "COMPLIANCE",
            sender="legal@corp.com",
            subject="Policy breach report",
        )
        assert rendered is not None
        assert "Compliance" in rendered["subject"]

    def test_neutral_returns_none(self):
        from skills.utils.email_templates import render_template

        rendered = render_template("NEUTRAL", sender="x@y.com", subject="Hi")
        assert rendered is None


# ── Auto Responder (integration-style with mocks) ────────────────────────────

class TestAutoResponder:
    @patch("skills.utils.auto_responder.parse_message")
    @patch("skills.utils.auto_responder.classify_email")
    def test_negative_email_triggers_reply(self, mock_classify, mock_parse):
        from skills.utils.auto_responder import analyse_and_respond

        mock_parse.return_value = {
            "subject": "Broken product",
            "body": "The item arrived damaged. I want a refund.",
            "sender": "upset@buyer.com",
            "date": "2026-04-14",
        }
        mock_classify.return_value = {
            "category": "NEGATIVE",
            "confidence": 0.93,
            "reason": "Product quality complaint.",
        }
        mock_send = MagicMock(return_value={"status": "sent", "message_id": "xyz"})

        result = analyse_and_respond(
            service=MagicMock(),
            message_id="msg123",
            send_fn=mock_send,
        )

        assert result["reply_sent"] is True
        assert result["template_used"] is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert "upset@buyer.com" in str(call_kwargs)

    @patch("skills.utils.auto_responder.parse_message")
    @patch("skills.utils.auto_responder.classify_email")
    def test_neutral_email_no_reply(self, mock_classify, mock_parse):
        from skills.utils.auto_responder import analyse_and_respond

        mock_parse.return_value = {
            "subject": "Meeting notes",
            "body": "Here are the notes from today's standup.",
            "sender": "team@corp.com",
            "date": "2026-04-14",
        }
        mock_classify.return_value = {
            "category": "NEUTRAL",
            "confidence": 0.85,
            "reason": "Informational meeting notes.",
        }
        mock_send = MagicMock()

        result = analyse_and_respond(
            service=MagicMock(),
            message_id="msg456",
            send_fn=mock_send,
        )

        assert result["reply_sent"] is False
        assert result["template_used"] is False
        mock_send.assert_not_called()

    @patch("skills.utils.auto_responder.parse_message")
    @patch("skills.utils.auto_responder.classify_email")
    def test_dry_run_does_not_send(self, mock_classify, mock_parse):
        from skills.utils.auto_responder import analyse_and_respond

        mock_parse.return_value = {
            "subject": "Compliance issue",
            "body": "We found a HIPAA violation in department X.",
            "sender": "auditor@firm.com",
            "date": "2026-04-14",
        }
        mock_classify.return_value = {
            "category": "COMPLIANCE",
            "confidence": 0.97,
            "reason": "HIPAA violation report.",
        }
        mock_send = MagicMock()

        result = analyse_and_respond(
            service=MagicMock(),
            message_id="msg789",
            send_fn=mock_send,
            dry_run=True,
        )

        assert result["template_used"] is True
        assert result["reply_sent"] is False
        assert "Dry-run" in result.get("note", "")
        mock_send.assert_not_called()
