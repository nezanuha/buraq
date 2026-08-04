"""
Paginator — paginate querysets or lists with a familiar API.

Usage:
    from buraq.paginator import Paginator

    # With a plain list
    paginator = Paginator(object_list, per_page=10)
    page = await paginator.page(1)
    for obj in page:
        print(obj)
    page.has_next()           # True/False
    page.next_page_number()   # 2
    paginator.num_pages       # total pages
    paginator.count           # total objects

    # With a QuerySet (async)
    paginator = Paginator(Post.objects.filter(published=True), per_page=10)
    page = await paginator.page(1)
"""
from math import ceil


class InvalidPage(Exception):
    pass


class PageNotAnInteger(InvalidPage):
    pass


class EmptyPage(InvalidPage):
    pass


class Page:
    def __init__(self, object_list: list, number: int, paginator: "Paginator"):
        self.object_list = object_list
        self.number = number
        self.paginator = paginator

    def __repr__(self):
        return f"<Page {self.number} of {self.paginator.num_pages}>"

    def __len__(self):
        return len(self.object_list)

    def __iter__(self):
        return iter(self.object_list)

    def __getitem__(self, index):
        return self.object_list[index]

    def has_next(self) -> bool:
        return self.number < self.paginator.num_pages

    def has_previous(self) -> bool:
        return self.number > 1

    def has_other_pages(self) -> bool:
        return self.has_previous() or self.has_next()

    def next_page_number(self) -> int:
        return self.paginator.validate_number(self.number + 1)

    def previous_page_number(self) -> int:
        return self.paginator.validate_number(self.number - 1)

    def start_index(self) -> int:
        """1-based index of the first item on this page."""
        if self.paginator.count == 0:
            return 0
        return (self.paginator.per_page * (self.number - 1)) + 1

    def end_index(self) -> int:
        """1-based index of the last item on this page."""
        if self.number == self.paginator.num_pages:
            return self.paginator.count
        return self.number * self.paginator.per_page


class Paginator:
    def __init__(
        self,
        object_list,
        per_page: int,
        orphans: int = 0,
        allow_empty_first_page: bool = True,
    ):
        self.object_list = object_list
        self.per_page = int(per_page)
        self.orphans = int(orphans)
        self.allow_empty_first_page = allow_empty_first_page
        self._count = None
        self._num_pages = None

    @property
    def count(self) -> int:
        if self._count is None:
            try:
                self._count = len(self.object_list)
            except TypeError:
                raise TypeError(
                    "Paginator.count is not available before calling page(). "
                    "Use `page = await paginator.page(n)` first."
                ) from None
        return self._count

    @property
    def num_pages(self) -> int:
        if self._num_pages is None:
            count = self.count
            if count == 0 and not self.allow_empty_first_page:
                self._num_pages = 0
            else:
                hits = max(1, count - self.orphans)
                self._num_pages = ceil(hits / self.per_page)
        return self._num_pages

    @property
    def page_range(self):
        return range(1, self.num_pages + 1)

    def validate_number(self, number) -> int:
        try:
            if isinstance(number, float) and not number.is_integer():
                raise ValueError
            number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger(f"That page number is not an integer: {number!r}") from None
        if number < 1:
            raise EmptyPage("That page number is less than 1.")
        if number > self.num_pages and (number != 1 or not self.allow_empty_first_page):
            raise EmptyPage("That page contains no results.")
        return number

    async def page(self, number) -> Page:
        """Return a Page for the given 1-based page number. Works with both lists and QuerySets."""
        # Resolve count
        if self._count is None:
            if hasattr(self.object_list, "count") and callable(self.object_list.count):
                import asyncio
                count = self.object_list.count()
                if asyncio.iscoroutine(count):
                    count = await count
                self._count = count
            else:
                self._count = len(self.object_list)

        number = self.validate_number(number)
        bottom = (number - 1) * self.per_page
        top = bottom + self.per_page
        if top + self.orphans >= self.count:
            top = self.count

        # Slice QuerySet with offset/limit, or plain list slice
        if hasattr(self.object_list, "offset"):
            items = await self.object_list.offset(bottom).limit(top - bottom).all()
        else:
            items = self.object_list[bottom:top]

        return Page(items, number, self)
