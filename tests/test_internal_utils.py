from __future__ import annotations

from functools import partial

from packaging.version import Version

from tests import utils


def test_is_pyvsupported(monkeypatch):
    monkeypatch.setattr(utils, "SUPPORTED_PYTHON_VERSIONS", [Version("1.0.0"), Version("2.1")])
    assert utils.is_pyvsupported("1.0")
    assert not utils.is_pyvsupported("1.1")
    assert not utils.is_pyvsupported("2")
    assert not utils.is_pyvsupported("2.0")
    assert utils.is_pyvsupported("2.1")
    assert utils.is_pyvsupported("2.1.0")
    assert not utils.is_pyvsupported("2.1.1")


def test_is_djvsupported(monkeypatch):
    monkeypatch.setattr(utils, "SUPPORTED_DJANGO_VERSIONS", [Version("1.0.0"), Version("2.1")])
    assert utils.is_djvsupported("1.0")
    assert not utils.is_djvsupported("1.1")
    assert not utils.is_djvsupported("2")
    assert not utils.is_djvsupported("2.0")
    assert utils.is_djvsupported("2.1")
    assert utils.is_djvsupported("2.1.0")
    assert not utils.is_djvsupported("2.1.1")


def test_is_supported_version():
    versions = [Version("1.0"), Version("2.1"), Version("2.3")]
    is_supported_version = partial(utils.is_supported_version, versions)
    assert is_supported_version(Version("1.0"))
    assert is_supported_version(Version("1.0.10"))
    assert not is_supported_version(Version("2.0"))
    assert is_supported_version(Version("2.1.10"))
    assert not is_supported_version(Version("2.2"))
    assert is_supported_version(Version("2.2a1"))
    assert is_supported_version(Version("2.3"))
