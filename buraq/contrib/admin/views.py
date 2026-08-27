from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

if TYPE_CHECKING:
    from buraq.contrib.admin.site import AdminSite

_admin_loader_added = False


def _ensure_admin_templates() -> None:
    global _admin_loader_added
    if _admin_loader_added:
        return
    from jinja2 import ChoiceLoader, FileSystemLoader

    from buraq.core.templating import get_templates

    admin_dir = str(Path(__file__).parent / "templates")
    env = get_templates().env
    # Last, not first. Ahead of the project's own directory these templates
    # could not be overridden at all: a project that wrote
    # templates/admin/login.html to rebrand the admin was silently ignored.
    if hasattr(env.loader, "loaders"):
        env.loader.loaders.append(FileSystemLoader(admin_dir))
    else:
        env.loader = ChoiceLoader([env.loader, FileSystemLoader(admin_dir)])
    _admin_loader_added = True


def _make_cookie(user_id: int, secret: str) -> str:
    payload = base64.urlsafe_b64encode(str(user_id).encode()).decode()
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{payload}.{sig}"


def _verify_cookie(cookie: str, secret: str) -> int | None:
    try:
        payload, sig = cookie.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(sig, expected):
            return None
        return int(base64.urlsafe_b64decode(payload).decode())
    except Exception:
        return None


