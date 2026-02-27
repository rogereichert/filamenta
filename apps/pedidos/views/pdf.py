from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Pedido


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

