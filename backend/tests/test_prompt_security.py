"""Unit tests for the trust-labeling primitives: every retrieved document
must be wrapped as untrusted data, and the system rules must explicitly
tell the model never to follow instructions found inside that wrapper.
"""

from app.agent.prompt_security import SECURITY_RULES, wrap_untrusted_document


def test_wrap_untrusted_document_adds_untrusted_trust_label():
    wrapped = wrap_untrusted_document("My Doc", "some content")

    assert "<retrieved_document" in wrapped
    assert 'trust="untrusted"' in wrapped
    assert "</retrieved_document>" in wrapped


def test_wrap_untrusted_document_preserves_original_content():
    wrapped = wrap_untrusted_document("My Doc", "some content with instructions inside")

    assert "some content with instructions inside" in wrapped


def test_security_rules_instruct_model_to_never_follow_untrusted_content():
    rules_lower = SECURITY_RULES.lower()

    assert "untrusted" in rules_lower
    assert "instruction" in rules_lower
    assert "never" in rules_lower
