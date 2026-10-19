from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as login_django, logout
from django.contrib.auth.decorators import login_required
from .models import (
    Perfil,
    Escola,
    Questao,
    Alternativa,
    TentativaQuestao,
    Disciplina,
    Conteudo
)
from urllib.parse import urlencode
from django.core.paginator import Paginator

def cadastro(request):
    escolas = Escola.objects.all().order_by("nome")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        email = request.POST.get("email", "").strip()
        escola_id = request.POST.get("escola", "").strip()
        senha = request.POST.get("senha", "")
        confirmar_senha = request.POST.get("confirmar_senha", "")

        context = {
            "escolas": escolas,
            "nome": nome,
            "email": email,
            "escola_id": escola_id,
        }

        if len(nome.split()) < 2:
            messages.error(request, "Você deve inserir seu nome completo")
            return render(request, "cadastro.html", context)

        if User.objects.filter(email=email).exists():
            messages.error(request, "Esse email ja está cadastrado")
            return render(request, "cadastro.html", context)

        if len(senha) < 8:
            messages.error(request, "A senha deve ter pelo menos 8 caracteres")
            return render(request, "cadastro.html", context)

        if senha != confirmar_senha:
            messages.error(request, "Os campos devem ter a mesma senha")
            return render(request, "cadastro.html", context)

        if not escola_id:
            messages.error(request, "Selecione uma escola")
            return render(request, "cadastro.html", context)

        try:
            escola = Escola.objects.get(id=escola_id)
        except (Escola.DoesNotExist, ValueError):
            messages.error(request, "Escola selecionada é inválida")
            return render(request, "cadastro.html", context)

        user = User.objects.create_user(username=email, email=email, password=senha)
        Perfil.objects.create(usuario=user, nome=nome, escola=escola)

        messages.success(request, "Cadastro realizado com sucesso! Faça login para continuar.")
        return redirect("login")

    return render(request, "cadastro.html", {"escolas": escolas})

def login(request):

    if request.method == "POST":
        email = request.POST.get("email")
        senha = request.POST.get("senha")

        user = authenticate(request, username=email, password=senha)

        print("USUÁRIO:", user)

        if user is not None:
            login_django(request, user)
            print("LOGIN REALIZADO")
            return redirect("questoes")
        
        messages.error(request, "E-mail ou senha incorretos")
    return render(request, "login.html")


def calcular_taxa_acerto(questao):
    primeiras_tentativas = TentativaQuestao.objects.filter(questao=questao, numero_tentativa=1)
    total = primeiras_tentativas.values("perfil").distinct().count()

    if total == 0:
        return 0

    acertos = primeiras_tentativas.filter(acertou=True).values("perfil").distinct().count()

    return round(acertos / total * 100, 1)

