import pytest

from dml_bot.api.auth import InvalidInitData, validate_init_data
from tests.webapp_signing import sign_init_data

BOT_TOKEN = "123456:fake-token-for-tests"
USER = {"id": 555, "first_name": "Alice", "username": "alice"}


def test_valid_init_data_is_accepted():
    init_data = sign_init_data(BOT_TOKEN, USER)
    user = validate_init_data(init_data, BOT_TOKEN)
    assert user.id == 555
    assert user.first_name == "Alice"
    assert user.username == "alice"


def test_tampered_field_is_rejected():
    init_data = sign_init_data(BOT_TOKEN, USER)
    tampered = init_data.replace("Alice", "Mallory")
    with pytest.raises(InvalidInitData, match="signature mismatch"):
        validate_init_data(tampered, BOT_TOKEN)


def test_wrong_bot_token_is_rejected():
    init_data = sign_init_data(BOT_TOKEN, USER)
    with pytest.raises(InvalidInitData, match="signature mismatch"):
        validate_init_data(init_data, "999999:different-token")


def test_expired_init_data_is_rejected():
    old_auth_date = 1_000_000_000  # long in the past
    init_data = sign_init_data(BOT_TOKEN, USER, auth_date=old_auth_date)
    with pytest.raises(InvalidInitData, match="expired"):
        validate_init_data(init_data, BOT_TOKEN, now=old_auth_date + 25 * 60 * 60)


def test_init_data_within_max_age_is_accepted():
    old_auth_date = 1_000_000_000
    init_data = sign_init_data(BOT_TOKEN, USER, auth_date=old_auth_date)
    user = validate_init_data(init_data, BOT_TOKEN, now=old_auth_date + 23 * 60 * 60)
    assert user.id == 555


def test_missing_hash_is_rejected():
    with pytest.raises(InvalidInitData, match="missing hash"):
        validate_init_data("user=%7B%22id%22%3A555%7D&auth_date=123", BOT_TOKEN)


def test_empty_init_data_is_rejected():
    with pytest.raises(InvalidInitData, match="empty"):
        validate_init_data("", BOT_TOKEN)


def test_malformed_user_field_is_rejected():
    init_data = sign_init_data(BOT_TOKEN, {"no_id_field": True})
    with pytest.raises(InvalidInitData, match="malformed user"):
        validate_init_data(init_data, BOT_TOKEN)
