import math

import sqlalchemy as sa


def paginate(total: int, page: int, per_page: int) -> dict:
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "page_range": list(range(max(1, page - 2), min(total_pages + 1, page + 3))),
    }


def get_column_type(col) -> str:
    t = type(col.type)
    if t is sa.Boolean:
        return "boolean"
    if t in (sa.Integer, sa.BigInteger, sa.SmallInteger):
        return "integer"
    if t in (sa.Float, sa.Numeric):
        return "float"
    if t is sa.Text:
        return "textarea"
    if t is sa.DateTime:
        return "datetime-local"
    if t is sa.Date:
        return "date"
    if t is sa.JSON:
        return "json"
    return "text"


def _is_auto_col(col) -> bool:
    if col.name == "id":
        return True
    if col.server_default is not None and "now" in str(col.server_default).lower():
        return True
    return getattr(col, "onupdate", None) is not None


def get_form_fields(model_admin) -> list[dict]:
    editable = set(model_admin.get_fields())
    readonly = set(model_admin.readonly_fields)
    result = []
    for col in model_admin._all_columns():
        if _is_auto_col(col):
            continue
        result.append({
            "name": col.name,
            "label": col.name.replace("_", " ").title(),
            "type": get_column_type(col),
            "required": (
                not col.nullable
                and col.default is None
                and col.server_default is None
            ),
            "readonly": col.name in readonly or col.name not in editable,
            "nullable": col.nullable,
        })
    return result


def obj_to_dict(obj) -> dict:
    try:
        return {col.name: getattr(obj, col.name, None) for col in obj.__table__.columns}
    except Exception:
        return {}


def coerce_form_data(form_data: dict, model_admin) -> dict:
    editable = set(model_admin.get_fields())
    result = {}
    for col in model_admin._all_columns():
        name = col.name
        if _is_auto_col(col) or name not in editable:
            continue
        col_type = get_column_type(col)
        # Unchecked checkboxes are absent from POST data — always include booleans
        if col_type == "boolean":
            result[name] = form_data.get(name, "") in ("on", "true", "1", "yes")
            continue
        if name not in form_data:
            continue
        val = form_data.get(name, "")
        if col_type == "integer":
            result[name] = int(val) if val else (None if col.nullable else 0)
        elif col_type == "float":
            result[name] = float(val) if val else (None if col.nullable else 0.0)
        elif val == "" and col.nullable:
            result[name] = None
        else:
            result[name] = val
    return result
