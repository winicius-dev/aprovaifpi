import re

from django import template
from django.utils.html import escape, format_html
from django.template.defaultfilters import linebreaksbr
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def render_enunciado(questao):
    partes = re.split(r"(\[IMG\])", questao.enunciado or "")
    imagens = {
        imagem.ordem: imagem
        for imagem in questao.imagens.all()
    }

    chunks = []
    indice_imagem = 1

    for parte in partes:
        if parte != "[IMG]":
            chunks.append(linebreaksbr(escape(parte)))
            continue

        imagem = imagens.get(indice_imagem)
        indice_imagem += 1

        if (
            imagem
            and imagem.arquivo
            and imagem.arquivo.storage.exists(imagem.arquivo.name)
        ):
            chunks.append(
                format_html(
                    '<div class="questao-imagem">'
                    '<img src="{}" alt="Imagem da questão" loading="lazy">'
                    '</div>',
                    imagem.arquivo.url,
                )
            )

    return mark_safe("".join(chunks))


@register.simple_tag
def render_alternativa(alternativa):
    partes = re.split(r"(\[IMG\])", alternativa.texto or "")
    chunks = []
    encontrou_marcador = False

    for parte in partes:
        if parte != "[IMG]":
            chunks.append(linebreaksbr(escape(parte)))
            continue

        encontrou_marcador = True

        if (
            alternativa.imagem
            and alternativa.imagem.storage.exists(
                alternativa.imagem.name
            )
        ):
            chunks.append(
                format_html(
                    '<img src="{}" alt="Imagem da alternativa {}" '
                    'class="alternativa-imagem" loading="lazy">',
                    alternativa.imagem.url,
                    alternativa.letra,
                )
            )

    if not encontrou_marcador and alternativa.imagem:
        if alternativa.imagem.storage.exists(alternativa.imagem.name):
            chunks.append(
                format_html(
                    '<img src="{}" alt="Imagem da alternativa {}" '
                    'class="alternativa-imagem" loading="lazy">',
                    alternativa.imagem.url,
                    alternativa.letra,
                )
            )

    return mark_safe("".join(chunks))