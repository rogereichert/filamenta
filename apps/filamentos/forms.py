from django import forms
from .models import Filamento

INPUT_CLASS = (
    "w-full mt-1 px-4 py-2 rounded-xl "
    "bg-slate-900/60 border border-white/10 "
    "text-slate-100 placeholder:text-slate-500 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500/60 "
    "focus:border-indigo-500/40 transition"
)

SELECT_CLASS = (
    "w-full mt-1 px-4 py-2 rounded-xl "
    "bg-slate-900/60 border border-white/10 "
    "text-slate-100 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500/60 "
    "focus:border-indigo-500/40 transition"
)

class FilamentoForm(forms.ModelForm):
    class Meta:
        model = Filamento
        fields = ["nome", "material", "cor", "peso_inicial_g", "peso_atual_g", "preco_kg"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: PLA Silk"}),
            "material": forms.Select(attrs={"class": SELECT_CLASS}),
            "cor": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: Laranja"}),
            "peso_inicial_g": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: 1000"}),
            "peso_atual_g": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: 930"}),
            "preco_kg": forms.NumberInput(attrs={"class": INPUT_CLASS, "placeholder": "Ex: 89.90", "step": "0.01"}),
        }

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("peso_inicial_g") or 0
        atual = cleaned.get("peso_atual_g") or 0
        if ini and atual and atual > ini:
            self.add_error("peso_atual_g", "O peso atual não pode ser maior que o peso inicial.")
        return cleaned
