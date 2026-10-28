from django.urls import path
from . import views

urlpatterns = [
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
]