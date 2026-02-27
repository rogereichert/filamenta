from decimal import Decimal
from io import BytesIO
import ssl
from django.core.mail import EmailMessage, get_connection
from django.conf import settings
from pathlib import Path
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.clientes.models import Cliente
from .models import Pedido, PedidoItem, PedidoItemFilamento
from .forms import PedidoForm, PedidoItemForm, PedidoItemFilamentoForm, PedidoCalculoForm, PedidoItemCalculoAddForm
# PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
def _to_decimal(v) -> Decimal:
    """
    Converte entrada BR/EN para Decimal.
    Aceita: 5,50 | 5.50 | 5 | "" | None
    """
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    s = str(v).strip()
    if not s:
        return Decimal("0")
    # suporte BR: "1.234,56" -> "1234.56"
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")
def _recalc_pedido_total(pedido: Pedido) -> None:
    """
    Recalcula e salva pedido.valor_total com base em:
    soma(itens.subtotal) - desconto + frete + taxa_extra
    """
    itens_total = Decimal("0")
    for it in pedido.itens.all():
        itens_total += (it.subtotal or Decimal("0"))

    desconto = _to_decimal(pedido.desconto)
    frete = _to_decimal(pedido.frete)
    taxa = _to_decimal(pedido.taxa_extra)

    total = (itens_total - desconto + frete + taxa)
    if total < 0:
        total = Decimal("0")

    pedido.valor_total = total
    pedido.save(update_fields=["valor_total"])
def _calc_orcamento(
    *,
    gramas: Decimal,
    desperdicio_pct: Decimal,
    tempo_horas: Decimal,
    preco_kg: Decimal,
    custo_hora: Decimal,
    energia: Decimal,
) -> dict:
    """Mesma lógica do menu 'Calcular Pedido'.

    Retorna valores já quantizados (2 casas) para dinheiro e com campos úteis.
    """
    fator = (Decimal("1") + (desperdicio_pct / Decimal("100")))
    gramas_cobradas = (gramas * fator)

    custo_material = (gramas_cobradas * (preco_kg / Decimal("1000")))
    custo_maquina = (tempo_horas * custo_hora)
    custo_total = (custo_material + custo_maquina + energia)

    preco_25 = (custo_total * Decimal("2.5"))
    preco_3 = (custo_total * Decimal("3"))

    q = Decimal("0.01")
    return {
        "gramas": gramas,
        "gramas_cobradas": gramas_cobradas,
        "tempo_horas": tempo_horas,
        "preco_kg": preco_kg,
        "custo_material": custo_material.quantize(q),
        "custo_maquina": custo_maquina.quantize(q),
        "custo_energia": energia.quantize(q),
        "custo_total": custo_total.quantize(q),
        "preco_25": preco_25.quantize(q),
        "preco_3": preco_3.quantize(q),
    }
