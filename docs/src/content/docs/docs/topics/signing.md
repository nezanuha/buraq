---
title: "Cryptographic Signing"
description: "buraq.utils.signing provides HMAC-SHA256-based signing and verification — useful for tamper-proof tokens in password-reset links, email confirmation URLs, and…"
---

`buraq.utils.signing` provides HMAC-SHA256-based signing and verification — useful for tamper-proof tokens in password-reset links, email confirmation URLs, and API tokens.

```python
from buraq.utils.signing import Signer, TimestampSigner, dumps, loads
```

Signing uses `settings.SECRET_KEY` as the key, so nothing extra needs to be configured.

---

## Signer

Sign and verify arbitrary strings.

```python
from buraq.utils.signing import Signer

signer = Signer()

# Sign
signed = signer.sign("user:42")
# → "user:42:Zm9vYmFy..."

# Verify
value = signer.unsign(signed)
# → "user:42"

# Tampered value raises BadSignature
from buraq.utils.signing import BadSignature

try:
    signer.unsign("user:42:INVALID")
except BadSignature:
    ...  # reject the request
```

### Options

```python
signer = Signer(
    key="override-secret",      # override SECRET_KEY
    sep=".",                    # separator between value and signature
    salt="myapp.password_reset", # extra entropy — use different salts for different purposes
    algorithm="sha256",         # hash algorithm
)
```

Using a distinct `salt` per action prevents a token issued for one purpose (e.g., password reset) from being accepted for another (e.g., email confirmation).

---

## TimestampSigner

Like `Signer`, but embeds a UTC timestamp so you can enforce expiry.

```python
from buraq.utils.signing import TimestampSigner, SignatureExpired

ts = TimestampSigner(salt="myapp.activate")

# Sign
signed = ts.sign(str(user_id))

# Verify within 1 hour
try:
    value = ts.unsign(signed, max_age=3600)
except SignatureExpired:
    return "This link has expired."
except BadSignature:
    return "Invalid link."
```

---

## dumps / loads

Serialize and sign arbitrary JSON-serializable objects. This is the most convenient API for self-contained tokens.

```python
from buraq.utils.signing import dumps, loads, SignatureExpired, BadSignature

# Create a token
token = dumps({"user_id": 42, "action": "activate"}, salt="myapp.activate")

# Verify (within 24 hours)
try:
    data = loads(token, salt="myapp.activate", max_age=86400)
    user_id = data["user_id"]
except SignatureExpired:
    return "Link expired"
except BadSignature:
    return "Invalid link"
```

### Compression

For large payloads, enable zlib compression:

```python
token = dumps(large_obj, compress=True)
data  = loads(token)
```

---

## Common patterns

### Password reset link

```python
from buraq.utils.signing import dumps, loads, SignatureExpired, BadSignature

# In the view that sends the email
token = dumps({"uid": user.id}, salt="buraq.password_reset")
link  = f"https://example.com/reset?token={token}"
# send link to user.email

# In the reset view
async def password_reset_confirm(request):
    token = request.query_params.get("token", "")
    try:
        data = loads(token, salt="buraq.password_reset", max_age=3600)
    except SignatureExpired:
        return await render(request, "reset/expired.html")
    except BadSignature:
        return await render(request, "reset/invalid.html")

    user = await User.objects.get(id=data["uid"])
    # show reset form
```

### Unsubscribe link (no expiry)

```python
from buraq.utils.signing import Signer

signer = Signer(salt="buraq.unsubscribe")
token  = signer.sign(str(user.email))
link   = f"https://example.com/unsubscribe?t={token}"

# In the unsubscribe view
try:
    email = signer.unsign(request.query_params["t"])
except BadSignature:
    raise Http404
await Subscription.objects.filter(email=email).delete()
```

---

## API reference

### `Signer(key=None, sep=":", salt="buraq.utils.signing", algorithm="sha256")`

| Method | Description |
|---|---|
| `sign(value)` | Return `"value:sig"` |
| `unsign(signed_value)` | Return original value or raise `BadSignature` |
| `sign_object(obj)` | JSON-serialize, base64-encode, then sign |
| `unsign_object(signed_value)` | Unsign and deserialize |

### `TimestampSigner(...)`

Inherits `Signer`. `unsign()` and `unsign_object()` accept `max_age` (seconds).

| Exception | When raised |
|---|---|
| `BadSignature` | Signature mismatch or malformed input |
| `SignatureExpired` | Timestamp older than `max_age` |

### `dumps(obj, key=None, salt="buraq.utils.signing", compress=False)`

Returns a signed URL-safe string.

### `loads(s, key=None, salt="buraq.utils.signing", max_age=None)`

Verifies and deserializes. Raises `BadSignature` or `SignatureExpired`.
