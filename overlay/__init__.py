"""Minimal teatree overlay for the borrower-portal repo.

This is a *lightweight* overlay: it teaches the open-source teatree CLI how
to find this repo, run its tests/lint, and validate PR metadata — so the
project can be developed and reviewed through `t3`. It deliberately does NOT
bundle lifecycle/phase skills, workspace orchestration, or loop slots; those
heavier extension points keep their teatree defaults.
"""
