"""The document analyzer — stub, mocked SDK, mocked CLI, mismatch detection.

Mocking the SDK and CLI network/process boundaries is the sanctioned
exception to the no-mock rule: the owner has no Anthropic key to test live,
so the live round-trip is covered by one auto-skipping smoke test instead.
"""

import json
import os
from decimal import Decimal
from subprocess import CalledProcessError  # noqa: S404 — only the exception type, used to drive a mocked boundary
from types import SimpleNamespace

import pytest
from django.test import override_settings

from portal.ai.analyzer import (
    AnalysisResult,
    AnalyzerBackendError,
    ApplicationFacts,
    InvalidAnalysisError,
    analyze_document,
    detect_mismatches,
    resolve_backend,
)
from portal.enums import DocumentKind


@pytest.fixture
def facts():
    return ApplicationFacts(
        full_name="Ada Lovelace", national_number="92052812928", property_price=Decimal("300000.00")
    )


class TestMismatchDetection:
    def test_no_mismatch_when_fields_agree(self, facts):
        extracted = {"full_name": "Ada Lovelace", "national_number": "92052812928"}
        assert detect_mismatches(extracted, facts) == []

    def test_mismatch_on_national_number(self, facts):
        extracted = {"national_number": "00000000000"}
        mismatches = detect_mismatches(extracted, facts)
        assert len(mismatches) == 1
        assert "national_number" in mismatches[0]

    def test_case_insensitive_name_match(self, facts):
        extracted = {"full_name": "ADA LOVELACE"}
        assert detect_mismatches(extracted, facts) == []

    def test_missing_field_is_not_a_mismatch(self, facts):
        assert detect_mismatches({}, facts) == []

    def test_mismatch_on_property_price(self, facts):
        mismatches = detect_mismatches({"property_price": "250000"}, facts)
        assert len(mismatches) == 1
        assert "property_price" in mismatches[0]

    def test_property_price_matches_despite_formatting(self, facts):
        assert detect_mismatches({"property_price": "300000.00"}, facts) == []
        assert detect_mismatches({"property_price": "€ 300,000"}, facts) == []

    @pytest.mark.parametrize("value", ["n/a", "1.2.3", "."])
    def test_unparseable_property_price_is_ignored(self, facts, value):
        assert detect_mismatches({"property_price": value}, facts) == []

    def test_property_price_skipped_when_application_has_none(self):
        facts = ApplicationFacts(full_name="Ada", national_number="1", property_price=None)
        assert detect_mismatches({"property_price": "999"}, facts) == []


class TestBackendResolution:
    def test_no_key_resolves_to_stub(self):
        with override_settings(ANTHROPIC_API_KEY="", DOCUMENT_ANALYZER_BACKEND=""):
            assert resolve_backend() == "stub"

    def test_key_present_resolves_to_sdk(self):
        with override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND=""):
            assert resolve_backend() == "sdk"

    def test_explicit_backend_wins_over_key(self):
        with override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="stub"):
            assert resolve_backend() == "stub"

    def test_cli_is_never_the_default_even_with_key(self):
        with override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND=""):
            assert resolve_backend() != "cli"

    def test_unknown_backend_is_rejected(self):
        with override_settings(DOCUMENT_ANALYZER_BACKEND="telepathy"), pytest.raises(AnalyzerBackendError):
            resolve_backend()


class TestStubBackend:
    def test_stub_used_when_no_key(self, facts):
        with override_settings(ANTHROPIC_API_KEY="", DOCUMENT_ANALYZER_BACKEND=""):
            result = analyze_document("irrelevant", "payslip_january.pdf", facts)
        assert result.is_stub is True
        assert result.detected_kind == "payslip"
        assert "STUB" in result.summary

    def test_stub_classifies_from_filename(self, facts):
        with override_settings(DOCUMENT_ANALYZER_BACKEND="stub"):
            assert analyze_document("x", "my_id_card.png", facts).detected_kind == "id_card"
            assert analyze_document("x", "random.bin", facts).detected_kind == "other"

    def test_stub_echoes_application_data_so_no_false_mismatch(self, facts):
        with override_settings(DOCUMENT_ANALYZER_BACKEND="stub"):
            result = analyze_document("x", "payslip.pdf", facts)
        assert result.mismatches == []


class _FakeAuthError(Exception):
    pass


class _FakePermissionError(Exception):
    pass


class _FakeNotFoundError(Exception):
    pass


