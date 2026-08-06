# Database Transactions

`buraq.db.transaction` provides async-first transaction management.

```python
from buraq.db import transaction
```

## atomic()

Wrap a block of database work in a single transaction. If an exception is raised, the transaction rolls back automatically.

### As a context manager

```python
from buraq.db import transaction

async def create_order(user, items):
    async with transaction.atomic():
        order = await Order.objects.create(user_id=user.id)
        for item in items:
            await OrderItem.objects.create(order_id=order.id, product_id=item.id)
        await Inventory.objects.filter(product_id__in=[i.id for i in items]).update(
            stock=F("stock") - 1
        )
    # commits here — rollback on any exception above
```

### As a decorator

```python
@transaction.atomic
async def transfer_funds(from_account_id, to_account_id, amount):
    await Account.objects.filter(id=from_account_id).update(balance=F("balance") - amount)
    await Account.objects.filter(id=to_account_id).update(balance=F("balance") + amount)
```

Both forms are equivalent — choose whichever fits the call site better.

## on_commit()

Run a callback after the current transaction commits successfully. Useful for side effects that must not happen if the transaction rolls back (sending emails, triggering webhooks, etc.):

```python
async with transaction.atomic():
    user = await User.objects.create(email="alice@example.com")

    async def send_welcome():
        await send_mail("Welcome!", "Thanks for signing up.", [user.email])

    await transaction.on_commit(send_welcome)
```

`on_commit` accepts both sync and async callables.

!!! note
    In the current implementation, `on_commit` runs immediately inside the atomic block rather than deferring to after the commit. For deferred side effects, call it after the `async with` block closes.

## non_atomic()

Mark a function as explicitly not requiring a transaction — useful for read-only views or functions that manage their own sessions:

```python
@transaction.non_atomic
async def read_report(request):
    return await Report.objects.all()
```

This is a documentation marker only — it does not open or close any transaction.

## Nesting

Nested `atomic()` calls are supported — the inner block shares the outer transaction:

```python
async with transaction.atomic():
    await Post.objects.create(title="Draft")

    async with transaction.atomic():
        await Tag.objects.create(name="python")
    # inner block exits — still in outer transaction

# outer commits or rolls back everything
```

## Error handling

```python
from buraq.db.transaction import TransactionManagementError

try:
    async with transaction.atomic():
        await Post.objects.create(title="")  # raises ValidationError
except Exception as e:
    # transaction already rolled back
    print(f"Failed: {e}")
```
