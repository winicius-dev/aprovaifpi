from django.contrib import admin
from .models import (
    Escola,
    Perfil,
    Disciplina,
    Conteudo,
    Questao,
    ImagemQuestao,
    Alternativa,
    TentativaQuestao,
    Conquista,
    ConquistaPerfil,
)

admin.site.register(Escola)
admin.site.register(Perfil)
admin.site.register(Disciplina)
admin.site.register(Conteudo)
admin.site.register(Questao)
admin.site.register(ImagemQuestao)
admin.site.register(Alternativa)
admin.site.register(TentativaQuestao)
admin.site.register(Conquista)
admin.site.register(ConquistaPerfil)