def get_admin_router(admin_site: AdminSite) -> APIRouter:
    # No prefix: where the admin lives is chosen at the mount point, so a
    # deployment can move it off the first path every scanner tries.
    router = APIRouter(tags=["admin"])

    async def _auth(request: Request):
        from buraq.conf import settings
        from buraq.contrib.auth.models import User

        cookie = request.cookies.get("_buraq_admin")
        if not cookie:
            return None
        secret = getattr(settings, "SECRET_KEY", "buraq-admin-secret")
        user_id = _verify_cookie(cookie, secret)
        if not user_id:
            return None
        try:
            user = await User.objects.get(id=user_id)
            return user if (user.is_staff or user.is_superuser) else None
        except Exception:
            return None

    def _render(request: Request, template: str, ctx: dict) -> HTMLResponse:
        _ensure_admin_templates()
        from buraq.core.templating import get_templates

        groups: dict[str, list] = defaultdict(list)
        for ma in admin_site._registry.values():
            groups[ma.get_app_label()].append(ma)

        ctx.setdefault("admin_site", admin_site)
        ctx.setdefault("user", None)
        ctx["app_groups"] = dict(groups)
        ctx["current_path"] = str(request.url.path)
        ctx["request"] = request
        ctx["buraq_static"] = "/_buraq/static"

        return HTMLResponse(get_templates().get_template(template).render(ctx))

    def _redirect_login() -> RedirectResponse:
        return RedirectResponse(f"{admin_site.prefix}/login", status_code=303)

    def _find_ma(app_label: str, model_name: str):
        for ma in admin_site._registry.values():
            if ma.get_app_label() == app_label and ma.get_model_name() == model_name:
                return ma
        return None

    # â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @router.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        return _render(request, "admin/login.html", {"error": None})

    @router.post("/login")
    async def login_post(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        from buraq.conf import settings
        from buraq.contrib.auth.models import User

        error = "Invalid credentials or insufficient permissions."
        try:
            user = await User.objects.get(username=username)
            from buraq.contrib.auth import check_password as _async_check
            if not await _async_check(password, user.hashed_password):
                raise ValueError
            if not (user.is_staff or user.is_superuser):
                raise ValueError
        except Exception:
            return _render(request, "admin/login.html", {"error": error})

        secret = getattr(settings, "SECRET_KEY", "buraq-admin-secret")
        response = RedirectResponse(f"{admin_site.prefix}/", status_code=303)
        response.set_cookie(
            "_buraq_admin",
            _make_cookie(user.id, secret),
            httponly=True,
            samesite="lax",
            secure=not settings.DEBUG,
        )
        return response

    @router.get("/logout")
    async def logout():
        resp = RedirectResponse(f"{admin_site.prefix}/login", status_code=303)
        resp.delete_cookie("_buraq_admin")
        return resp

    # â”€â”€ Dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @router.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        model_cards = []
        for model, ma in admin_site._registry.items():
            try:
                count = await model.objects.count()
            except Exception:
                count = "â€”"
            model_cards.append({
                "app_label": ma.get_app_label(),
                "model_name": ma.get_model_name(),
                "verbose_name_plural": ma.get_verbose_name_plural(),
                "count": count,
                "can_create": ma.can_create,
            })

        return _render(request, "admin/dashboard.html", {
            "user": user,
            "model_cards": model_cards,
        })

    # â”€â”€ Model list â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @router.get("/{app_label}/{model_name}/", response_class=HTMLResponse)
    async def model_list(request: Request, app_label: str, model_name: str):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma:
            raise HTTPException(404)

        page = int(request.query_params.get("page", 1))
        search = request.query_params.get("q", "").strip()
        ordering_param = request.query_params.get("o", "")

        qs = ma.model.objects.all()

        # â”€â”€ Search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if search and ma.search_fields:
            from buraq.orm.query import Q
            q_filter = None
            for field in ma.search_fields:
                clause = Q(**{f"{field}__icontains": search})
                q_filter = clause if q_filter is None else (q_filter | clause)
            qs = qs.filter(q_filter)

        # â”€â”€ list_filter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        filter_params: dict[str, str] = {}
        for field in ma.list_filter:
            val = request.query_params.get(field, "")
            if val:
                filter_params[field] = val
                with contextlib.suppress(Exception):
                    qs = qs.filter(**{field: val})

        # â”€â”€ Ordering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        all_col_names = ma._all_column_names()
        if ordering_param:
            col = ordering_param.lstrip("-")
            qs = qs.order_by(ordering_param) if col in all_col_names else qs.order_by("-id")
        elif ma.ordering:
            qs = qs.order_by(*ma.ordering)
        else:
            qs = qs.order_by("-id")

        # â”€â”€ Paginate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from buraq.contrib.admin.helpers import obj_to_dict, paginate

        total = await qs.count()
        objects = await qs.offset((page - 1) * ma.list_per_page).limit(ma.list_per_page).all()
        pagination = paginate(total, page, ma.list_per_page)
        list_display = ma.get_list_display()

        rows = []
        for obj in objects:
            d = obj_to_dict(obj)
            rows.append({
                "obj_id": d.get("id"),
                "cells": [str(d.get(f, "")) for f in list_display],
            })

        # â”€â”€ Filter groups for sidebar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        filter_groups = []
        for field in ma.list_filter:
            try:
                raw_vals = await ma.model.objects.values_list(field, flat=True).distinct().all()
                vals = sorted({str(v) for v in raw_vals if v is not None})
                filter_groups.append({
                    "field": field,
                    "label": field.replace("_", " ").title(),
                    "values": vals,
                    "active": filter_params.get(field, ""),
                })
            except Exception:
                pass

        return _render(request, "admin/list.html", {
            "user": user,
            "ma": ma,
            "app_label": app_label,
            "model_name": model_name,
            "list_display": list_display,
            "rows": rows,
            "pagination": pagination,
            "search": search,
            "success": request.query_params.get("success", ""),
            "filter_groups": filter_groups,
            "filter_params": filter_params,
            "ordering_param": ordering_param,
        })

    # â”€â”€ Bulk action POST â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @router.post("/{app_label}/{model_name}/")
    async def model_list_action(request: Request, app_label: str, model_name: str):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma:
            raise HTTPException(404)

        form = await request.form()
        action = form.get("action", "")
        selected = [v for v in form.getlist("select") if str(v).isdigit()]

        redirect_url = f"{admin_site.prefix}/{app_label}/{model_name}/"

        if action == "delete_selected" and ma.can_delete and selected:
            from buraq.orm.query import Q
            ids = [int(i) for i in selected]
            q = None
            for id_ in ids:
                clause = Q(id=id_)
                q = clause if q is None else (q | clause)
            try:
                await ma.model.objects.filter(q).delete()
                redirect_url += "?success=deleted"
            except Exception:
                pass

        return RedirectResponse(redirect_url, status_code=303)

    # â”€â”€ Add â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @router.get("/{app_label}/{model_name}/add/", response_class=HTMLResponse)
    async def model_add_get(request: Request, app_label: str, model_name: str):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma or not ma.can_create:
            raise HTTPException(403)

        from buraq.contrib.admin.helpers import get_form_fields

        return _render(request, "admin/change.html", {
            "user": user,
            "ma": ma,
            "app_label": app_label,
            "model_name": model_name,
            "form_fields": get_form_fields(ma),
            "obj": {},
            "is_add": True,
            "error": None,
        })

    @router.post("/{app_label}/{model_name}/add/")
    async def model_add_post(request: Request, app_label: str, model_name: str):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma or not ma.can_create:
            raise HTTPException(403)

        from buraq.contrib.admin.helpers import coerce_form_data, get_form_fields

        form = await request.form()
        save_action = form.get("_save_action", "")
        data = coerce_form_data(dict(form), ma)

        try:
            obj = await ma.model.objects.create(**data)
            obj_id = getattr(obj, "id", None)
            if save_action == "_continue" and obj_id:
                return RedirectResponse(
                    f"{admin_site.prefix}/{app_label}/{model_name}/{obj_id}/change/?success=created",
                    status_code=303,
                )
            if save_action == "_addanother":
                return RedirectResponse(
                    f"{admin_site.prefix}/{app_label}/{model_name}/add/?success=created",
                    status_code=303,
                )
            return RedirectResponse(
                f"{admin_site.prefix}/{app_label}/{model_name}/?success=created", status_code=303
            )
        except Exception as e:
            return _render(request, "admin/change.html", {
                "user": user,
                "ma": ma,
                "app_label": app_label,
                "model_name": model_name,
                "form_fields": get_form_fields(ma),
                "obj": dict(form),
                "is_add": True,
                "error": str(e),
            })

    # â”€â”€ Change â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @router.get("/{app_label}/{model_name}/{obj_id}/change/", response_class=HTMLResponse)
    async def model_change_get(
        request: Request, app_label: str, model_name: str, obj_id: int
    ):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma:
            raise HTTPException(404)

        try:
            obj = await ma.model.objects.get(id=obj_id)
        except Exception:
            raise HTTPException(404) from None

        from buraq.contrib.admin.helpers import get_form_fields, obj_to_dict

        return _render(request, "admin/change.html", {
            "user": user,
            "ma": ma,
            "app_label": app_label,
            "model_name": model_name,
            "form_fields": get_form_fields(ma),
            "obj": obj_to_dict(obj),
            "is_add": False,
            "error": None,
            "success": request.query_params.get("success", ""),
        })

    @router.post("/{app_label}/{model_name}/{obj_id}/change/")
    async def model_change_post(
        request: Request, app_label: str, model_name: str, obj_id: int
    ):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma or not ma.can_edit:
            raise HTTPException(403)

        try:
            obj = await ma.model.objects.get(id=obj_id)
        except Exception:
            raise HTTPException(404) from None

        from buraq.contrib.admin.helpers import coerce_form_data, get_form_fields, obj_to_dict

        form = await request.form()
        save_action = form.get("_save_action", "")
        data = coerce_form_data(dict(form), ma)

        try:
            for k, v in data.items():
                setattr(obj, k, v)
            await obj.save()
            if save_action == "_continue":
                return RedirectResponse(
                    f"{admin_site.prefix}/{app_label}/{model_name}/{obj_id}/change/?success=saved",
                    status_code=303,
                )
            if save_action == "_addanother":
                return RedirectResponse(
                    f"{admin_site.prefix}/{app_label}/{model_name}/add/",
                    status_code=303,
                )
            return RedirectResponse(
                f"{admin_site.prefix}/{app_label}/{model_name}/?success=saved", status_code=303
            )
        except Exception as e:
            return _render(request, "admin/change.html", {
                "user": user,
                "ma": ma,
                "app_label": app_label,
                "model_name": model_name,
                "form_fields": get_form_fields(ma),
                "obj": obj_to_dict(obj),
                "is_add": False,
                "error": str(e),
            })

    # â”€â”€ Delete â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @router.get("/{app_label}/{model_name}/{obj_id}/delete/", response_class=HTMLResponse)
    async def model_delete_get(
        request: Request, app_label: str, model_name: str, obj_id: int
    ):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma or not ma.can_delete:
            raise HTTPException(403)

        try:
            obj = await ma.model.objects.get(id=obj_id)
        except Exception:
            raise HTTPException(404) from None

        from buraq.contrib.admin.helpers import obj_to_dict

        return _render(request, "admin/delete.html", {
            "user": user,
            "ma": ma,
            "app_label": app_label,
            "model_name": model_name,
            "obj": obj_to_dict(obj),
            "obj_id": obj_id,
        })

    @router.post("/{app_label}/{model_name}/{obj_id}/delete/")
    async def model_delete_post(
        request: Request, app_label: str, model_name: str, obj_id: int
    ):
        user = await _auth(request)
        if not user:
            return _redirect_login()

        ma = _find_ma(app_label, model_name)
        if not ma or not ma.can_delete:
            raise HTTPException(403)

        try:
            obj = await ma.model.objects.get(id=obj_id)
        except Exception:
            # Already deleted — treat as success
            return RedirectResponse(
                f"{admin_site.prefix}/{app_label}/{model_name}/?success=deleted", status_code=303
            )

        await obj.delete()
        return RedirectResponse(
            f"{admin_site.prefix}/{app_label}/{model_name}/?success=deleted", status_code=303
        )

    return router
