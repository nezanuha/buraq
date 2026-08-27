"""
`select_related()` / `prefetch_related()` actually resolving relations.

Regression: a ``ForeignKey`` field is a plain integer column — accessing it
returns the raw id, never the related instance, with or without
``select_related()``. `select_related()`/`prefetch_related()` tried to apply
SQLAlchemy loader strategies (`joinedload`/`selectinload`) to these columns
and to the framework's own reverse-FK/many-to-many descriptors, none of
which are real SQLAlchemy relationships — every call raised
``sqlalchemy.exc.ArgumentError: expected ORM mapped attribute for loader
strategy argument``. `Prefetch.apply()` existed and was documented but was
never actually called from `prefetch_related()`, and separately assumed a
Django-style `<model>_id` column name that this ORM does not generate.

Fixed by batch-fetching instead of joining: `select_related()` collects the
raw ids after the main query and issues one follow-up query per named
relation; `prefetch_related()` now actually calls `Prefetch.apply()`, which
does the same for the reverse-FK and many-to-many direction. Both are O(1)
extra queries regardless of row count — no per-row queries — and the
relation's normal accessor (`.category`, `.docs.all()`, `.tags.all()`)
returns the resolved value with no further query once eager-loaded, exactly
as it would with none of this called, just resolved instead of raw.
"""

import pytest

from buraq import models
from buraq.core.db import Base, engine
from buraq.orm.prefetch import Prefetch


class RelCategory(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        db_table = "test_rel_categories"


class RelDoc(models.Model):
    title = models.CharField(max_length=50)
    category = models.ForeignKey(RelCategory, related_name="docs", null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "test_rel_docs"


class RelTag(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        db_table = "test_rel_tags"


class RelPost(models.Model):
    title = models.CharField(max_length=50)
    tags = models.ManyToManyField(RelTag, related_name="posts")

    class Meta:
        db_table = "test_rel_posts"


@pytest.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── select_related() — forward FK ──────────────────────────────────────────


async def test_fk_is_the_raw_id_without_select_related(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Button", category=cat.id)

    doc = await RelDoc.objects.get(title="Button")
    assert doc.category == cat.id
    assert isinstance(doc.category, int)


async def test_select_related_resolves_the_same_attribute_to_the_object(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Button", category=cat.id)

    doc = await RelDoc.objects.select_related("category").get(title="Button")
    assert isinstance(doc.category, RelCategory)
    assert doc.category.name == "Components"


async def test_select_related_via_first(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Button", category=cat.id)

    doc = await RelDoc.objects.select_related("category").first()
    assert isinstance(doc.category, RelCategory)


async def test_select_related_leaves_null_fk_as_none(db):
    await RelDoc.objects.create(title="Orphan", category=None)

    doc = await RelDoc.objects.select_related("category").get(title="Orphan")
    assert doc.category is None


async def test_select_related_survives_chaining(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Button", category=cat.id)

    docs = await RelDoc.objects.select_related("category").filter(is_active=True).all()
    assert isinstance(docs[0].category, RelCategory)


# ── prefetch_related() — reverse FK ────────────────────────────────────────


async def test_reverse_fk_all_without_prefetch_returns_a_lazy_queryset(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Button", category=cat.id)

    fetched = await RelCategory.objects.get(id=cat.id)
    result = fetched.docs.all()
    assert not isinstance(result, list)  # still lazy — needs await/iteration
    resolved = await result
    expected = await RelDoc.objects.filter(category=cat.id).all()
    assert [d.id for d in resolved] == [d.id for d in expected]


async def test_prefetch_related_reverse_fk_makes_all_synchronous(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Button", category=cat.id)
    await RelDoc.objects.create(title="Card", category=cat.id)

    fetched = await RelCategory.objects.prefetch_related("docs").get(id=cat.id)
    docs = fetched.docs.all()  # no await — this is the point
    assert isinstance(docs, list)
    assert {d.title for d in docs} == {"Button", "Card"}


async def test_prefetch_related_groups_by_the_correct_parent(db):
    cat_a = await RelCategory.objects.create(name="A")
    cat_b = await RelCategory.objects.create(name="B")
    await RelDoc.objects.create(title="A-doc", category=cat_a.id)
    await RelDoc.objects.create(title="B-doc", category=cat_b.id)

    cats = await RelCategory.objects.prefetch_related("docs").order_by("name").all()
    assert [d.title for d in cats[0].docs.all()] == ["A-doc"]
    assert [d.title for d in cats[1].docs.all()] == ["B-doc"]


async def test_prefetch_related_empty_relation_is_an_empty_list_not_a_query(db):
    cat = await RelCategory.objects.create(name="Lonely")

    fetched = await RelCategory.objects.prefetch_related("docs").get(id=cat.id)
    assert fetched.docs.all() == []


async def test_prefetch_object_with_custom_queryset_filters(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Active", category=cat.id, is_active=True)
    await RelDoc.objects.create(title="Inactive", category=cat.id, is_active=False)

    fetched = await RelCategory.objects.prefetch_related(
        Prefetch("docs", queryset=RelDoc.objects.filter(is_active=True))
    ).get(id=cat.id)
    assert [d.title for d in fetched.docs.all()] == ["Active"]


async def test_prefetch_related_via_first(db):
    cat = await RelCategory.objects.create(name="Components")
    await RelDoc.objects.create(title="Button", category=cat.id)

    fetched = await RelCategory.objects.prefetch_related("docs").first()
    assert fetched.docs.all() == [] or fetched.docs.all()[0].title == "Button"


# ── prefetch_related() — many-to-many ──────────────────────────────────────


async def test_m2m_all_without_prefetch_still_needs_await(db):
    post = await RelPost.objects.create(title="Hello")
    tag = await RelTag.objects.create(name="news")
    await post.tags.add(tag)

    fetched = await RelPost.objects.get(id=post.id)
    result = fetched.tags.all()
    assert not isinstance(result, list)  # still a coroutine — needs await
    assert [t.name for t in await result] == ["news"]


async def test_prefetch_related_m2m_makes_all_synchronous(db):
    post = await RelPost.objects.create(title="Hello")
    tag_a = await RelTag.objects.create(name="news")
    tag_b = await RelTag.objects.create(name="tips")
    await post.tags.add(tag_a, tag_b)

    fetched = await RelPost.objects.prefetch_related("tags").get(id=post.id)
    tags = fetched.tags.all()  # no await
    assert isinstance(tags, list)
    assert {t.name for t in tags} == {"news", "tips"}