def pedido_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    page_number = request.GET.get("page") or 1

    qs = Pedido.objects.select_related("cliente").all()

    if q:
        qs = qs.filter(
            Q(cliente__nome__icontains=q) |
            Q(id__icontains=q) |
            Q(titulo__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 7)
    page_obj = paginator.get_page(page_number)

    return render(request, "pedidos/list.html", {
        "pedidos": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "total": qs.count(),
        "status_choices": Pedido.Status.choices,
    })
def pedido_create(request):
    cliente_id = (request.GET.get("cliente") or "").strip()
    cliente_initial = None
    if cliente_id.isdigit():
        cliente_initial = get_object_or_404(Cliente, pk=int(cliente_id))

    if request.method == "POST":
        form = PedidoForm(request.POST)
        if form.is_valid():
            pedido = form.save()
            _recalc_pedido_total(pedido)
            # ✅ se criou já como ENTREGUE (raro), baixa estoque
            pedido.baixar_estoque_se_necessario()

            messages.success(request, "Pedido criado com sucesso.")
            return redirect("pedidos:detail", pk=pedido.pk)
    else:
        form = PedidoForm(initial={"cliente": cliente_initial} if cliente_initial else None)

    return render(request, "pedidos/form.html", {
        "form": form,
        "modo": "novo",
    })
def pedido_update(request, pk):
    """
    (FALLBACK) Você pode manter essa tela, mas com a Opção A
    você vai praticamente usar só o /pedidos/<id>/ (detail/OS).
    """
    pedido = get_object_or_404(Pedido, pk=pk)

    ItensFormSet = inlineformset_factory(
        parent_model=Pedido,
        model=PedidoItem,
        form=PedidoItemForm,
        extra=1,
        can_delete=True,
        fields=("descricao", "quantidade", "preco_unitario"),
    )

    if request.method == "POST":
        form = PedidoForm(request.POST, instance=pedido)
        itens_formset = ItensFormSet(request.POST, instance=pedido)

        if form.is_valid() and itens_formset.is_valid():
            pedido = form.save()
            itens_formset.save()

            # ✅ baixa estoque se virou ENTREGUE
            pedido.baixar_estoque_se_necessario()

            _recalc_pedido_total(pedido)

            messages.success(request, "Pedido atualizado com sucesso.")
            return redirect("pedidos:detail", pk=pedido.pk)

        messages.error(request, "Revise os campos do pedido e dos itens.")
    else:
        form = PedidoForm(instance=pedido)
        itens_formset = ItensFormSet(instance=pedido)

    return render(request, "pedidos/form.html", {
        "form": form,
        "modo": "editar",
        "pedido": pedido,
        "itens_formset": itens_formset,
    })
def pedido_detail(request, pk):
    """
    ✅ Tela principal (OS). Aqui fica:
    - visualizar pedido
    - adicionar/remover itens
    - adicionar/remover consumos
    - gerar PDF
    - editar cabeçalho via MODAL (sem sair da tela)
    """
    pedido = get_object_or_404(Pedido.objects.select_related("cliente"), pk=pk)

    form_item = PedidoItemForm()
    form_item_filamento = PedidoItemFilamentoForm()
    form_header = PedidoForm(instance=pedido)
    form_item_calc = PedidoItemCalculoAddForm()

    # ✅ POST do modal: atualizar cabeçalho
    if request.method == "POST" and (request.POST.get("acao") == "update_header"):
        form_header = PedidoForm(request.POST, instance=pedido)

        if form_header.is_valid():
            pedido = form_header.save()

            # ✅ baixa estoque se virou ENTREGUE
            pedido.baixar_estoque_se_necessario()

            _recalc_pedido_total(pedido)
            messages.success(request, "Cabeçalho do pedido atualizado com sucesso.")
            return redirect("pedidos:detail", pk=pedido.pk)

        messages.error(request, "Revise os campos do pedido (cabeçalho).")

    itens = (
        pedido.itens
        .prefetch_related("filamentos__filamento")
        .order_by("id")
    )

    total_gramas = (
        PedidoItemFilamento.objects
        .filter(item__pedido=pedido)
        .aggregate(total=Sum("gramas_g"))
    )["total"] or 0

    return render(request, "pedidos/detail.html", {
        "pedido": pedido,
        "itens": itens,
        "total_gramas": total_gramas,
        "form_item": form_item,
        "form_item_filamento": form_item_filamento,
        "form_header": form_header,
        "form_item_calc": form_item_calc,
    })
def pedido_item_add_calculado(request, pk):
    """Adiciona um item ao pedido usando o mesmo cálculo do menu Calcular Pedido.

    Isso resolve a inconsistência: ao criar um pedido e adicionar itens, você
    não precisa calcular manualmente o preço unitário.
    """
    pedido = get_object_or_404(Pedido, pk=pk)
    if request.method != "POST":
        return redirect("pedidos:detail", pk=pedido.pk)

    form = PedidoItemCalculoAddForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revise os campos do cálculo (item calculado).")
        return redirect("pedidos:detail", pk=pedido.pk)

    cd = form.cleaned_data
    filamento = cd.get("filamento")
    preco_kg = cd["preco_kg"]
    if filamento and getattr(filamento, "preco_kg", None):
        preco_kg = filamento.preco_kg

    resultado = _calc_orcamento(
        gramas=cd["gramas_total"],
        desperdicio_pct=cd.get("desperdicio_pct") or Decimal("0"),
        tempo_horas=cd["tempo_total"],
        preco_kg=preco_kg,
        custo_hora=cd["custo_hora_maquina"],
        energia=cd["energia_fixa"],
    )

    multiplicador = cd.get("multiplicador")
    if multiplicador == "3":
        preco_unitario = resultado["preco_3"]
    elif multiplicador == "manual":
        preco_manual = cd.get("preco_venda_manual")
        if not preco_manual or preco_manual <= 0:
            messages.error(request, "Informe um preço manual válido (maior que 0).")
            return redirect("pedidos:detail", pk=pedido.pk)
        preco_unitario = _to_decimal(preco_manual)
    else:
        preco_unitario = resultado["preco_25"]

    # cria item
    item = PedidoItem.objects.create(
        pedido=pedido,
        descricao=cd["descricao"].strip(),
        quantidade=cd["quantidade"],
        preco_unitario=preco_unitario,
    )

    # registra consumo total (por item) se filamento foi selecionado
    if filamento:
        from decimal import ROUND_HALF_UP
        gramas_total = (resultado["gramas_cobradas"] * Decimal(cd["quantidade"]))
        gramas_int = int(gramas_total.to_integral_value(rounding=ROUND_HALF_UP))
        if gramas_int < 1:
            gramas_int = 1
        PedidoItemFilamento.objects.create(
            item=item,
            filamento=filamento,
            gramas_g=gramas_int,
        )

    # log leve no pedido (útil p/ auditoria)
    log = (
        f"[CALC] {item.descricao} | g={resultado['gramas']:.2f} | "
        f"h={resultado['tempo_horas']:.2f} | kg={resultado['preco_kg']:.2f} | "
        f"mat={resultado['custo_material']:.2f} maq={resultado['custo_maquina']:.2f} "
        f"ene={resultado['custo_energia']:.2f} total={resultado['custo_total']:.2f} | "
        f"unit={_to_decimal(preco_unitario):.2f}\n"
    )
    pedido.observacoes = (pedido.observacoes or "") + log
    pedido.save(update_fields=["observacoes"])

    messages.success(
        request,
        f"Item calculado adicionado. Custo: R$ {resultado['custo_total']:.2f} | "
        f"Preço unit.: R$ {_to_decimal(preco_unitario):.2f}"
    )
    return redirect("pedidos:detail", pk=pedido.pk)
def pedido_item_add(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    form = PedidoItemForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.pedido = pedido
        item.save()
        _recalc_pedido_total(pedido)
        messages.success(request, "Item adicionado ao pedido.")
    else:
        messages.error(request, "Verifique os campos do item (descrição, quantidade e preço).")

    return redirect("pedidos:detail", pk=pedido.pk)
def pedido_item_remove(request, pk, item_id):
    pedido = get_object_or_404(Pedido, pk=pk)
    item = get_object_or_404(PedidoItem, pk=item_id, pedido=pedido)
    item.delete()
    _recalc_pedido_total(pedido)
    messages.success(request, "Item removido.")
    return redirect("pedidos:detail", pk=pedido.pk)
def item_filamento_add(request, pk, item_id):
    pedido = get_object_or_404(Pedido, pk=pk)
    item = get_object_or_404(PedidoItem, pk=item_id, pedido=pedido)

    form = PedidoItemFilamentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        itf = form.save(commit=False)
        itf.item = item
        itf.save()
        messages.success(request, "Consumo de filamento adicionado ao item.")
    else:
        messages.error(request, "Verifique o filamento e as gramas informadas.")

    return redirect("pedidos:detail", pk=pedido.pk)
def item_filamento_remove(request, pk, item_id, if_id):
    pedido = get_object_or_404(Pedido, pk=pk)
    item = get_object_or_404(PedidoItem, pk=item_id, pedido=pedido)
    itf = get_object_or_404(PedidoItemFilamento, pk=if_id, item=item)
    itf.delete()
    messages.success(request, "Consumo de filamento removido do item.")
    return redirect("pedidos:detail", pk=pedido.pk)
def pedido_delete(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)

    if request.method == "POST":
        pedido.delete()
        messages.success(request, "Pedido excluído.")
        return redirect("pedidos:list")

    return render(request, "pedidos/confirm_delete.html", {"pedido": pedido})
def gerar_pedido_pdf_bytes(pedido: Pedido) -> bytes:
    """Gera a Ordem de Serviço (PDF) do pedido com layout mais 'premium'.

    - Cabeçalho com logo e box
    - Tabelas em largura total (doc.width)
    - Destaque para o Total
    - Rodapé com data/hora e paginação
    """
    from datetime import datetime
    import os
    from django.conf import settings
    from reportlab.lib.styles import ParagraphStyle


    itens = list(pedido.itens.all().order_by("id"))

    consumos = (
        PedidoItemFilamento.objects
        .filter(item__pedido=pedido)
        .select_related("item", "filamento")
        .order_by("item_id", "id")
    )

    total_gramas = (
        PedidoItemFilamento.objects
        .filter(item__pedido=pedido)
        .aggregate(total=Sum("gramas_g"))
    )["total"] or 0

    buffer = BytesIO()
    generated_at = datetime.now()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,  # um pouco maior por conta do rodapé
        title=f"Pedido #{pedido.id} - OS",
    )
    avail_w = doc.width

    styles = getSampleStyleSheet()

    # ---------- Tipografia ----------
    Title = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=0,
    )

    SubTitle = ParagraphStyle(
        "SubTitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
        spaceAfter=0,
    )

    H2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=6,
    )

    Normal = ParagraphStyle(
        "Normal",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # ---------- Header (logo + box) ----------
    logo_path = os.path.join(settings.BASE_DIR, "static", "img", "logo.png")
    logo = None
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=20 * mm, height=20 * mm)
        logo.hAlign = "LEFT"

    header_right = [
        Paragraph(f"Pedido #{pedido.id}", Title),
        Paragraph("Ordem de serviço (itens, consumo e resumo)", SubTitle),
    ]
    header_row = [[logo if logo else "", header_right]]
    header = Table(header_row, colWidths=[24 * mm, avail_w - (24 * mm)], hAlign="LEFT")
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header)
    story.append(Spacer(1, 10))

    # ---------- Meta (box leve) ----------
    meta = [
        ["Cliente", pedido.cliente.nome, "Status", pedido.get_status_display()],
        ["Telefone", pedido.cliente.telefone or "-", "Criado em", pedido.created_at.strftime("%d/%m/%Y %H:%M")],
        ["Título", pedido.titulo or "-", "Atualizado", pedido.updated_at.strftime("%d/%m/%Y %H:%M")],
    ]

    w_label = avail_w * 0.12
    w_value = avail_w * 0.38
    meta_table = Table(meta, colWidths=[w_label, w_value, w_label, w_value], hAlign="LEFT")
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748B")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#64748B")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_table)

    # Separador fino
    sep = Table([[""]], colWidths=[avail_w], hAlign="LEFT")
    sep.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sep)

    # ---------- Itens ----------
    story.append(Paragraph("Itens do pedido", H2))

    data_itens = [["Descrição", "Qtd", "Preço (R$)", "Subtotal (R$)"]]
    for it in itens:
        data_itens.append([
            it.descricao,
            str(it.quantidade),
            f"{(it.preco_unitario or 0):.2f}".replace(".", ","),
            f"{(it.subtotal or 0):.2f}".replace(".", ","),
        ])

    w_desc = avail_w * 0.58
    w_qtd = avail_w * 0.10
    w_preco = avail_w * 0.16
    w_sub = avail_w * 0.16

    table_itens = Table(data_itens, colWidths=[w_desc, w_qtd, w_preco, w_sub], hAlign="LEFT")
    table_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(table_itens)

    # ---------- Consumo ----------
    story.append(Paragraph("Consumo de filamento (por item)", H2))

    data_consumo = [["Item", "Filamento", "Cor", "g"]]
    for c in consumos:
        data_consumo.append([
            c.item.descricao,
            c.filamento.nome,
            c.filamento.cor or "-",
            str(c.gramas_g or 0),
        ])

    w_item = avail_w * 0.32
    w_fil = avail_w * 0.46
    w_cor = avail_w * 0.16
    w_g = avail_w * 0.06

    table_consumo = Table(data_consumo, colWidths=[w_item, w_fil, w_cor, w_g], hAlign="LEFT")
    table_consumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(table_consumo)

    # ---------- Resumo ----------
    story.append(Paragraph("Resumo", H2))

    itens_total = sum([(it.subtotal or Decimal("0")) for it in itens], Decimal("0"))
    desconto = _to_decimal(pedido.desconto)
    frete = _to_decimal(pedido.frete)
    taxa = _to_decimal(pedido.taxa_extra)
    total = _to_decimal(pedido.valor_total)

    resumo = [
        ["Itens (R$)", f"{itens_total:.2f}".replace(".", ",")],
        ["Desconto (R$)", f"{desconto:.2f}".replace(".", ",")],
        ["Frete (R$)", f"{frete:.2f}".replace(".", ",")],
        ["Taxa extra (R$)", f"{taxa:.2f}".replace(".", ",")],
        ["Total (R$)", f"{total:.2f}".replace(".", ",")],
        ["Consumo total (g)", str(total_gramas)],
    ]

    w_left = avail_w * 0.65
    w_right = avail_w * 0.35

    t2 = Table(resumo, colWidths=[w_left, w_right], hAlign="LEFT")
    t2.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        # destaque do total
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#EEF2FF")),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("FONTSIZE", (0, 4), (-1, 4), 10),
        ("LINEABOVE", (0, 4), (-1, 4), 1.0, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t2)

    # ---------- Observações ----------
    if pedido.observacoes:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Observações", H2))
        obs_box = Table([[Paragraph(pedido.observacoes.replace("\n", "<br/>"), Normal)]], colWidths=[avail_w], hAlign="LEFT")
        obs_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(obs_box)

    # ---------- Footer ----------
    def _footer(canvas, _doc):
        canvas.saveState()
        page_num = canvas.getPageNumber()

        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        canvas.setLineWidth(0.75)
        canvas.line(doc.leftMargin, 14 * mm, doc.leftMargin + avail_w, 14 * mm)

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        left_txt = f"Filamenta • Pedido #{pedido.id}"
        right_txt = f"Gerado em {generated_at.strftime('%d/%m/%Y %H:%M')} • Página {page_num}"
        canvas.drawString(doc.leftMargin, 9 * mm, left_txt)
        canvas.drawRightString(doc.leftMargin + avail_w, 9 * mm, right_txt)

        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf


