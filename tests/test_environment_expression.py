from __future__ import annotations

from config_tree import env


def test_env_expression_reads_environment(monkeypatch):
    monkeypatch.setenv('BFORGE_TEST_ENV', 'alpha')

    expression = env('BFORGE_TEST_ENV')

    assert expression.evaluate() == 'alpha'


def test_env_expression_falls_back_to_default(monkeypatch):
    monkeypatch.delenv('BFORGE_TEST_ENV_MISSING', raising=False)

    expression = env('BFORGE_TEST_ENV_MISSING', default='fallback')

    assert expression.evaluate() == 'fallback'


def test_env_expression_supports_string_comparison(monkeypatch):
    monkeypatch.setenv('BFORGE_MODE', 'gvsoc')

    expression = env('BFORGE_MODE') == 'gvsoc'

    assert expression.evaluate() is True


def test_env_expression_supports_string_concat(monkeypatch):
    monkeypatch.setenv('BFORGE_HOME', '/tmp/home')

    expression = env('BFORGE_HOME') + '/include'

    assert expression.evaluate() == '/tmp/home/include'
