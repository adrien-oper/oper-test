"""The deploy-readiness system check for the default secret key."""

from django.test import override_settings

from config.checks import INSECURE_SECRET_KEY, check_secret_key


class TestSecretKeyCheck:
    def test_default_key_with_debug_off_is_an_error(self):
        with override_settings(SECRET_KEY=INSECURE_SECRET_KEY, DEBUG=False):
            errors = check_secret_key()
        assert [error.id for error in errors] == ["config.E001"]

    def test_default_key_with_debug_on_is_allowed(self):
        with override_settings(SECRET_KEY=INSECURE_SECRET_KEY, DEBUG=True):
            assert check_secret_key() == []

    def test_real_key_with_debug_off_is_allowed(self):
        with override_settings(SECRET_KEY="a-real-production-secret", DEBUG=False):
            assert check_secret_key() == []
