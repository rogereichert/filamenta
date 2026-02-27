from django import forms
from .models import Cliente
import re

INPUT_CLASS = (
    "w-full mt-1 px-4 py-2 rounded-xl "
    "bg-slate-900/60 border border-white/10 "
    "text-slate-100 placeholder:text-slate-500 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500/60 "
    "focus:border-indigo-500/40 transition"
)

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nome", "telefone", "email"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: Roger Reichert"}),
            "telefone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: (51) 99999-9999"}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: roger@email.com"}),
        }

    def clean_telefone(self):
        telefone = self.cleaned_data.get("telefone", "") or ""
        return re.sub(r"\D", "", telefone)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return ""
        qs = Cliente.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cliente com este email.")
        return email
