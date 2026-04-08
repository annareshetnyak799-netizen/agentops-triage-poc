from src.safety.redaction import redact_list, redact_text


def test_redact_text_masks_email() -> None:
    value = "Contact oncall@example.com for details."
    redacted = redact_text(value)
    assert "oncall@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_redact_text_masks_token() -> None:
    value = "Leaked token sk_1234567890abcdef should not appear."
    redacted = redact_text(value)
    assert "sk_1234567890abcdef" not in redacted
    assert "[REDACTED_TOKEN]" in redacted


def test_redact_text_masks_phone() -> None:
    value = "Escalate to +1 (555) 123-4567 immediately."
    redacted = redact_text(value)
    assert "+1 (555) 123-4567" not in redacted
    assert "[REDACTED_PHONE]" in redacted


def test_redact_list_masks_multiple_values() -> None:
    values = [
        "Email: user@example.com",
        "Token: ghp_1234567890abcdef",
    ]
    redacted = redact_list(values)

    assert len(redacted) == 2
    assert "user@example.com" not in redacted[0]
    assert "ghp_1234567890abcdef" not in redacted[1]