def _pedido_pdf_cache_path(pedido: Pedido) -> Path:
    """Caminho do PDF cacheado.

    Inclui `updated_at` como chave do cache, então qualquer alteração no pedido
    invalida automaticamente o PDF anterior.
    """
    ts = (pedido.updated_at or pedido.created_at).strftime("%Y%m%d%H%M%S")
    return Path(settings.MEDIA_ROOT) / "pdf_cache" / f"pedido_{pedido.id}_{ts}.pdf"


def get_pedido_pdf_cached(pedido: Pedido) -> bytes:
    """Retorna o PDF do pedido usando cache em disco (MEDIA_ROOT/pdf_cache)."""
    cache_path = _pedido_pdf_cache_path(pedido)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        return cache_path.read_bytes()

    pdf_bytes = gerar_pedido_pdf_bytes(pedido)
    cache_path.write_bytes(pdf_bytes)

    # Limpa PDFs antigos do mesmo pedido (não acumula lixo)
    try:
        for old in cache_path.parent.glob(f"pedido_{pedido.id}_*.pdf"):
            if old.name != cache_path.name:
                old.unlink(missing_ok=True)
    except Exception:
        pass

    return pdf_bytes


def pedido_pdf(request, pk):
    """Gera a Ordem de Serviço (PDF) do pedido."""
    pedido = get_object_or_404(
        Pedido.objects.select_related("cliente").prefetch_related("itens"),
        pk=pk,
    )
    pdf = get_pedido_pdf_cached(pedido)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="pedido_{pedido.id}_os.pdf"'
    response.write(pdf)
    return response


