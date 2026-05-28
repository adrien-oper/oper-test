"""The document analyzer — stub path, mocked live path, mismatch detection."""

import json
from types import SimpleNamespace

import pytest
from django.test import override_settings

from portal.ai.analyzer import AnalysisResult, ApplicationFacts, analyze_document, detect_mismatches


@pytest.fixture
def facts():
    return ApplicationFacts(full_name="Ada Lovelace", national_number="92052812928")


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


class TestStubPath:
    def test_stub_used_when_no_key(self, facts):
        with override_settings(ANTHROPIC_API_KEY="", AI_ANALYSIS_ENABLED=False):
            result = analyze_document("irrelevant", "payslip_january.pdf", facts)
        assert result.is_stub is True
        assert result.detected_kind == "payslip"
        assert "STUB" in result.summary

    def test_stub_classifies_from_filename(self, facts):
        with override_settings(AI_ANALYSIS_ENABLED=False):
            assert analyze_document("x", "my_id_card.png", facts).detected_kind == "id_card"
            assert analyze_document("x", "random.bin", facts).detected_kind == "other"

    def test_stub_echoes_application_data_so_no_false_mismatch(self, facts):
        with override_settings(AI_ANALYSIS_ENABLED=False):
            result = analyze_document("x", "payslip.pdf", facts)
        assert result.mismatches == []


class TestLivePath:
    def _fake_client(self, payload):
        message = SimpleNamespace(content=[SimpleNamespace(text=json.dumps(payload))])
        messages = SimpleNamespace(create=lambda **_: message)
        return SimpleNamespace(messages=messages)

    def test_live_path_parses_response_and_flags_mismatch(self, facts, mocker):
        payload = {
            "detected_kind": "payslip",
            "summary": "A payslip.",
            "extracted_fields": {"national_number": "11111111111"},
            "confidence": 0.9,
        }
        fake = self._fake_client(payload)
        mock_anthropic = mocker.MagicMock()
        mock_anthropic.Anthropic.return_value = fake
        mocker.patch.dict("sys.modules", {"anthropic": mock_anthropic})

        with override_settings(
            ANTHROPIC_API_KEY="sk-test", AI_ANALYSIS_ENABLED=True, ANTHROPIC_MODEL="claude-haiku-4-5"
        ):
            result = analyze_document("payslip text", "payslip.pdf", facts)

        assert result.is_stub is False
        assert result.model_used == "claude-haiku-4-5"
        assert result.detected_kind == "payslip"
        assert result.mismatches  # national number disagrees

    def test_live_path_marks_prompt_cache_breakpoint(self, facts, mocker):
        captured = {}

        def _create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({"detected_kind": "other"}))])

        fake = SimpleNamespace(messages=SimpleNamespace(create=_create))
        mock_anthropic = mocker.MagicMock()
        mock_anthropic.Anthropic.return_value = fake
        mocker.patch.dict("sys.modules", {"anthropic": mock_anthropic})

        with override_settings(ANTHROPIC_API_KEY="sk-test", AI_ANALYSIS_ENABLED=True):
            analyze_document("text", "doc.pdf", facts)

        system_blocks = captured["system"]
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_live_path_tolerates_unparseable_response(self, facts, mocker):
        fake = SimpleNamespace(
            messages=SimpleNamespace(
                create=lambda **_: SimpleNamespace(content=[SimpleNamespace(text="not json")]),
            ),
        )
        mock_anthropic = mocker.MagicMock()
        mock_anthropic.Anthropic.return_value = fake
        mocker.patch.dict("sys.modules", {"anthropic": mock_anthropic})

        with override_settings(ANTHROPIC_API_KEY="sk-test", AI_ANALYSIS_ENABLED=True):
            result = analyze_document("text", "doc.pdf", facts)
        assert result.detected_kind == "other"


class TestResultDataclass:
    def test_defaults(self):
        result = AnalysisResult(detected_kind="other", summary="s", extracted_fields={})
        assert result.is_stub is True
        assert result.mismatches == []
