from backend.security import hash_password, verify_password


def test_verify_password_correct():
    password = "mypassword"

    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False
