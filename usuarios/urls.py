from django.urls import path
from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('inicio/', views.inicio, name='inicio_alias'),
    path('cadastro/', views.cadastro, name='cadastro'),
    path('login/', views.login, name='login'),
    path('recuperar-conta/', views.recuperar_conta, name='recuperar_conta'),
    path('perfil/', views.meu_perfil, name='perfil'),
    path('perfil/<int:perfil_id>/', views.perfil_publico, name='perfil_publico'),
    path('perfil/api/<int:perfil_id>/', views.perfil_api, name='perfil_api'),
    path('configuracoes/', views.configuracoes, name='configuracoes'),
    path('questoes/', views.questoes, name='questoes'),
    path('conteudos/', views.conteudos, name='conteudos'),
    path('ranking/', views.ranking, name='ranking'),
    path('sobre/', views.sobre, name='sobre'),
    path('logout/', views.logout_view, name='logout'),
    path('recuperaifpi/', views.recuperaifpi, name='recuperaifpi'),
    path('recuperaifpi/responder/', views.recuperaifpi_responder, name='recuperaifpi_responder'),
    path('recuperaifpi/api/conteudos/', views.recuperaifpi_conteudos_api, name='recuperaifpi_conteudos_api'),
    # Cronograma de Estudos
    path('recuperaifpi/cronograma/salvar/', views.recuperaifpi_cronograma_salvar, name='recuperaifpi_cronograma_salvar'),
    path('recuperaifpi/cronograma/limpar/', views.recuperaifpi_cronograma_limpar, name='recuperaifpi_cronograma_limpar'),
    # Agenda Acadêmica & Semanas de Provas
    path('recuperaifpi/agenda/eventos/', views.recuperaifpi_agenda_eventos_api, name='recuperaifpi_agenda_eventos_api'),
    path('recuperaifpi/agenda/evento/criar/', views.recuperaifpi_evento_criar, name='recuperaifpi_evento_criar'),
    path('recuperaifpi/agenda/evento/editar/', views.recuperaifpi_evento_editar, name='recuperaifpi_evento_editar'),
    path('recuperaifpi/agenda/evento/excluir/', views.recuperaifpi_evento_excluir, name='recuperaifpi_evento_excluir'),
    path('recuperaifpi/agenda/evento/concluir/', views.recuperaifpi_evento_concluir, name='recuperaifpi_evento_concluir'),
    path('recuperaifpi/agenda/semana/criar/', views.recuperaifpi_semana_criar, name='recuperaifpi_semana_criar'),
    path('recuperaifpi/agenda/semana/excluir/', views.recuperaifpi_semana_excluir, name='recuperaifpi_semana_excluir'),
    path('recuperaifpi/agenda/avaliacao/criar/', views.recuperaifpi_avaliacao_criar, name='recuperaifpi_avaliacao_criar'),
    path('recuperaifpi/agenda/avaliacao/editar/', views.recuperaifpi_avaliacao_editar, name='recuperaifpi_avaliacao_editar'),
    path('recuperaifpi/agenda/avaliacao/excluir/', views.recuperaifpi_avaliacao_excluir, name='recuperaifpi_avaliacao_excluir'),
    path('api/tema/alternar/', views.alternar_tema_api, name='alternar_tema_api'),
]
