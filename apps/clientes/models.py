from django.db import models

# Criar o Model Cliente (a “tabela” no banco)

class Cliente(models.Model):
    nome = models.CharField(max_length=120)
    telefone = models.CharField(max_length=30, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome