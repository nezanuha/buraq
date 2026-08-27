"""The CSRF token is masked per response.

Compression plus a secret that repeats in every response is the BREACH
precondition: an attacker who can get reflected input into a page reads the
secret a character at a time from how well the response compresses. Buraq
compresses by default, so the token must not repeat.
"""

from buraq.contrib.csrf import mask_token, unmask_token

SECRET = "ab" * 32


def test_the_same_secret_looks_different_every_time():
    first, second = mask_token(SECRET), mask_token(SECRET)

    assert first != second
    assert unmask_token(first) == unmask_token(second) == SECRET


def test_a_masked_token_never_contains_the_secret():
    """If the secret appeared verbatim, masking would buy nothing."""
    for _ in range(20):
        assert SECRET not in mask_token(SECRET)


def test_rubbish_is_returned_unchanged_rather_than_raising():
    """Validation compares the result; a forged token must simply not match."""
    assert unmask_token("not-hex-at-all") == "not-hex-at-all"
    assert unmask_token("") == ""
    # Odd length cannot be split into mask and payload.
    assert unmask_token("abc") == "abc"


def test_a_forged_token_does_not_unmask_to_the_secret():
    assert unmask_token("cd" * 64) != SECRET