def _fake_sdk(create, mocker):
    fake = SimpleNamespace(messages=SimpleNamespace(create=create))
    module = mocker.MagicMock()
    module.Anthropic.return_value = fake
    # The analyzer catches these by class, so they must be real exception types.
    module.AuthenticationError = _FakeAuthError
    module.PermissionDeniedError = _FakePermissionError
    module.NotFoundError = _FakeNotFoundError
    mocker.patch.dict("sys.modules", {"anthropic": module})
    return module


def _sdk_returning(text, mocker):
    return _fake_sdk(lambda **_: SimpleNamespace(content=[SimpleNamespace(text=text)]), mocker)


class TestSdkBackend:
    def test_request_construction(self, facts, mocker):
        captured = {}

        def _create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({"detected_kind": "other"}))])

        _fake_sdk(_create, mocker)
        with override_settings(
            ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk", ANTHROPIC_MODEL="claude-haiku-4-5"
        ):
            analyze_document("payslip text", "payslip.pdf", facts)

        assert captured["model"] == "claude-haiku-4-5"
        assert captured["max_tokens"] == 1024
        assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert "payslip text" in captured["messages"][0]["content"]
        assert "payslip.pdf" in captured["messages"][0]["content"]

    def test_parses_response_and_flags_mismatch(self, facts, mocker):
        payload = {
            "detected_kind": "payslip",
            "summary": "A payslip.",
            "extracted_fields": {"national_number": "11111111111"},
            "confidence": 0.9,
        }
        _sdk_returning(json.dumps(payload), mocker)
        with override_settings(
            ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk", ANTHROPIC_MODEL="claude-haiku-4-5"
        ):
            result = analyze_document("payslip text", "payslip.pdf", facts)

        assert result.is_stub is False
        assert result.model_used == "claude-haiku-4-5"
        assert result.detected_kind == "payslip"
        assert result.mismatches  # national number disagrees

    def test_rejects_unparseable_response(self, facts, mocker):
        _sdk_returning("not json", mocker)
        with (
            override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk"),
            pytest.raises(InvalidAnalysisError),
        ):
            analyze_document("text", "doc.pdf", facts)

    def test_rejects_unknown_detected_kind(self, facts, mocker):
        _sdk_returning(json.dumps({"detected_kind": "not_a_kind", "summary": "x"}), mocker)
        with (
            override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk"),
            pytest.raises(InvalidAnalysisError),
        ):
            analyze_document("text", "doc.pdf", facts)

    def test_rejects_non_object_json(self, facts, mocker):
        _sdk_returning(json.dumps(["a", "list"]), mocker)
        with (
            override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk"),
            pytest.raises(InvalidAnalysisError),
        ):
            analyze_document("text", "doc.pdf", facts)

    def test_rejects_missing_detected_kind(self, facts, mocker):
        _sdk_returning(json.dumps({"summary": "no kind here"}), mocker)
        with (
            override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk"),
            pytest.raises(InvalidAnalysisError),
        ):
            analyze_document("text", "doc.pdf", facts)

    def test_tolerates_non_dict_extracted_fields(self, facts, mocker):
        _sdk_returning(json.dumps({"detected_kind": "payslip", "extracted_fields": "oops"}), mocker)
        with override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk"):
            result = analyze_document("text", "doc.pdf", facts)
        assert result.extracted_fields == {}
        assert result.mismatches == []

    def test_propagates_api_and_rate_limit_errors(self, facts, mocker):
        def _raise(**_):
            msg = "rate limited"
            raise RuntimeError(msg)

        _fake_sdk(_raise, mocker)
        with (
            override_settings(ANTHROPIC_API_KEY="sk-test", DOCUMENT_ANALYZER_BACKEND="sdk"),
            pytest.raises(RuntimeError, match="rate limited"),
        ):
            analyze_document("text", "doc.pdf", facts)

    @pytest.mark.parametrize("error_attr", ["AuthenticationError", "PermissionDeniedError", "NotFoundError"])
    def test_unrecoverable_api_errors_become_backend_error(self, facts, mocker, error_attr):
        # A rejected/forbidden key or an unknown model is permanent: a retry
        # fails identically. The analyzer must surface it as a terminal backend
        # error so the task fails the document instead of wedging it.
        module = _fake_sdk(lambda **_: None, mocker)
        exc_type = getattr(module, error_attr)

        def _raise(**_):
            msg = "boom"
            raise exc_type(msg)

        module.Anthropic.return_value.messages.create = _raise
        with (
            override_settings(ANTHROPIC_API_KEY="sk-bad", DOCUMENT_ANALYZER_BACKEND="sdk"),
            pytest.raises(AnalyzerBackendError, match="unrecoverable"),
        ):
            analyze_document("text", "doc.pdf", facts)


