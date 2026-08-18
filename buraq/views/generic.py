"""
Generic class-based views — ListView, DetailView, CreateView, UpdateView, DeleteView.
"""
from buraq.shortcuts import redirect, render
from buraq.views.base import View


class ContextMixin:
    extra_context: dict = None

    async def get_context_data(self, **kwargs) -> dict:
        ctx = dict(self.extra_context or {})
        ctx.update(kwargs)
        return ctx


class TemplateMixin:
    template_name: str = None

    def get_template_name(self) -> str:
        if self.template_name:
            return self.template_name
        if hasattr(self, "model") and self.model:
            model_name = self.model.__name__.lower()
            suffix = getattr(self, "_template_suffix", "_detail.html")
            return f"{model_name}s/{model_name}{suffix}"
        raise ValueError(f"{self.__class__.__name__} requires a template_name")


class TemplateView(ContextMixin, TemplateMixin, View):
    """
    Render a template. Override get_context_data() to add variables.

    Usage:
        class HomeView(TemplateView):
            template_name = "home.html"
            extra_context = {"title": "Welcome"}

        get("/", HomeView.as_view())
    """

    async def get(self, request, **kwargs):
        ctx = await self.get_context_data(**kwargs)
        return await render(request, self.get_template_name(), ctx)


class RedirectView(View):
    """
    Redirect to a URL. Override get_redirect_url() for dynamic targets.

    Usage:
        get("/old/", RedirectView.as_view(url="/new/", permanent=True))
        get("/old/", RedirectView.as_view(url="/new/", preserve_request=True))
    """

    url: str = None
    permanent: bool = False
    query_string: bool = False
    preserve_request: bool = False

    def get_redirect_url(self, **kwargs) -> str:
        url = self.url
        if not url:
            raise ValueError(f"{self.__class__.__name__} requires url")
        if kwargs:
            url = url % kwargs
        if self.query_string and hasattr(self, "request"):
            qs = str(self.request.url.query)
            if qs:
                url = f"{url}?{qs}"
        return url

    def _status_code(self, method: str) -> int:
        """Return the appropriate HTTP status code for the redirect."""
        if self.preserve_request:
            return 308 if self.permanent else 307
        return 301 if self.permanent else 302

    async def get(self, request, **kwargs):
        self.request = request
        url = self.get_redirect_url(**kwargs)
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=url, status_code=self._status_code(request.method))

    async def post(self, request, **kwargs):
        self.request = request
        url = self.get_redirect_url(**kwargs)
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=url, status_code=self._status_code(request.method))

    async def put(self, request, **kwargs):
        return await self.post(request, **kwargs)

    async def patch(self, request, **kwargs):
        return await self.post(request, **kwargs)

    async def delete(self, request, **kwargs):
        return await self.post(request, **kwargs)


class SingleObjectMixin:
    model = None
    queryset = None
    pk_url_kwarg: str = "pk"
    slug_url_kwarg: str = "slug"
    slug_field: str = "slug"
    context_object_name: str = None

    async def get_object(self):
        from buraq.shortcuts import get_object_or_404
        pk = self.kwargs.get(self.pk_url_kwarg)
        slug = self.kwargs.get(self.slug_url_kwarg)
        if pk is not None:
            return await get_object_or_404(self.model, id=pk)
        if slug is not None:
            return await get_object_or_404(self.model, **{self.slug_field: slug})
        raise AttributeError(f"{self.__class__.__name__} requires pk or slug in URL kwargs")

    def get_context_object_name(self) -> str:
        if self.context_object_name:
            return self.context_object_name
        return self.model.__name__.lower() if self.model else "object"


class MultipleObjectMixin:
    model = None
    queryset = None
    ordering = None
    context_object_name: str = None
    paginate_by: int = None
    paginator_class = None
    page_kwarg: str = "page"
    allow_empty: bool = True

    async def get_queryset(self):
        if self.queryset is not None:
            return await self.queryset.all()
        if self.model is not None:
            qs = self.model.objects.all()
            if self.ordering:
                qs = qs.order_by(*self.ordering)
            return await qs
        raise ValueError(f"{self.__class__.__name__} requires model or queryset")

    def get_context_object_name(self) -> str:
        if self.context_object_name:
            return self.context_object_name
        return f"{self.model.__name__.lower()}_list" if self.model else "object_list"

    async def paginate_queryset(self, queryset, page_size: int):
        from buraq.paginator import EmptyPage, PageNotAnInteger, Paginator
        paginator = (self.paginator_class or Paginator)(queryset, page_size)
        page_num = self.request.query_params.get(self.page_kwarg, 1)
        try:
            page = await paginator.page(page_num)
        except PageNotAnInteger:
            page = await paginator.page(1)
        except EmptyPage:
            page = await paginator.page(paginator.num_pages)
        return paginator, page, page.object_list, page.has_other_pages()


# ── Concrete generic views ───────────────────────────────────────────────────

