# Filamenta

Sistema interno para gestão de clientes, pedidos e controle/consumo de filamentos (impressão 3D).

## Requisitos
- Python 3.11+ (recomendado)
- PostgreSQL

## Setup rápido

```bash
cd filamenta
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env  # Windows: Copy-Item .env.example .env
# edite o .env com suas credenciais

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse:
- App: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

## Variáveis de ambiente
Veja `.env.example`.

## Produção (checklist)
- `DJANGO_DEBUG=false`
- Definir `DJANGO_ALLOWED_HOSTS`
- Configurar `STATIC_ROOT` e rodar `collectstatic`
- Usar um servidor WSGI (ex.: gunicorn) e reverse proxy (ex.: nginx)