def _cli_payload(result_text):
    return json.dumps({"type": "result", "result": result_text})


class TestCliBackend:
    def test_argv_construction_and_parsing(self, facts, mocker):
        captured = {}

        def _run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            payload = json.dumps({"detected_kind": "payslip", "summary": "A payslip.", "extracted_fields": {}})
            return SimpleNamespace(stdout=_cli_payload(payload), returncode=0)

        mocker.patch("portal.ai.analyzer.shutil.which", return_value="/usr/local/bin/claude")
        mocker.patch("portal.ai.analyzer.subprocess.run", side_effect=_run)

        with override_settings(DOCUMENT_ANALYZER_BACKEND="cli", CLAUDE_CLI_PATH="claude"):
            result = analyze_document("payslip text", "payslip.pdf", facts)

        argv = captured["argv"]
        assert argv == ["/usr/local/bin/claude", "-p", "--output-format", "json"]
        # The document text (possibly PII) goes on stdin, never argv.
        assert "payslip text" not in " ".join(argv)
        assert "payslip text" in captured["kwargs"]["input"]
        assert "payslip.pdf" in captured["kwargs"]["input"]
        assert captured["kwargs"]["check"] is True
        assert result.is_stub is False
        assert result.model_used == "claude-cli"
        assert result.detected_kind == "payslip"

    def test_missing_binary_fails_loudly(self, facts, mocker):
        mocker.patch("portal.ai.analyzer.shutil.which", return_value=None)
        with (
            override_settings(DOCUMENT_ANALYZER_BACKEND="cli"),
            pytest.raises(AnalyzerBackendError, match="on PATH"),
        ):
            analyze_document("text", "doc.pdf", facts)

    def test_non_zero_exit_fails_loudly(self, facts, mocker):
        mocker.patch("portal.ai.analyzer.shutil.which", return_value="/usr/local/bin/claude")
        mocker.patch(
            "portal.ai.analyzer.subprocess.run",
            side_effect=CalledProcessError(returncode=2, cmd=["claude"]),
        )
        with (
            override_settings(DOCUMENT_ANALYZER_BACKEND="cli"),
            pytest.raises(AnalyzerBackendError, match="status 2"),
        ):
            analyze_document("text", "doc.pdf", facts)

    def test_malformed_envelope_json_is_rejected(self, facts, mocker):
        mocker.patch("portal.ai.analyzer.shutil.which", return_value="/usr/local/bin/claude")
        mocker.patch(
            "portal.ai.analyzer.subprocess.run",
            return_value=SimpleNamespace(stdout="not json at all", returncode=0),
        )
        with (
            override_settings(DOCUMENT_ANALYZER_BACKEND="cli"),
            pytest.raises(InvalidAnalysisError),
        ):
            analyze_document("text", "doc.pdf", facts)

    def test_plain_json_result_without_envelope_is_parsed(self, facts, mocker):
        payload = json.dumps({"detected_kind": "id_card", "summary": "An id card.", "extracted_fields": {}})
        mocker.patch("portal.ai.analyzer.shutil.which", return_value="/usr/local/bin/claude")
        mocker.patch(
            "portal.ai.analyzer.subprocess.run",
            return_value=SimpleNamespace(stdout=payload, returncode=0),
        )
        with override_settings(DOCUMENT_ANALYZER_BACKEND="cli"):
            result = analyze_document("text", "id.png", facts)
        assert result.detected_kind == "id_card"


class TestResultDataclass:
    def test_defaults(self):
        result = AnalysisResult(detected_kind="other", summary="s", extracted_fields={})
        assert result.is_stub is True
        assert result.mismatches == []


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="live API key not configured")
class TestLiveSmoke:
    def test_live_round_trip_returns_a_valid_kind(self, facts):
        with override_settings(DOCUMENT_ANALYZER_BACKEND="sdk"):
            result = analyze_document(
                "Payslip for Ada Lovelace, national number 92052812928, gross monthly 6000 EUR.",
                "payslip.txt",
                facts,
            )
        assert result.is_stub is False
        assert result.detected_kind in DocumentKind.values