class DetailView(SingleObjectMixin, ContextMixin, TemplateMixin, View):
    """
    Display a single model instance.

    Usage:
        class PostDetailView(DetailView):
            model = Post
            template_name = "posts/detail.html"

        get("/<int:pk>", PostDetailView.as_view(), name="post_detail")
    """

    _template_suffix = "_detail.html"

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        obj = await self.get_object()
        ctx = await self.get_context_data(
            object=obj, **{self.get_context_object_name(): obj}, **kwargs
        )
        return await render(request, self.get_template_name(), ctx)


class ListView(MultipleObjectMixin, ContextMixin, TemplateMixin, View):
    """
    Display a list of model instances.

    Usage:
        class PostListView(ListView):
            model = Post
            template_name = "posts/list.html"
            paginate_by = 10

        get("/", PostListView.as_view(), name="post_list")
    """

    _template_suffix = "_list.html"

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        self.request = request
        object_list = await self.get_queryset()

        if not self.allow_empty and not object_list:
            from buraq.exceptions import Http404
            raise Http404(
                f"Empty list and '{type(self).__name__}.allow_empty' is False."
            )

        context_name = self.get_context_object_name()
        ctx = {"object_list": object_list, context_name: object_list}

        if self.paginate_by:
            paginator, page, object_list, is_paginated = await self.paginate_queryset(
                object_list, self.paginate_by
            )
            ctx.update({
                "paginator": paginator,
                "page_obj": page,
                "is_paginated": is_paginated,
                "object_list": object_list,
                context_name: object_list,
            })

        ctx.update(await self.get_context_data(**kwargs))
        return await render(request, self.get_template_name(), ctx)


class FormMixin(ContextMixin):
    form_class = None
    success_url: str = None
    prefix: str = None

    def get_form_class(self):
        return self.form_class

    def get_form(self, form_class=None, data=None, instance=None):
        if form_class is None:
            form_class = self.get_form_class()
        initial = self.get_initial()
        kwargs = dict(data=data, initial=initial, prefix=self.prefix)
        if instance is not None:
            kwargs["instance"] = instance
        return form_class(**kwargs)

    def get_initial(self) -> dict:
        return {}

    def get_success_url(self) -> str:
        if self.success_url:
            return self.success_url
        raise ValueError(f"{self.__class__.__name__} requires success_url")

    async def form_valid(self, form):
        return redirect(self.get_success_url())

    async def form_invalid(self, request, form):
        context = await self.get_context_data(form=form)
        return await render(request, self.get_template_name(), context)


class CreateView(FormMixin, TemplateMixin, View):
    """
    Display a form and create a model instance on POST.

    Usage:
        class PostCreateView(CreateView):
            model = Post
            form_class = PostForm
            template_name = "posts/form.html"
            success_url = "/posts/"

        get("/new",  PostCreateView.as_view())
        post("/new", PostCreateView.as_view())
    """

    _template_suffix = "_form.html"

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        form = self.get_form()
        ctx = await self.get_context_data(form=form, **kwargs)
        return await render(request, self.get_template_name(), ctx)

    async def post(self, request, **kwargs):
        self.kwargs = kwargs
        form_data = dict(await request.form())
        form = self.get_form(data=form_data)
        if await form.is_valid():
            if hasattr(form, "save"):
                await form.save()
            return await self.form_valid(form)
        return await self.form_invalid(request, form)


class UpdateView(SingleObjectMixin, FormMixin, TemplateMixin, View):
    """
    Display a form and update an existing model instance on POST.

    Usage:
        class PostUpdateView(UpdateView):
            model = Post
            form_class = PostForm
            template_name = "posts/form.html"
            success_url = "/posts/"

        get("/<int:pk>/edit",  PostUpdateView.as_view())
        post("/<int:pk>/edit", PostUpdateView.as_view())
    """

    _template_suffix = "_form.html"

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        obj = await self.get_object()
        form = self.get_form(instance=obj)
        ctx = await self.get_context_data(form=form, object=obj, **kwargs)
        return await render(request, self.get_template_name(), ctx)

    async def post(self, request, **kwargs):
        self.kwargs = kwargs
        obj = await self.get_object()
        form_data = dict(await request.form())
        form = self.get_form(data=form_data, instance=obj)
        if await form.is_valid():
            if hasattr(form, "save"):
                await form.save()
            return await self.form_valid(form)
        return await self.form_invalid(request, form)


class DeleteView(SingleObjectMixin, TemplateMixin, View):
    """
    Display a confirmation page and delete a model instance on POST.

    Usage:
        class PostDeleteView(DeleteView):
            model = Post
            template_name = "posts/confirm_delete.html"
            success_url = "/posts/"

        get("/<int:pk>/delete",  PostDeleteView.as_view())
        post("/<int:pk>/delete", PostDeleteView.as_view())
    """

    _template_suffix = "_confirm_delete.html"
    success_url: str = "/"

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        obj = await self.get_object()
        ctx = {"object": obj, self.get_context_object_name(): obj, **kwargs}
        return await render(request, self.get_template_name(), ctx)

    async def post(self, request, **kwargs):
        self.kwargs = kwargs
        obj = await self.get_object()
        await obj.delete()
        return redirect(self.success_url)


class FormView(ContextMixin, TemplateMixin, View):
    """
    Generic view for displaying and processing a form.

    Usage:
        class ContactView(FormView):
            template_name = "contact.html"
            form_class = ContactForm
            success_url = "/thanks/"

            async def form_valid(self, request, form):
                # handle valid form data
                return redirect(self.success_url)

        get("/contact",  ContactView.as_view())
        post("/contact", ContactView.as_view())
    """

    form_class = None
    success_url: str = "/"
    prefix: str = ""

    def get_form_class(self):
        return self.form_class

    def get_form(self, data=None, **kwargs):
        form_class = self.get_form_class()
        return form_class(data=data, prefix=self.prefix, **kwargs) if form_class else None

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        form = self.get_form()
        ctx = await self.get_context_data(form=form, **kwargs)
        return await render(request, self.get_template_name(), ctx)

    async def post(self, request, **kwargs):
        self.kwargs = kwargs
        raw = dict(await request.form())
        form = self.get_form(data=raw)
        if form is None or await form.is_valid():
            return await self.form_valid(request, form)
        return await self.form_invalid(request, form)

    async def form_valid(self, request, form):
        return redirect(self.success_url)

    async def form_invalid(self, request, form):
        ctx = await self.get_context_data(form=form)
        return await render(request, self.get_template_name(), ctx)


class ArchiveView(ListView):
    """ListView that filters by date field."""
    date_field: str = "created_at"
    allow_future: bool = False


class YearArchiveView(ArchiveView):
    async def get_queryset(self):
        import datetime
        year = int(self.kwargs.get("year", datetime.date.today().year))
        qs = (self.model.objects.all()
              .filter(**{f"{self.date_field}__year": year}))
        return await qs


class MonthArchiveView(ArchiveView):
    async def get_queryset(self):
        import datetime
        year = int(self.kwargs.get("year", datetime.date.today().year))
        month = int(self.kwargs.get("month", datetime.date.today().month))
        qs = (self.model.objects.all()
              .filter(**{f"{self.date_field}__year": year, f"{self.date_field}__month": month}))
        return await qs


class WeekArchiveView(ArchiveView):
    """List objects for a given ISO week number."""

    async def get_queryset(self):
        import datetime
        year = int(self.kwargs.get("year", datetime.date.today().year))
        week = int(self.kwargs.get("week", 1))
        # ISO: Monday = 1
        first_day = datetime.date.fromisocalendar(year, week, 1)
        last_day = first_day + datetime.timedelta(days=6)
        return await self.model.objects.all().filter(
            **{f"{self.date_field}__gte": first_day, f"{self.date_field}__lte": last_day}
        )


class DayArchiveView(ArchiveView):
    """List objects for a specific calendar day."""

    async def get_queryset(self):
        import datetime
        year = int(self.kwargs.get("year", datetime.date.today().year))
        month = int(self.kwargs.get("month", datetime.date.today().month))
        day = int(self.kwargs.get("day", datetime.date.today().day))
        return await self.model.objects.all().filter(**{
            f"{self.date_field}__year": year,
            f"{self.date_field}__month": month,
            f"{self.date_field}__day": day,
        })


class TodayArchiveView(DayArchiveView):
    """List objects for today's date."""

    async def get_queryset(self):
        import datetime
        today = datetime.date.today()
        self.kwargs = {
            "year": today.year,
            "month": today.month,
            "day": today.day,
            **getattr(self, "kwargs", {}),
        }
        return await super().get_queryset()


class ArchiveIndexView(ArchiveView):
    """Top-level archive — list all distinct years that have objects."""

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        years = await self.model.objects.dates(self.date_field, "year")
        ctx = await self.get_context_data(date_list=years, **kwargs)
        return await render(request, self.get_template_name(), ctx)


class DateDetailView(SingleObjectMixin, TemplateMixin, View):
    """Retrieve a single object identified by year/month/day + pk/slug."""

    date_field: str = "created_at"
    _template_suffix = "_detail.html"

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        import datetime
        year = int(kwargs.get("year", datetime.date.today().year))
        month = int(kwargs.get("month", datetime.date.today().month))
        day = int(kwargs.get("day", datetime.date.today().day))
        date_filters = {
            f"{self.date_field}__year": year,
            f"{self.date_field}__month": month,
            f"{self.date_field}__day": day,
        }
        pk = kwargs.get("pk")
        slug = kwargs.get("slug")
        if pk:
            date_filters["id"] = pk
        elif slug:
            date_filters[self.slug_field] = slug
        obj = await self.model.objects.filter(**date_filters).first()
        if obj is None:
            from buraq.exceptions import Http404
            raise Http404
        name = self.get_context_object_name()
        ctx = await self.get_context_data(object=obj, **{name: obj}, **kwargs)
        return await render(request, self.get_template_name(), ctx)