@login_required
def questoes(request):
    perfil = Perfil.objects.get(usuario=request.user)
    resultado_questao = request.session.pop("resultado_questao", None)
    parametros = request.POST if request.method == "POST" else request.GET
    filtro = parametros.get("filtro", "todas")
    disciplina_geral = parametros.get("disciplina", "")
    disciplina1 = parametros.get("disciplina1", "")
    disciplina2 = parametros.get("disciplina2", "")
    disciplina3 = parametros.get("disciplina3", "")
    conteudo1 = parametros.get("conteudo1", "")
    conteudo2 = parametros.get("conteudo2", "")
    conteudo3 = parametros.get("conteudo3", "")
    ano = parametros.get("ano", "")
    dificuldade = parametros.get("dificuldade", "")

    questoes_acertadas = Questao.objects.filter(tentativaquestao__perfil=perfil, tentativaquestao__acertou=True).distinct()
    questoes_respondidas = Questao.objects.filter(tentativaquestao__perfil=perfil).distinct()
    questoes_nao_respondidas = Questao.objects.exclude(id__in=questoes_respondidas.values("id"))
    questoes_erradas = questoes_respondidas.exclude(id__in=questoes_acertadas.values("id"))
    questoes = Questao.objects.all().order_by("id")

    if filtro == "acertadas":
        questoes = questoes_acertadas
    elif filtro == "erradas":
        questoes = questoes_erradas
    elif filtro == "nao_respondidas":
        questoes = questoes_nao_respondidas

    if disciplina_geral:
        questoes = questoes.filter(conteudo__disciplina_id=disciplina_geral)

    from django.db.models import Q

    filtros_disciplina = Q()

    for disciplina_atual, conteudo_atual in [
        (disciplina1, conteudo1),
        (disciplina2, conteudo2),
        (disciplina3, conteudo3)
    ]:
        if disciplina_atual and conteudo_atual:
            filtros_disciplina |= Q(conteudo_id=conteudo_atual, conteudo__disciplina_id=disciplina_atual)

        elif disciplina_atual:
            filtros_disciplina |= Q(conteudo__disciplina_id=disciplina_atual)

        elif conteudo_atual:
            filtros_disciplina |= Q(conteudo_id=conteudo_atual)

    if filtros_disciplina:
        questoes = questoes.filter(filtros_disciplina)

    if ano:
        questoes = questoes.filter(ano=ano)

    if dificuldade:
        questoes = questoes.filter(dificuldade=dificuldade)

    total_questoes = questoes.count()
    disciplinas = Disciplina.objects.all().order_by("nome")
    conteudos = Conteudo.objects.select_related("disciplina").order_by("disciplina__nome", "nome")
    anos = Questao.objects.values_list("ano", flat=True).distinct().order_by("-ano")
    dificuldades = Questao.objects.values_list("dificuldade", flat=True).distinct().order_by("dificuldade")

    if request.method == "POST":
        alternativa_id = request.POST.get("alternativa")
        questao_id = request.POST.get("questao_id")

        if questao_id:
            alternativa = Alternativa.objects.get(id=alternativa_id, questao_id=questao_id)
        else:
            alternativa = Alternativa.objects.get(id=alternativa_id)

        questao = alternativa.questao
        tentativas = TentativaQuestao.objects.filter(perfil=perfil, questao=questao).count()

        numero_tentativa = tentativas + 1
        xp_ganho = 0

        if alternativa.e_correta and numero_tentativa == 1:
            if questao.dificuldade == "Fácil":
                xp_ganho = 1
            elif questao.dificuldade == "Médio":
                xp_ganho = 2
            elif questao.dificuldade == "Difícil":
                xp_ganho = 3

        perfil.xp += xp_ganho
        perfil.save()

        TentativaQuestao.objects.create(xp_ganho=xp_ganho, acertou=alternativa.e_correta, numero_tentativa=numero_tentativa, perfil=perfil, questao=questao, alternativa=alternativa)

        alternativa_correta = Alternativa.objects.get(questao=questao, e_correta=True)
        taxa_acerto = calcular_taxa_acerto(questao)
        circunferencia_offset = 301.59 * (1 - max(0, min(100, taxa_acerto)) / 100)

        request.session["resultado_questao"] = {
            "questao_id": questao.id,
            "alternativa_escolhida_id": alternativa.id,
            "acertou": alternativa.e_correta,
            "gabarito": alternativa_correta.letra,
            "gabarito_id": alternativa_correta.id,
            "xp_ganho": xp_ganho,
            "numero_tentativa": numero_tentativa,
            "taxa_acerto": taxa_acerto,
            "circunferencia_offset": circunferencia_offset,
            "explicacao": "A pontuação empregada liga duas orações coordenadas, marcando uma pausa expressiva e relação lógica entre as proposições."
        }

        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.POST.get("ajax") == "1"

        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({
                "sucesso": True,
                "questao_id": questao.id,
                "alternativa_escolhida_id": alternativa.id,
                "acertou": alternativa.e_correta,
                "gabarito": alternativa_correta.letra,
                "gabarito_id": alternativa_correta.id,
                "xp_ganho": xp_ganho,
                "numero_tentativa": numero_tentativa,
                "total_xp": perfil.xp,
                "taxa_acerto": taxa_acerto,
                "circunferencia_offset": circunferencia_offset,
                "explicacao": "A pontuação empregada liga duas orações coordenadas, marcando uma pausa expressiva e relação lógica entre as proposições."
            }, json_dumps_params={"ensure_ascii": False})

        parametros_url = (
            f"filtro={filtro}"
            f"&disciplina={disciplina_geral}"
            f"&disciplina1={disciplina1}"
            f"&disciplina2={disciplina2}"
            f"&disciplina3={disciplina3}"
            f"&conteudo1={conteudo1}"
            f"&conteudo2={conteudo2}"
            f"&conteudo3={conteudo3}"
            f"&ano={ano}"
            f"&dificuldade={dificuldade}"
        )

        return redirect(f"/auth/questoes/?{parametros_url}")

    parametros_paginacao = request.GET.copy()
    parametros_paginacao.pop("page", None)
    querystring_paginacao = parametros_paginacao.urlencode()
    paginador = Paginator(questoes, 10)
    questoes = paginador.get_page(request.GET.get("page"))

    tentativas_qs = TentativaQuestao.objects.filter(perfil=perfil)
    tentativas_map = {t.questao_id: t for t in tentativas_qs.order_by("id")}
    from django.db.models import Count
    tentativas_count_map = dict(
        tentativas_qs.values("questao_id").annotate(c=Count("id")).values_list("questao_id", "c")
    )

    for q in questoes:
        q.ultima_tentativa = tentativas_map.get(q.id)
        q.total_tentativas = tentativas_count_map.get(q.id, 0)
        correta = Alternativa.objects.filter(questao=q, e_correta=True).first()
        q.gabarito_letra = correta.letra if correta else "A"
        q.gabarito_id = correta.id if correta else None
        if q.ultima_tentativa:
            taxa = calcular_taxa_acerto(q)
            q.taxa_acerto = round(taxa, 1)
            q.circunferencia_offset = round(301.59 * (1 - max(0, min(100, taxa)) / 100), 2)

    return render(
        request,
        "questoes.html",
        {
            "questoes": questoes,
            "total_questoes": total_questoes,
            "filtro": filtro,
            "disciplinas": disciplinas,
            "conteudos": conteudos,
            "anos": anos,
            "dificuldades": dificuldades,
            "disciplina": disciplina_geral,
            "disciplina1": disciplina1,
            "disciplina2": disciplina2,
            "disciplina3": disciplina3,
            "conteudo1": conteudo1,
            "conteudo2": conteudo2,
            "conteudo3": conteudo3,
            "ano": ano,
            "dificuldade": dificuldade,
            "resultado_questao": resultado_questao,
            "perfil": perfil,
            "acertadas_ids": set(questoes_acertadas.values_list("id", flat=True)),
            "respondidas_ids": set(questoes_respondidas.values_list("id", flat=True)),
            "tentativas_dict": tentativas_map,
            "paginador": paginador,
            "querystring_paginacao": querystring_paginacao,
        }
    )


@login_required
def conteudos(request):
    questoes = Questao.objects.all()

    return render(request, "questoes.html", {"questoes": questoes})

@login_required
def ranking(request):
    questoes = Questao.objects.all()

    return render(request, "questoes.html", {"questoes": questoes})

@login_required
def sobre(request):
    questoes = Questao.objects.all()

    return render(request, "questoes.html", {"questoes": questoes})

def logout_view(request):
    logout(request)
    return redirect("login")