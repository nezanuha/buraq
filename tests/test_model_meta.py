"""
Tests for ``class Meta`` options on models.

Covers the option surface exposed through ``Model._meta`` (buraq.orm.options)
and the behaviour the model metaclass derives from it.
"""

import pytest

from buraq import models
from buraq.core.db import unmanaged_table_names
from buraq.orm.manager import Manager

# ── Identity: app_label, label, label_lower, verbose names ────────────────────

def test_label_and_verbose_names_default_from_class_name():
    class BlogPost(models.Model):
        title = models.CharField(max_length=10)

    assert BlogPost._meta.object_name == "BlogPost"
    assert BlogPost._meta.model_name == "blogpost"
    # CamelCase becomes spaced lowercase.
    assert BlogPost._meta.verbose_name == "blog post"
    assert BlogPost._meta.verbose_name_plural == "blog posts"
    assert BlogPost._meta.label.endswith(".BlogPost")
    assert BlogPost._meta.label_lower.endswith(".blogpost")


def test_explicit_app_label_and_verbose_names_win():
    class Pizza(models.Model):
        name = models.CharField(max_length=10)

        class Meta:
            app_label = "food"
            verbose_name = "pizza pie"
            verbose_name_plural = "pizza pies"

    assert Pizza._meta.label == "food.Pizza"
    assert Pizza._meta.label_lower == "food.pizza"
    assert Pizza._meta.verbose_name_plural == "pizza pies"


def test_legacy_meta_aliases_still_populated():
    """buraq.contrib.admin reads these directly."""

    class Widget(models.Model):
        name = models.CharField(max_length=10)

        class Meta:
            verbose_name = "gadget"

    assert Widget._meta_verbose_name == "gadget"
    assert Widget._meta_verbose_name_plural == "gadgets"


# ── Table options ─────────────────────────────────────────────────────────────

def test_db_table_and_alias_and_comment():
    class Album(models.Model):
        name = models.CharField(max_length=10)

        class Meta:
            db_table = "music_album"
            db_table_comment = "Music albums"

    assert Album.__tablename__ == "music_album"
    assert Album.__table__.comment == "Music albums"


def test_table_name_is_an_alias_for_db_table():
    class Legacy(models.Model):
        name = models.CharField(max_length=10)

        class Meta:
            table_name = "legacy_rows"

    assert Legacy.__tablename__ == "legacy_rows"


# ── abstract ──────────────────────────────────────────────────────────────────

def test_abstract_model_has_no_table_and_shares_columns():
    class TimeStamped(models.Model):
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            abstract = True

    class Article(TimeStamped):
        title = models.CharField(max_length=50)

    assert TimeStamped._meta.abstract is True
    assert not hasattr(TimeStamped, "__table__")

    assert Article._meta.abstract is False
    assert {"id", "title", "created_at"} <= set(Article.__table__.columns.keys())


def test_abstract_is_not_inherited_through_meta_subclassing():
    class Base_(models.Model):
        name = models.CharField(max_length=10)

        class Meta:
            abstract = True
            ordering = ["name"]

    class Child(Base_):
        class Meta(Base_.Meta):
            pass

    # Inheriting Meta must not make the child abstract too.
    assert Child._meta.abstract is False
    assert hasattr(Child, "__table__")
    assert Child._meta.ordering == ["name"]


# ── proxy ─────────────────────────────────────────────────────────────────────

def test_proxy_shares_parent_table_but_has_own_meta():
    class Person(models.Model):
        name = models.CharField(max_length=50)

    class OrderedPerson(Person):
        class Meta:
            proxy = True
            ordering = ["name"]
            verbose_name = "ordered person"

    assert OrderedPerson._meta.proxy is True
    assert OrderedPerson.__table__ is Person.__table__
    assert OrderedPerson._meta.concrete_model is Person
    assert OrderedPerson._meta.ordering == ["name"]
    assert Person._meta.ordering == []


def test_proxy_without_concrete_parent_is_rejected():
    with pytest.raises(TypeError, match="concrete model parent"):

        class Orphan(models.Model):
            class Meta:
                proxy = True


# ── managed ───────────────────────────────────────────────────────────────────

def test_unmanaged_model_is_excluded_from_table_creation():
    class DbView(models.Model):
        value = models.IntegerField()

        class Meta:
            db_table = "reporting_view"
            managed = False

    assert DbView._meta.managed is False
    assert "reporting_view" in unmanaged_table_names()


