import pytest
from digisac import deve_bloquear, deve_desbloquear

def test_deve_bloquear():
    assert deve_bloquear("GREEN", "RED") is True
    assert deve_bloquear("YELLOW", "RED") is True
    assert deve_bloquear("RED", "RED") is False
    assert deve_bloquear(None, "RED") is False
    assert deve_bloquear("GREEN", "YELLOW") is False

def test_deve_desbloquear():
    assert deve_desbloquear("RED", "GREEN") is True
    assert deve_desbloquear("RED", "YELLOW") is True
    assert deve_desbloquear("YELLOW", "GREEN") is False
    assert deve_desbloquear(None, "GREEN") is False
    assert deve_desbloquear("RED", "RED") is False