def pedido_enviar_email(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related("cliente").prefetch_related("itens"),
        pk=pk,
    )

    if request.method == "POST":
        pdf_bytes = get_pedido_pdf_cached(pedido)

        email = EmailMessage(
            subject=f"Pedido #{pedido.id} - Filamenta",
            body=f"Segue em anexo o PDF do pedido #{pedido.id}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.PEDIDO_DESTINO_EMAIL],
        )

        email.attach(
            f"pedido_{pedido.id}.pdf",
            pdf_bytes,
            "application/pdf"
        )

        try:
            email.send(fail_silently=False)

        except ssl.SSLCertVerificationError:
            # fallback sem verificação SSL (apenas dev/local)
            connection = get_connection()
            connection.ssl_context = ssl._create_unverified_context()
            email.connection = connection
            email.send(fail_silently=False)

        messages.success(request, "Pedido enviado por e-mail com sucesso.")
        return redirect("pedidos:detail", pk=pedido.pk)

    return redirect("pedidos:detail", pk=pedido.pk)



def pedido_calcular(request):
    """
    Tela simples para calcular custo (material + energia + máquina) a partir de:
    - gramas (do slicer)
    - tempo total (do slicer)
    """
    resultado = None

    if request.method == "POST":
        form = PedidoCalculoForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            filamento = cd.get("filamento")
            preco_kg = cd["preco_kg"]
            if filamento and filamento.preco_kg:
                preco_kg = filamento.preco_kg

            desperdicio_pct = cd.get("desperdicio_pct") or Decimal("0")
            gramas = cd["gramas_total"]
            tempo_horas = cd["tempo_total"]
            custo_hora = cd["custo_hora_maquina"]
            energia_fixa = cd["energia_fixa"]

            resultado = _calc_orcamento(
                gramas=gramas,
                desperdicio_pct=desperdicio_pct,
                tempo_horas=tempo_horas,
                preco_kg=preco_kg,
                custo_hora=custo_hora,
                energia=energia_fixa,
            )

            preco_25 = resultado["preco_25"]
            preco_3 = resultado["preco_3"]

            # --- Ação: transformar em Orçamento/Pedido ---
            acao = (request.POST.get("acao") or "").strip()
            if acao in {"criar_25", "criar_3", "criar_manual"}:
                from decimal import ROUND_HALF_UP
                from django.db import transaction

                cliente = cd.get("cliente")
                if not cliente:
                    messages.error(request, "Selecione um cliente para criar o orçamento.")
                    return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})

                titulo = (cd.get("titulo") or "").strip()
                item_descricao = (cd.get("item_descricao") or "").strip()
                if not item_descricao:
                    messages.error(request, "Informe a descrição do item para criar o orçamento.")
                    return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})

                quantidade = cd.get("quantidade") or 1

                if acao == "criar_25":
                    preco_venda = preco_25
                elif acao == "criar_3":
                    preco_venda = preco_3
                else:
                    preco_manual = cd.get("preco_venda_manual")
                    if not preco_manual or preco_manual <= 0:
                        messages.error(request, "Informe um preço manual válido para salvar o orçamento.")
                        return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})
                    preco_venda = _to_decimal(preco_manual)

                # quantiza para 2 casas
                preco_venda_q = _to_decimal(preco_venda).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                # Para consumo, guarda gramas inteiras (do total cobrado * quantidade)
                gramas_total_consumo = _to_decimal(resultado["gramas_cobradas"]) * Decimal(int(quantidade))
                gramas_int = int(gramas_total_consumo.to_integral_value(rounding=ROUND_HALF_UP))
                if gramas_int < 1:
                    gramas_int = 1

                # Observações (SEM variáveis soltas)
                obs = (
                    "Cálculo (slicer):\n"
                    f"- Gramas (total): {_to_decimal(gramas).quantize(Decimal('0.01'))} g\n"
                    f"- Desperdício: {_to_decimal(desperdicio_pct).quantize(Decimal('0.01'))}%\n"
                    f"- Gramas cobradas: {_to_decimal(resultado['gramas_cobradas']).quantize(Decimal('0.01'))} g\n"
                    f"- Tempo: {_to_decimal(tempo_horas).quantize(Decimal('0.01'))} h\n"
                    f"- Filamento: R$ {_to_decimal(preco_kg).quantize(Decimal('0.01'))}/kg\n"
                    f"- Máquina: R$ {_to_decimal(custo_hora).quantize(Decimal('0.01'))}/h\n"
                    f"- Energia: R$ {_to_decimal(energia_fixa).quantize(Decimal('0.01'))}\n"
                    f"- Material: R$ {_to_decimal(resultado['custo_material']).quantize(Decimal('0.01'))}\n"
                    f"- Máquina: R$ {_to_decimal(resultado['custo_maquina']).quantize(Decimal('0.01'))}\n"
                    f"- Total custo: R$ {_to_decimal(resultado['custo_total']).quantize(Decimal('0.01'))}\n"
                    f"- Preço 2,5x: R$ {_to_decimal(resultado['preco_25']).quantize(Decimal('0.01'))}\n"
                    f"- Preço 3x: R$ {_to_decimal(resultado['preco_3']).quantize(Decimal('0.01'))}\n"
                )

                with transaction.atomic():
                    pedido = Pedido.objects.create(
                        cliente=cliente,
                        status=Pedido.Status.ORCAMENTO,
                        titulo=titulo or item_descricao,
                        observacoes=obs,
                    )

                    item = PedidoItem.objects.create(
                        pedido=pedido,
                        descricao=item_descricao,
                        quantidade=quantidade,
                        preco_unitario=preco_venda_q,
                    )

                    if filamento and gramas_int > 0:
                        PedidoItemFilamento.objects.create(
                            item=item,
                            filamento=filamento,
                            gramas_g=gramas_int,
                        )

                    # ✅ recalcula total do pedido do jeito que seu projeto já faz
                    _recalc_pedido_total(pedido)

                messages.success(request, "Orçamento criado! Você já pode ver na lista de pedidos.")
                return redirect("pedidos:detail", pk=pedido.pk)
    else:
        form = PedidoCalculoForm(initial={
            "quantidade": 1,
            "preco_kg": Decimal("120.00"),
            "custo_hora_maquina": Decimal("1.30"),
            "energia_fixa": Decimal("0.60"),
            "desperdicio_pct": Decimal("0.00"),
        })

    return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})