def test_models_are_managed_by_default():
    class Normal(models.Model):
        value = models.IntegerField()

    assert Normal._meta.managed is True
    assert Normal.__tablename__ not in unmanaged_table_names()


# ── ordering / get_latest_by ──────────────────────────────────────────────────

def test_get_latest_by_resolves_for_latest_and_earliest():
    class Order(models.Model):
        placed_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            get_latest_by = "placed_at"

    assert Order.objects.all()._latest_by_fields() == ("placed_at",)


def test_get_latest_by_accepts_a_list():
    class Task(models.Model):
        priority = models.IntegerField(default=0)
        due = models.DateTimeField(null=True)

        class Meta:
            get_latest_by = ["-priority", "due"]

    assert Task.objects.all()._latest_by_fields() == ("-priority", "due")


def test_latest_defaults_to_primary_key_without_meta():
    class Plain(models.Model):
        name = models.CharField(max_length=10)

    assert Plain.objects.all()._latest_by_fields() == ("id",)


# ── order_with_respect_to ─────────────────────────────────────────────────────

def test_order_with_respect_to_adds_column_ordering_and_helpers():
    class Question(models.Model):
        text = models.TextField()

    class Answer(models.Model):
        question_id = models.ForeignKey(Question)

        class Meta:
            order_with_respect_to = "question_id"

    assert "_order" in Answer.__table__.columns
    assert Answer._meta.ordering == ["_order"]
    # Accessors land on the model being ordered against...
    assert hasattr(Question, "get_answer_order")
    assert hasattr(Question, "set_answer_order")
    # ...and navigation helpers on the ordered model.
    assert hasattr(Answer, "get_next_in_order")
    assert hasattr(Answer, "get_previous_in_order")


def test_order_with_respect_to_conflicts_with_ordering():
    class Poll(models.Model):
        text = models.TextField()

    with pytest.raises(TypeError, match="cannot be combined"):

        class Choice(models.Model):
            poll_id = models.ForeignKey(Poll)

            class Meta:
                order_with_respect_to = "poll_id"
                ordering = ["id"]


# ── managers ──────────────────────────────────────────────────────────────────

def test_objects_manager_created_when_none_declared():
    class Simple(models.Model):
        name = models.CharField(max_length=10)

    assert isinstance(Simple.objects, Manager)
    assert Simple._default_manager is Simple.objects
    assert Simple._base_manager is Simple.objects


def test_manager_name_options_select_declared_managers():
    class Published(Manager):
        pass

    class Entry(models.Model):
        title = models.CharField(max_length=10)

        objects = Manager()
        published = Published()

        class Meta:
            default_manager_name = "published"
            base_manager_name = "objects"

    assert set(Entry._managers) == {"objects", "published"}
    assert isinstance(Entry._default_manager, Published)
    assert Entry._base_manager is Entry.objects
    # Declared managers get bound to the model by the metaclass.
    assert Entry.published._model is Entry


def test_unknown_manager_name_is_rejected():
    with pytest.raises(ValueError, match="does not match any manager"):

        class Broken(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                default_manager_name = "nope"


# ── default_related_name ──────────────────────────────────────────────────────

def test_default_related_name_sets_the_reverse_accessor():
    class Author(models.Model):
        name = models.CharField(max_length=50)

    class Book(models.Model):
        author_id = models.ForeignKey(Author)

        class Meta:
            default_related_name = "books"

    assert hasattr(Author, "books")


def test_reverse_accessor_falls_back_to_model_set():
    class Tag(models.Model):
        label = models.CharField(max_length=20)

    class Note(models.Model):
        tag_id = models.ForeignKey(Tag)

    assert hasattr(Tag, "note_set")


def test_explicit_related_name_beats_default_related_name():
    class Shelf(models.Model):
        name = models.CharField(max_length=20)

    class Item(models.Model):
        shelf_id = models.ForeignKey(Shelf, related_name="items")

        class Meta:
            default_related_name = "ignored"

    assert hasattr(Shelf, "items")
    assert not hasattr(Shelf, "ignored")


# ── permissions ───────────────────────────────────────────────────────────────

def test_default_permissions_are_generated():
    class Report(models.Model):
        title = models.CharField(max_length=10)

    codenames = [c for c, _ in Report._meta.get_default_permissions()]
    assert codenames == ["add_report", "change_report", "delete_report", "view_report"]


def test_extra_permissions_are_appended():
    class Delivery(models.Model):
        address = models.CharField(max_length=50)

        class Meta:
            permissions = [("can_deliver", "Can deliver")]

    perms = Delivery._meta.get_default_permissions()
    assert ("can_deliver", "Can deliver") in perms
    assert len(perms) == 5


def test_default_permissions_can_be_disabled():
    class Silent(models.Model):
        name = models.CharField(max_length=10)

        class Meta:
            default_permissions = ()

    assert Silent._meta.get_default_permissions() == []


# ── indexes / constraints / unique_together still work ────────────────────────

def test_indexes_and_unique_together_are_applied():
    class Customer(models.Model):
        first_name = models.CharField(max_length=50)
        last_name = models.CharField(max_length=50)

        class Meta:
            unique_together = [["first_name", "last_name"]]
            indexes = [
                models.Index(fields=["last_name"]),
                models.Index(fields=["first_name"], name="first_name_idx"),
            ]

    index_names = {ix.name for ix in Customer.__table__.indexes}
    assert "first_name_idx" in index_names
    constraint_types = {type(c).__name__ for c in Customer.__table__.constraints}
    assert "UniqueConstraint" in constraint_types


# ── abstract + ForeignKey ─────────────────────────────────────────────────────

def test_foreign_key_on_abstract_base_is_copied_to_each_subclass():
    class Owner(models.Model):
        name = models.CharField(max_length=50)

    class Owned(models.Model):
        owner_id = models.ForeignKey(Owner)

        class Meta:
            abstract = True

    class Car(Owned):
        plate = models.CharField(max_length=20)

    class Boat(Owned):
        hull = models.CharField(max_length=20)

    # Each concrete table gets its own column object and its own FK constraint.
    assert Car.__table__.c.owner_id is not Boat.__table__.c.owner_id
    for model in (Car, Boat):
        targets = {fk.target_fullname for fk in model.__table__.foreign_keys}
        # Read the name off the model rather than spelling it: table names carry
        # the app label, which here is whatever module the test lives in.
        assert targets == {f"{Owner.__tablename__}.id"}


def test_reverse_accessors_created_for_inherited_foreign_keys():
    class Studio(models.Model):
        name = models.CharField(max_length=50)

    class Produced(models.Model):
        studio_id = models.ForeignKey(Studio)

        class Meta:
            abstract = True

    class Film(Produced):
        title = models.CharField(max_length=50)

    class Series(Produced):
        title = models.CharField(max_length=50)

    # The FK lives on the abstract base, so both children must still register.
    assert hasattr(Studio, "film_set")
    assert hasattr(Studio, "series_set")


def test_default_related_name_applies_to_inherited_foreign_key():
    class Label(models.Model):
        name = models.CharField(max_length=50)

    class Signed(models.Model):
        label_id = models.ForeignKey(Label)

        class Meta:
            abstract = True

    class Band(Signed):
        name = models.CharField(max_length=50)

        class Meta:
            default_related_name = "bands"

    assert hasattr(Label, "bands")


# ── Meta.ordering is actually applied ─────────────────────────────────────────

def test_meta_ordering_reaches_the_query():
    class OrderedArticle(models.Model):
        title = models.CharField(max_length=50)

        class Meta:
            ordering = ["-title"]

    sql = str(OrderedArticle.objects.all()._query)
    assert "ORDER BY" in sql and "DESC" in sql


def test_explicit_order_by_replaces_meta_ordering():
    class Story(models.Model):
        title = models.CharField(max_length=50)

        class Meta:
            ordering = ["-title"]

    sql = str(Story.objects.all().order_by("title")._query)
    assert sql.count("ORDER BY") == 1
    assert "DESC" not in sql, "Meta.ordering must be replaced, not appended to"


def test_order_by_with_no_arguments_clears_ordering():
    class ClearedItem(models.Model):
        name = models.CharField(max_length=50)

        class Meta:
            ordering = ["name"]

    assert "ORDER BY" not in str(ClearedItem.objects.all().order_by()._query)


def test_model_without_meta_ordering_is_unordered():
    class Loose(models.Model):
        name = models.CharField(max_length=50)

    assert "ORDER BY" not in str(Loose.objects.all()._query)


# ── Unknown Meta options ──────────────────────────────────────────────────────

def test_unknown_meta_option_raises():
    with pytest.raises(TypeError, match="invalid attribute"):

        class Typo(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                orderring = ["-name"]  # typo for `ordering`


def test_unknown_meta_option_error_names_the_offenders():
    with pytest.raises(TypeError, match="verbose_nme"):

        class Typo2(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                verbose_nme = "thing"
