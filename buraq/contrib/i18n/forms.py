from buraq.forms.fields import CharField
from buraq.forms.forms import ModelForm
from buraq.forms.widgets import HiddenInput
from buraq.utils.translation import get_language


class TranslatableModelForm(ModelForm):
    language_code = CharField(required=False, widget=HiddenInput)

    async def save(self, commit: bool = True):
        instance = await super().save(commit=commit)
        lang = self.cleaned_data.get("language_code") or get_language() or "en"
        model = self.__class__.Meta.model
        if not hasattr(model, "set_translation"):
            return instance
        trans_cols = {
            c.name for c in model.translation_model.__table__.columns
            if c.name not in ("id", "master_id", "language_code")
        }
        translated_data = {k: v for k, v in self.cleaned_data.items() if k in trans_cols}
        if translated_data:
            await instance.set_translation(lang, **translated_data)
        return instance
