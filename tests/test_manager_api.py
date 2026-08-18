"""
Manager must expose the same terminal methods as QuerySet.

The docs promise `await Post.objects.exists()` and `await Post.objects.last()`,
but Manager only delegated `count`/`get` — those calls raised AttributeError.
"""

import pytest

from buraq import models
from buraq.core.db import Base, engine


class Gadget(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        db_table = "test_manager_gadgets"


@pytest.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_manager_exists_on_empty_and_populated_table(db):
    assert await Gadget.objects.exists() is False
    await Gadget.objects.create(name="one")
    assert await Gadget.objects.exists() is True


async def test_manager_first_and_last(db):
    await Gadget.objects.create(name="one")
    await Gadget.objects.create(name="two")

    first = await Gadget.objects.first()
    last = await Gadget.objects.last()

    assert first is not None and last is not None
    assert first.name == "one"
    assert last.name == "two"


async def test_manager_first_returns_none_when_empty(db):
    assert await Gadget.objects.first() is None
    assert await Gadget.objects.last() is None


async def test_manager_and_queryset_agree(db):
    await Gadget.objects.create(name="one")

    assert await Gadget.objects.count() == await Gadget.objects.all().count()
    assert await Gadget.objects.exists() == await Gadget.objects.all().exists()
