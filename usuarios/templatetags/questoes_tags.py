import re

from django import template
from django.utils.html import escape, format_html
from django.template.defaultfilters import linebreaksbr

register = template.Library()


@register.simple_tag
def render_enunciado(questao):
    partes = re.split(r"(\[IMG\])", questao.enunciado or "")
    imagens = {
        imagem.ordem: imagem
        for imagem in questao.imagens.all()
    }

    resultado = format_html("")
    indice_imagem = 1

    for parte in partes:
        if parte != "[IMG]":
            resultado = format_html(
                "{}{}", resultado, linebreaksbr(escape(parte))
            )
            continue

        imagem = imagens.get(indice_imagem)
        indice_imagem += 1

        if (
            imagem
            and imagem.arquivo
            and imagem.arquivo.storage.exists(imagem.arquivo.name)
        ):
            elemento = format_html(
                '<div class="questao-imagem">'
                '<img src="{}" alt="Imagem da questão" loading="lazy">'
                '</div>',
                imagem.arquivo.url,
            )
            resultado = format_html("{}{}", resultado, elemento)

    return resultado


@register.simple_tag
def render_alternativa(alternativa):
    partes = re.split(r"(\[IMG\])", alternativa.texto or "")
    resultado = format_html("")
    encontrou_marcador = False

    for parte in partes:
        if parte != "[IMG]":
            resultado = format_html(
                "{}{}", resultado, linebreaksbr(escape(parte))
            )
            continue

        encontrou_marcador = True

        if (
            alternativa.imagem
            and alternativa.imagem.storage.exists(
                alternativa.imagem.name
            )
        ):
            elemento = format_html(
                '<img src="{}" alt="Imagem da alternativa {}" '
                'class="alternativa-imagem" loading="lazy">',
                alternativa.imagem.url,
                alternativa.letra,
            )
            resultado = format_html("{}{}", resultado, elemento)

    if not encontrou_marcador and alternativa.imagem:
        if alternativa.imagem.storage.exists(alternativa.imagem.name):
            elemento = format_html(
                '<img src="{}" alt="Imagem da alternativa {}" '
                'class="alternativa-imagem" loading="lazy">',
                alternativa.imagem.url,
                alternativa.letra,
            )
            resultado = format_html("{}{}", resultado, elemento)

    return resultado