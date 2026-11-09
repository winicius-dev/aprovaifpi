from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as login_django, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import (
    Perfil,
    Escola,
    Questao,
    Alternativa,
    TentativaQuestao,
    Disciplina,
    Conteudo,
    Conquista,
    ConquistaPerfil,
    SessaoRecuperacao,
    CronogramaEstudoItem,
    EventoAgenda,
    SemanaProva,
    AvaliacaoSemanaProva
)
import json
import datetime
from django.db import transaction
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db import models
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Q, IntegerField
from django.db.models.functions import Coalesce




@login_required
def inicio(request):
    """Página inicial - Dashboard do estudante."""
    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    stats = obter_estatisticas_perfil(perfil)
    total_questoes = Questao.objects.count()

    # Ranking Geral
    perfis_geral = list(Perfil.objects.select_related("usuario", "escola").order_by("-xp", "nome", "id"))

    AVATAR_CORES = [
        "#0056d6", "#dc2626", "#16a34a", "#9333ea", "#0d9488",
        "#ca8a04", "#4b5563", "#0284c7", "#c026d3", "#ea580c"
    ]

    for i, p in enumerate(perfis_geral, start=1):
        p.posicao = i
        p.xp_ranking = p.xp
        p.cor_avatar = AVATAR_CORES[p.id % len(AVATAR_CORES)]
        p.inicial = (p.nome[:1].upper() if p.nome else 'U')

    posicao_geral = next((p.posicao for p in perfis_geral if p.id == perfil.id), None)

    # Ranking Escolar
    perfis_escola = [p for p in perfis_geral if p.escola_id == perfil.escola_id]
    posicao_escolar = next((i for i, p in enumerate(perfis_escola, start=1) if p.id == perfil.id), None)

    # Ranking Semanal
    hoje = timezone.localdate()
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    perfis_semanais = Perfil.objects.select_related("usuario", "escola").annotate(
        xp_ranking=Coalesce(
            Sum(
                "tentativaquestao__xp_ganho",
                filter=Q(
                    tentativaquestao__data_realizacao__date__gte=inicio_semana,
                    tentativaquestao__data_realizacao__date__lte=hoje
                )
            ),
            0,
            output_field=IntegerField()
        )
    ).order_by("-xp_ranking", "-xp", "nome", "id")

    perfis_semanais_list = list(perfis_semanais)
    for i, p in enumerate(perfis_semanais_list, start=1):
        p.posicao = i
        p.xp_semanal = p.xp_ranking
        p.cor_avatar = AVATAR_CORES[p.id % len(AVATAR_CORES)]
        p.inicial = (p.nome[:1].upper() if p.nome else 'U')

    # Top 10 e Top 5 para os Rankings Geral e Semanal
    top_10_geral = perfis_geral[:10]
    top_5_geral = perfis_geral[:5]
    top_10_semanal = perfis_semanais_list[:10]
    top_5_semanal = perfis_semanais_list[:5]

    # Taxa de acerto circle offset
    taxa_acerto = stats["taxa_acerto"]
    circunferencia = 301.59
    circunferencia_offset = circunferencia * (1 - max(0, min(100, taxa_acerto)) / 100)
    offset_100 = round(100 - max(0, min(100, taxa_acerto)), 1)
    taxa_acerto_int = int(round(taxa_acerto))

    verificar_conquistas(perfil)

    return render(request, "inicio.html", {
        "perfil": perfil,
        "stats": stats,
        "total_questoes": total_questoes,
        "posicao_geral": posicao_geral,
        "posicao_escolar": posicao_escolar,
        "top_10_geral": top_10_geral,
        "top_5_geral": top_5_geral,
        "top_10_semanal": top_10_semanal,
        "top_5_semanal": top_5_semanal,
        "taxa_acerto": taxa_acerto,
        "taxa_acerto_int": taxa_acerto_int,
        "circunferencia": circunferencia,
        "circunferencia_offset": circunferencia_offset,
        "offset_100": offset_100,
    })


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
            return redirect("inicio")
        
        messages.error(request, "E-mail ou senha incorretos")
    return render(request, "login.html")


def calcular_taxa_acerto(questao):
    primeiras_tentativas = TentativaQuestao.objects.filter(questao=questao, numero_tentativa=1)
    total = primeiras_tentativas.values("perfil").distinct().count()

    if total == 0:
        return 0

    acertos = primeiras_tentativas.filter(acertou=True).values("perfil").distinct().count()

    return round(acertos / total * 100, 1)


def desbloquear_conquista(perfil, codigo):
    """
    Desbloqueia uma conquista para o perfil de forma permanente e segura.
    Regra de negócio:
    - O aluno só recebe o XP da conquista uma única vez (ao conquistá-la pela 1ª vez).
    - Para todas as conquistas de ranking (Top 1, Top 10, Top 3 Semanal), se o aluno
      posteriormente sair da posição no ranking, ele CONTINUA com o XP ganho e com o banner.
    - Caso reingresse no ranking, não recebe XP duplicado (criada = False).
    """
    conquista = Conquista.objects.filter(codigo=codigo, ativa=True).first()

    if conquista is None:
        return False

    _, criada = ConquistaPerfil.objects.get_or_create(perfil=perfil, conquista=conquista)

    # Só credita XP se o registro foi criado pela primeira vez
    if criada and conquista.xp_recompensa > 0:
        perfil.xp += conquista.xp_recompensa
        perfil.save(update_fields=["xp"])

    return criada


def verificar_conquistas(perfil):
    tentativas = TentativaQuestao.objects.filter(perfil=perfil)

    # CENTENA E VETERNANO
    total_questoes = tentativas.values("questao_id").distinct().count()

    if total_questoes >= 100:
        desbloquear_conquista(perfil, "centena")

    if total_questoes >= 300:
        desbloquear_conquista(perfil, "veterano")

    # 2. MESTRE E PALAVRA CERTA
    acertos_primeira = tentativas.filter(acertou=True, numero_tentativa=1)

    acertos_matematica = acertos_primeira.filter(questao__conteudo__disciplina__nome__iexact="Matemática").values("questao_id").distinct().count()

    if acertos_matematica >= 50:
        desbloquear_conquista(perfil, "mestre")

    acertos_portugues = acertos_primeira.filter(questao__conteudo__disciplina__nome__iexact="Português").values("questao_id").distinct().count()

    if acertos_portugues >= 50:
        desbloquear_conquista(perfil, "palavra-certa")

    # 3. RUMO AO IFPI
    total_disponiveis = Questao.objects.count()
    total_acertos_primeira = acertos_primeira.values("questao_id").distinct().count()

    if total_disponiveis and total_acertos_primeira / total_disponiveis >= 0.5:
        desbloquear_conquista(perfil, "rumo-ao-ifpi")

    # 4. POLIVALENTE
    total_conteudos = tentativas.values("questao__conteudo_id").distinct().count()

    if total_conteudos >= 10:
        desbloquear_conquista(perfil, "polivalente")

    # 5. NA MOSCA
    ultimas_tentativas = list(tentativas.order_by("-data_realizacao", "-id")[:10])

    if (
        len(ultimas_tentativas) == 10
        and len({t.questao_id for t in ultimas_tentativas}) == 10
        and all(t.acertou and t.numero_tentativa == 1 for t in ultimas_tentativas)
    ):
        desbloquear_conquista(perfil, "na-mosca")

    # 6. ATIVO
    dias_ativos = set(tentativas.dates("data_realizacao", "day", order="DESC"))

    hoje = timezone.localdate()
    sequencia_dias = 0

    for i in range(30):
        dia = hoje - timedelta(days=i)

        if dia in dias_ativos:
            sequencia_dias += 1
        else:
            break

    if sequencia_dias == 30:
        desbloquear_conquista(perfil, "ativo")

    # 7. CONQUISTAS DO RANKNG
    perfis_geral = list(
        Perfil.objects.order_by("-xp", "nome", "id")
    )

    posicao_geral = next(
        (
            indice
            for indice, item in enumerate(perfis_geral, start=1)
            if item.id == perfil.id
        ),
        None
    )

    if posicao_geral == 1:
        desbloquear_conquista(perfil, "top-1")

    if posicao_geral is not None and posicao_geral <= 10:
        desbloquear_conquista(perfil, "top-10")

    # RANKING SEMANAL
    hoje = timezone.localdate()
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    perfis_semanais = Perfil.objects.annotate(
        xp_semanal=Coalesce(
            Sum(
                "tentativaquestao__xp_ganho",
                filter=Q(
                    tentativaquestao__data_realizacao__date__gte=inicio_semana,
                    tentativaquestao__data_realizacao__date__lte=hoje
                )
            ),
            0,
            output_field=IntegerField()
        )
    ).order_by("-xp_semanal", "nome", "id")

    posicao_semanal = next(
        (
            indice
            for indice, item in enumerate(perfis_semanais, start=1)
            if item.id == perfil.id
        ),
        None
    )

    xp_semanal_usuario = next((item.xp_semanal for item in perfis_semanais if item.id == perfil.id), 0)

    if posicao_semanal is not None and posicao_semanal <= 3 and xp_semanal_usuario > 0:
        desbloquear_conquista(perfil, "top-3-semanal")


def calcular_ofensiva(perfil):
    dias_ativos = set(
        TentativaQuestao.objects.filter(perfil=perfil).dates("data_realizacao", "day", order="DESC")
    )

    hoje = timezone.localdate()

    if hoje in dias_ativos:
        dia_referencia = hoje
    elif hoje - timedelta(days=1) in dias_ativos:
        dia_referencia = hoje - timedelta(days=1)
    else:
        return 0

    ofensiva = 0

    while dia_referencia in dias_ativos:
        ofensiva += 1
        dia_referencia -= timedelta(days=1)

    return ofensiva


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

    # Apenas questões das disciplinas Português e Matemática existem e devem ser consideradas
    questoes_base = Questao.objects.filter(conteudo__disciplina__id__in=[1, 2])  # Portugues e Matematica
    questoes_acertadas = questoes_base.filter(tentativaquestao__perfil=perfil, tentativaquestao__acertou=True).distinct()
    questoes_respondidas = questoes_base.filter(tentativaquestao__perfil=perfil).distinct()
    questoes_nao_respondidas = questoes_base.exclude(id__in=questoes_respondidas.values("id"))
    questoes_erradas = questoes_respondidas.exclude(id__in=questoes_acertadas.values("id"))

    if filtro == "respondidas":
        questoes = questoes_respondidas
    elif filtro == "acertadas":
        questoes = questoes_acertadas
    elif filtro == "erradas":
        questoes = questoes_erradas
    elif filtro == "todas_banco":
        questoes = questoes_base
    else:
        # Padrão: exibe apenas questões não respondidas.
        # Assim que uma questão é respondida, ela some ao atualizar a página ou trocar de aba.
        questoes = questoes_nao_respondidas
        filtro = "nao_respondidas"

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
    disciplinas = Disciplina.objects.filter(id__in=[1, 2]).order_by("nome")  # Portugues e Matematica
    conteudos = Conteudo.objects.filter(disciplina__in=disciplinas).select_related("disciplina").order_by("disciplina__nome", "nome")
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
        verificar_conquistas(perfil)
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
                "sucesso": True, "ok": True,
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
                "explicacao": "Em construção."
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

    # Ordem aleatória toda vez que a página é carregada
    page_param = request.GET.get("page")
    seed_key = f"questoes_seed_{filtro}_{disciplina_geral}_{disciplina1}_{disciplina2}_{disciplina3}_{conteudo1}_{conteudo2}_{conteudo3}_{ano}_{dificuldade}"

    import random
    if not page_param or seed_key not in request.session:
        seed = random.randint(1, 10000000)
        request.session[seed_key] = seed
    else:
        seed = request.session[seed_key]

    questoes_ids = list(questoes.values_list("id", flat=True))
    rng = random.Random(seed)
    rng.shuffle(questoes_ids)

    # Se houve resultado de resposta sem AJAX nesta requisição, garante que a questão recém-respondida
    # continue visível até que a página seja recarregada ou a aba seja trocada
    if resultado_questao and resultado_questao.get("questao_id"):
        qid_recente = resultado_questao["questao_id"]
        if qid_recente not in questoes_ids:
            questoes_ids.insert(0, qid_recente)

    total_questoes = len(questoes_ids)
    paginador = Paginator(questoes_ids, 10)
    page_obj = paginador.get_page(page_param)

    page_ids = list(page_obj.object_list)
    questoes_dict = {
        q.id: q
        for q in Questao.objects.filter(id__in=page_ids).select_related("conteudo__disciplina")
    }
    questoes_ordenadas = [questoes_dict[qid] for qid in page_ids if qid in questoes_dict]
    page_obj.object_list = questoes_ordenadas
    questoes = page_obj

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
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Sum, IntegerField, Q
    from django.db.models.functions import Coalesce

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    modalidade = request.GET.get("tipo", "geral")

    if modalidade not in ["geral", "semanal", "escola"]:
        modalidade = "geral"

    hoje = timezone.localdate()
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    AVATAR_CORES = [
        "#0056d6", "#dc2626", "#16a34a", "#9333ea", "#0d9488",
        "#ca8a04", "#4b5563", "#0284c7", "#c026d3", "#ea580c"
    ]

    if modalidade == "escola":
        ranking_escolas = Escola.objects.annotate(
            xp_ranking=Coalesce(Sum("perfil__xp"), 0, output_field=IntegerField())
        ).order_by("-xp_ranking", "nome", "id")

        lista_perfis = list(ranking_escolas)

        for escola in lista_perfis:
            escola.ofensiva = "-"
            escola.cor_avatar = AVATAR_CORES[(escola.id if hasattr(escola, 'id') else 1) % len(AVATAR_CORES)]
            escola.inicial = (escola.nome[:1].upper() if hasattr(escola, 'nome') and escola.nome else 'E')

        for i, escola in enumerate(lista_perfis, start=1):
            escola.posicao = i

        posicao_usuario = next((e.posicao for e in lista_perfis if e.id == perfil.escola_id), None)
        xp_usuario = next((e.xp_ranking for e in lista_perfis if e.id == perfil.escola_id), 0)
        xp_para_top1 = max(0, lista_perfis[0].xp_ranking - xp_usuario) if lista_perfis else 0

    else:
        perfis = Perfil.objects.select_related("usuario", "escola")

        if modalidade == "semanal":
            perfis = perfis.annotate(
                xp_ranking=Coalesce(
                    Sum(
                        "tentativaquestao__xp_ganho",
                        filter=Q(
                            tentativaquestao__data_realizacao__date__gte=inicio_semana,
                            tentativaquestao__data_realizacao__date__lte=hoje
                        )
                    ),
                    0,
                    output_field=IntegerField()
                )
            ).order_by("-xp_ranking", "nome", "id")
        else:
            perfis = perfis.order_by("-xp", "nome", "id")

        lista_perfis = list(perfis)

        for p in lista_perfis:
            p.ofensiva = calcular_ofensiva(p)
            p.cor_avatar = AVATAR_CORES[(p.id if hasattr(p, 'id') else 1) % len(AVATAR_CORES)]
            p.inicial = (p.nome[:1].upper() if hasattr(p, 'nome') and p.nome else 'U')

        for i, p in enumerate(lista_perfis, start=1):
            p.posicao = i

        for p in lista_perfis:
            banners = p.get_banners_equipados()
            if not banners:
                banners = list(Conquista.objects.filter(ativa=True, desbloqueios__perfil=p).distinct().order_by("-xp_recompensa")[:2])
            p.banners = banners[:2]

        posicao_usuario = next((p.posicao for p in lista_perfis if p.id == perfil.id), None)

        if modalidade == "semanal":
            xp_usuario = next((p.xp_ranking for p in lista_perfis if p.id == perfil.id), 0)
            xp_top1 = lista_perfis[0].xp_ranking if lista_perfis else 0
        else:
            xp_usuario = perfil.xp
            xp_top1 = lista_perfis[0].xp if lista_perfis else 0

        xp_para_top1 = max(0, xp_top1 - xp_usuario)

    verificar_conquistas(perfil)

    conquistas = list(Conquista.objects.filter(ativa=True).order_by("-xp_recompensa", "nome"))

    desbloqueios = {
        item.conquista_id: item
        for item in ConquistaPerfil.objects.filter(perfil=perfil)
    }

    for conquista in conquistas:
        registro = desbloqueios.get(conquista.id)
        conquista.desbloqueada = registro is not None
        conquista.data_desbloqueio = (registro.data_desbloqueio if registro else None)

    top_3 = lista_perfis[:3]
    resto_perfis = lista_perfis[3:]

    return render(request, "ranking.html", {
        "perfil": perfil,
        "perfis_ranking": lista_perfis,
        "top_3": top_3,
        "resto_perfis": resto_perfis,
        "modalidade": modalidade,
        "posicao_usuario": posicao_usuario,
        "xp_para_top1": xp_para_top1,
        "conquistas": conquistas,
        "ofensiva_usuario": calcular_ofensiva(perfil),
    })


def obter_estatisticas_perfil(perfil_alvo):
    """Calcula estatísticas de desempenho, banners e ofensiva para um perfil."""
    verificar_conquistas(perfil_alvo)

    questoes_respondidas = Questao.objects.filter(tentativaquestao__perfil=perfil_alvo).distinct().count()
    questoes_acertadas = Questao.objects.filter(tentativaquestao__perfil=perfil_alvo, tentativaquestao__acertou=True).distinct().count()
    questoes_erradas = max(0, questoes_respondidas - questoes_acertadas)

    total_tentativas = TentativaQuestao.objects.filter(perfil=perfil_alvo).count()
    tentativas_certas = TentativaQuestao.objects.filter(perfil=perfil_alvo, acertou=True).count()
    tentativas_erradas = TentativaQuestao.objects.filter(perfil=perfil_alvo, acertou=False).count()

    taxa_acerto = round((questoes_acertadas / questoes_respondidas * 100), 1) if questoes_respondidas > 0 else 0.0

    banners = perfil_alvo.get_banners_equipados()
    if not banners:
        banners = list(Conquista.objects.filter(ativa=True, desbloqueios__perfil=perfil_alvo).distinct().order_by("-xp_recompensa")[:2])

    conquistas_desbloqueadas = list(
        Conquista.objects.filter(ativa=True, desbloqueios__perfil=perfil_alvo).distinct().order_by("-xp_recompensa", "nome")
    )

    perfis_geral = list(Perfil.objects.order_by("-xp", "nome", "id"))
    posicao_ranking = next((idx for idx, p in enumerate(perfis_geral, start=1) if p.id == perfil_alvo.id), None)

    return {
        "questoes_respondidas": questoes_respondidas,
        "questoes_acertadas": questoes_acertadas,
        "questoes_erradas": questoes_erradas,
        "total_tentativas": total_tentativas,
        "tentativas_certas": tentativas_certas,
        "tentativas_erradas": tentativas_erradas,
        "taxa_acerto": taxa_acerto,
        "ofensiva": calcular_ofensiva(perfil_alvo),
        "banners_equipados": banners[:2],
        "conquistas_desbloqueadas": conquistas_desbloqueadas,
        "posicao_ranking": posicao_ranking,
    }


@login_required
def meu_perfil(request):
    perfil = Perfil.objects.select_related("usuario", "escola").get(usuario=request.user)
    verificar_conquistas(perfil)

    aba_ativa = request.GET.get("aba", "perfil")

    if request.method == "POST":
        acao = request.POST.get("acao", "")

        if acao == "atualizar_perfil":
            nome = request.POST.get("nome", "").strip()
            remover_avatar = request.POST.get("remover_avatar", "") == "true"

            if not nome or len(nome.split()) < 2:
                messages.error(request, "Por favor, digite seu nome completo (nome e sobrenome).")
                return redirect(f"/auth/perfil/?aba=perfil")

            perfil.nome = nome

            if remover_avatar:
                if perfil.avatar:
                    perfil.avatar.delete(save=False)
                    perfil.avatar = None

            if "avatar" in request.FILES:
                avatar_file = request.FILES["avatar"]
                if avatar_file.size > 5 * 1024 * 1024:
                    messages.error(request, "A imagem de perfil deve ter no máximo 5MB.")
                    return redirect(f"/auth/perfil/?aba=perfil")
                perfil.avatar = avatar_file

            perfil.save()
            messages.success(request, "Perfil atualizado com sucesso!")
            return redirect(f"/auth/perfil/?aba=perfil")

        elif acao == "atualizar_banners":
            desbloqueadas_ids = set(
                ConquistaPerfil.objects.filter(perfil=perfil).values_list("conquista_id", flat=True)
            )

            banner_1_val = request.POST.get("banner_1", "").strip()
            banner_2_val = request.POST.get("banner_2", "").strip()

            novo_b1 = None
            if banner_1_val and banner_1_val.isdigit():
                b1_id = int(banner_1_val)
                if b1_id in desbloqueadas_ids:
                    novo_b1 = Conquista.objects.filter(id=b1_id, ativa=True).first()

            novo_b2 = None
            if banner_2_val and banner_2_val.isdigit():
                b2_id = int(banner_2_val)
                if b2_id in desbloqueadas_ids and (novo_b1 is None or b2_id != novo_b1.id):
                    novo_b2 = Conquista.objects.filter(id=b2_id, ativa=True).first()

            perfil.banner_1 = novo_b1
            perfil.banner_2 = novo_b2
            perfil.save()

            messages.success(request, "Banners em destaque atualizados com sucesso! Eles serão exibidos no seu perfil e no ranking.")
            return redirect(f"/auth/perfil/?aba=banners")

    stats = obter_estatisticas_perfil(perfil)

    desbloqueios = {
        item.conquista_id: item
        for item in ConquistaPerfil.objects.filter(perfil=perfil)
    }

    todas_conquistas = list(Conquista.objects.filter(ativa=True).order_by("-xp_recompensa", "nome"))
    for c in todas_conquistas:
        registro = desbloqueios.get(c.id)
        c.desbloqueada = registro is not None
        c.data_desbloqueio = (registro.data_desbloqueio if registro else None)
        c.equipado_slot1 = (perfil.banner_1_id == c.id)
        c.equipado_slot2 = (perfil.banner_2_id == c.id)

    conquistas_desbloqueadas = [c for c in todas_conquistas if c.desbloqueada]

    return render(request, "perfil.html", {
        "perfil": perfil,
        "stats": stats,
        "aba_ativa": aba_ativa,
        "todas_conquistas": todas_conquistas,
        "conquistas_desbloqueadas": conquistas_desbloqueadas,
        "is_proprio_perfil": True,
    })


@login_required
def configuracoes(request):
    perfil = Perfil.objects.select_related("usuario", "escola").get(usuario=request.user)

    if request.method == "POST":
        acao = request.POST.get("acao", "")

        if acao == "alterar_email":
            novo_email = request.POST.get("email", "").strip().lower()

            if not novo_email or "@" not in novo_email:
                messages.error(request, "Por favor, informe um endereço de e-mail válido.")
                return redirect("configuracoes")

            if User.objects.exclude(id=request.user.id).filter(Q(email__iexact=novo_email) | Q(username__iexact=novo_email)).exists():
                messages.error(request, "Este endereço de e-mail já está em uso por outra conta.")
                return redirect("configuracoes")

            request.user.email = novo_email
            request.user.username = novo_email
            request.user.save()

            messages.success(request, "E-mail alterado com sucesso!")
            return redirect("configuracoes")

        elif acao == "alterar_senha":
            senha_atual = request.POST.get("senha_atual", "")
            nova_senha = request.POST.get("nova_senha", "")
            confirmar_senha = request.POST.get("confirmar_senha", "")

            if not request.user.check_password(senha_atual):
                messages.error(request, "A senha atual informada está incorreta.")
                return redirect("configuracoes")

            if len(nova_senha) < 8:
                messages.error(request, "A nova senha deve possuir pelo menos 8 caracteres.")
                return redirect("configuracoes")

            if nova_senha != confirmar_senha:
                messages.error(request, "A nova senha e a confirmação não conferem.")
                return redirect("configuracoes")

            request.user.set_password(nova_senha)
            request.user.save()
            update_session_auth_hash(request, request.user)

            messages.success(request, "Senha alterada com sucesso!")
            return redirect("configuracoes")

        elif acao == "alterar_tema":
            tema_escuro_val = request.POST.get("tema_escuro") in ["true", "1", "on", True]
            perfil.tema_escuro = tema_escuro_val
            perfil.save()
            messages.success(request, f"Tema {'escuro' if tema_escuro_val else 'claro'} salvo com sucesso!")
            return redirect("configuracoes")

    stats = obter_estatisticas_perfil(perfil)

    return render(request, "configuracoes.html", {
        "perfil": perfil,
        "stats": stats,
        "aba_ativa": "configuracoes",
    })


@login_required
def perfil_publico(request, perfil_id):
    perfil_alvo = get_object_or_404(Perfil.objects.select_related("usuario", "escola"), id=perfil_id)
    perfil_logado = Perfil.objects.select_related("usuario", "escola").get(usuario=request.user)

    if perfil_alvo.id == perfil_logado.id:
        return redirect("perfil")

    stats = obter_estatisticas_perfil(perfil_alvo)

    return render(request, "perfil.html", {
        "perfil": perfil_alvo,
        "perfil_logado": perfil_logado,
        "stats": stats,
        "is_proprio_perfil": False,
        "aba_ativa": "perfil",
    })


@login_required
def perfil_api(request, perfil_id):
    """Endpoint JSON rápido para visualização instantânea de perfil no ranking."""
    perfil_alvo = get_object_or_404(Perfil.objects.select_related("usuario", "escola"), id=perfil_id)
    stats = obter_estatisticas_perfil(perfil_alvo)

    banners_data = [
        {"codigo": b.codigo, "nome": b.nome, "xp": b.xp_recompensa}
        for b in stats["banners_equipados"]
    ]

    conquistas_data = [
        {"codigo": c.codigo, "nome": c.nome, "xp": c.xp_recompensa}
        for c in stats["conquistas_desbloqueadas"]
    ]

    AVATAR_CORES = [
        "#0056d6", "#dc2626", "#16a34a", "#9333ea", "#0d9488",
        "#ca8a04", "#4b5563", "#0284c7", "#c026d3", "#ea580c"
    ]

    return JsonResponse({
        "success": True,
        "id": perfil_alvo.id,
        "nome": perfil_alvo.nome,
        "escola": perfil_alvo.escola.nome,
        "xp": perfil_alvo.xp,
        "avatar_url": perfil_alvo.avatar.url if perfil_alvo.avatar else None,
        "inicial": perfil_alvo.nome[:1].upper() if perfil_alvo.nome else "U",
        "cor_avatar": AVATAR_CORES[perfil_alvo.id % len(AVATAR_CORES)],
        "questoes_respondidas": stats["questoes_respondidas"],
        "questoes_acertadas": stats["questoes_acertadas"],
        "questoes_erradas": stats["questoes_erradas"],
        "taxa_acerto": stats["taxa_acerto"],
        "ofensiva": stats["ofensiva"],
        "posicao_ranking": stats["posicao_ranking"],
        "banners": banners_data,
        "conquistas": conquistas_data,
    })


def recuperar_conta(request):
    """Página de recuperação de conta / redefinição de senha."""
    etapa = "identificar"
    email_identificado = ""

    if request.method == "POST":
        acao = request.POST.get("acao", "")

        if acao == "buscar_conta":
            email = request.POST.get("email", "").strip().lower()
            usuario = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()

            if not usuario:
                messages.error(request, "Nenhuma conta foi encontrada com o e-mail informado.")
            else:
                messages.success(request, f"Conta encontrada com sucesso para {usuario.email}! Agora defina sua nova senha.")
                etapa = "redefinir"
                email_identificado = usuario.email

        elif acao == "redefinir_senha":
            email = request.POST.get("email", "").strip().lower()
            nova_senha = request.POST.get("nova_senha", "")
            confirmar_senha = request.POST.get("confirmar_senha", "")

            usuario = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()

            if not usuario:
                messages.error(request, "Usuário não encontrado.")
            elif len(nova_senha) < 8:
                messages.error(request, "A nova senha deve ter no mínimo 8 caracteres.")
                etapa = "redefinir"
                email_identificado = email
            elif nova_senha != confirmar_senha:
                messages.error(request, "A nova senha e a confirmação não coincidem.")
                etapa = "redefinir"
                email_identificado = email
            else:
                usuario.set_password(nova_senha)
                usuario.save()
                messages.success(request, "Senha redefinida com sucesso! Você já pode entrar com sua nova senha.")
                return redirect("login")

    return render(request, "recuperar_conta.html", {
        "etapa": etapa,
        "email_identificado": email_identificado,
    })


@login_required
def sobre(request):
    perfil = Perfil.objects.get(usuario=request.user)
    questoes = Questao.objects.all()
    return render(request, "questoes.html", {"questoes": questoes, "perfil": perfil})


def logout_view(request):
    logout(request)
    return redirect("login")


def eh_estudante_ifpi(perfil):
    """Verifica se o estudante foi cadastrado em uma escola do IFPI."""
    if not perfil or not perfil.escola:
        return False
    nome = perfil.escola.nome.upper()
    return "IFPI" in nome or "INSTITUTO FEDERAL" in nome


@login_required
def recuperaifpi(request):
    """Página principal do RecuperaIFPI - seleção, atividade e resultado."""
    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)

    # Restrição de acesso: exclusivo para estudantes cadastrados no IFPI
    if not eh_estudante_ifpi(perfil):
        context = {
            "perfil": perfil,
            "acesso_negado": True,
            "escola_aluno": perfil.escola.nome if perfil.escola else "Não informada",
        }
        return render(request, "recuperaifpi.html", context)

    # Na parte de atividades: apenas Portugues e Matematica por enquanto
    disciplinas_atividades = Disciplina.objects.filter(id__in=[1, 2]).order_by("nome")
    conteudos_atividades = Conteudo.objects.filter(disciplina__in=disciplinas_atividades).select_related("disciplina").order_by("disciplina__nome", "nome")

    # No cronograma e na agenda: manter todas as disciplinas
    disciplinas_todas = Disciplina.objects.all().order_by("nome")
    disciplinas = disciplinas_atividades
    conteudos = conteudos_atividades

    modo = request.GET.get("modo", "selecao")
    secao = request.GET.get("secao", "atividades")
    if modo in ["atividade", "resultado"]:
        secao = "atividades"
    disciplina_selecionada = request.GET.get("disciplina", "")
    conteudo_id = request.GET.get("conteudo", "")
    sessao_id = request.GET.get("sessao_id", "")

    conteudo_selecionado = None
    questoes = []
    questao_atual = None
    questao_index = 0
    total_questoes = 0
    resultado = None
    historico = []
    feedback = None

    # Carregar histórico geral do estudante (sessões finalizadas)
    sessoes_anteriores = SessaoRecuperacao.objects.filter(
        perfil=perfil, finalizada=True
    ).order_by("-data_inicio")

    # Se um conteúdo específico foi selecionado, filtrar histórico por ele
    if conteudo_id:
        try:
            conteudo_selecionado = Conteudo.objects.get(id=int(conteudo_id))
            historico_qs = sessoes_anteriores.filter(conteudo=conteudo_selecionado)
        except (Conteudo.DoesNotExist, ValueError):
            conteudo_selecionado = None
            historico_qs = sessoes_anteriores
    else:
        historico_qs = sessoes_anteriores

    for s in historico_qs[:10]:
        historico.append({
            "data": s.data_inicio,
            "acertos": s.acertos,
            "total": s.total_questoes,
            "percentual": s.percentual,
            "conteudo_nome": s.conteudo.nome,
            "disciplina_nome": s.conteudo.disciplina.nome,
        })

    if modo == "atividade" and conteudo_selecionado:
        # Buscar questões do conteúdo selecionado (limitado a no máximo 5 questões)
        questoes_lista = list(
            Questao.objects.filter(conteudo=conteudo_selecionado).order_by("id")[:5]
        )
        total_questoes = len(questoes_lista)

        if total_questoes == 0:
            modo = "selecao"
        else:
            # Obter ou criar sessão
            if sessao_id:
                try:
                    sessao = SessaoRecuperacao.objects.get(
                        id=int(sessao_id), perfil=perfil, finalizada=False
                    )
                    # Forçar limite de no máximo 5 questões na sessão
                    if sessao.total_questoes > 5 or sessao.total_questoes != total_questoes:
                        sessao.total_questoes = total_questoes
                        sessao.save(update_fields=["total_questoes"])
                except (SessaoRecuperacao.DoesNotExist, ValueError):
                    sessao = SessaoRecuperacao.objects.create(
                        perfil=perfil,
                        conteudo=conteudo_selecionado,
                        total_questoes=total_questoes,
                    )
            else:
                sessao = SessaoRecuperacao.objects.create(
                    perfil=perfil,
                    conteudo=conteudo_selecionado,
                    total_questoes=total_questoes,
                )
            sessao_id = sessao.id

            # Determinar qual questão exibir
            questao_index_str = request.GET.get("questao_index", "0")
            try:
                questao_index = int(questao_index_str)
            except ValueError:
                questao_index = 0

            # Verificar feedback de resposta anterior
            feedback_data = request.session.pop("recupera_feedback", None)
            if feedback_data and feedback_data.get("sessao_id") == sessao_id:
                feedback = feedback_data

            if questao_index >= total_questoes:
                # Finalizar sessão
                sessao.finalizada = True
                sessao.data_fim = timezone.now()
                sessao.save(update_fields=["finalizada", "data_fim"])

                total_calc = sessao.total_questoes if sessao.total_questoes > 0 else (sessao.acertos + sessao.erros)
                total_calc = min(total_calc, 5)
                pct = sessao.percentual
                pct_val = int(pct) if (isinstance(pct, (int, float)) and pct == int(pct)) else pct

                resultado = {
                    "sessao_id": sessao.id,
                    "total": total_calc,
                    "acertos": sessao.acertos,
                    "erros": sessao.erros,
                    "percentual": pct_val,
                    "disciplina_nome": conteudo_selecionado.disciplina.nome if (conteudo_selecionado and conteudo_selecionado.disciplina) else "",
                    "conteudo_nome": conteudo_selecionado.nome if conteudo_selecionado else "",
                    "xp_ganho": 0,
                }
                modo = "resultado"

                # Atualizar histórico com a sessão recém-finalizada
                historico_qs = SessaoRecuperacao.objects.filter(
                    perfil=perfil, finalizada=True, conteudo=conteudo_selecionado
                ).order_by("-data_inicio")
                historico = []
                for s in historico_qs[:10]:
                    historico.append({
                        "data": s.data_inicio,
                        "acertos": s.acertos,
                        "total": min(s.total_questoes, 5) if s.total_questoes > 0 else (s.acertos + s.erros),
                        "percentual": s.percentual,
                        "conteudo_nome": s.conteudo.nome,
                        "disciplina_nome": s.conteudo.disciplina.nome,
                    })
            else:
                questao_atual = questoes_lista[questao_index]

    elif modo == "resultado":
        sessao = None
        if sessao_id:
            try:
                sessao = SessaoRecuperacao.objects.select_related(
                    "conteudo__disciplina", "perfil"
                ).get(id=int(sessao_id), perfil=perfil)
            except (SessaoRecuperacao.DoesNotExist, ValueError):
                sessao = None

        if not sessao and conteudo_selecionado:
            sessao = SessaoRecuperacao.objects.select_related(
                "conteudo__disciplina", "perfil"
            ).filter(perfil=perfil, conteudo=conteudo_selecionado).order_by("-data_inicio").first()

        if not sessao:
            sessao = SessaoRecuperacao.objects.select_related(
                "conteudo__disciplina", "perfil"
            ).filter(perfil=perfil).order_by("-data_inicio").first()

        if sessao:
            if not sessao.finalizada:
                sessao.finalizada = True
                sessao.data_fim = timezone.now()
                sessao.save(update_fields=["finalizada", "data_fim"])

            if not conteudo_selecionado and sessao.conteudo:
                conteudo_selecionado = sessao.conteudo
            if not disciplina_selecionada and sessao.conteudo and sessao.conteudo.disciplina:
                disciplina_selecionada = str(sessao.conteudo.disciplina.id)

            sessao_id = sessao.id
            total_calc = sessao.total_questoes if sessao.total_questoes > 0 else (sessao.acertos + sessao.erros)
            total_calc = min(total_calc, 5)
            pct = sessao.percentual
            pct_val = int(pct) if (isinstance(pct, (int, float)) and pct == int(pct)) else pct

            resultado = {
                "sessao_id": sessao.id,
                "total": total_calc,
                "acertos": sessao.acertos,
                "erros": sessao.erros,
                "percentual": pct_val,
                "disciplina_nome": sessao.conteudo.disciplina.nome if (sessao.conteudo and sessao.conteudo.disciplina) else "",
                "conteudo_nome": sessao.conteudo.nome if sessao.conteudo else "",
                "xp_ganho": 0,
            }

            historico_qs = SessaoRecuperacao.objects.filter(
                perfil=perfil, finalizada=True
            )
            if sessao.conteudo:
                historico_qs = historico_qs.filter(conteudo=sessao.conteudo)
            historico_qs = historico_qs.order_by("-data_inicio")
            historico = []
            for s in historico_qs[:10]:
                historico.append({
                    "data": s.data_inicio,
                    "acertos": s.acertos,
                    "total": min(s.total_questoes, 5) if s.total_questoes > 0 else (s.acertos + s.erros),
                    "percentual": s.percentual,
                    "conteudo_nome": s.conteudo.nome,
                    "disciplina_nome": s.conteudo.disciplina.nome,
                })
        else:
            modo = "selecao"

    hoje = timezone.localdate()

    # Dados do Cronograma de Estudos
    cronograma_itens = list(
        CronogramaEstudoItem.objects.filter(perfil=perfil).order_by("dia_semana", "horario_inicio", "ordem")
    )
    cronograma_itens_json = json.dumps([
        {
            "id": item.id,
            "dia_semana": item.dia_semana,
            "horario_inicio": item.horario_inicio,
            "horario_fim": item.horario_fim,
            "disciplina_nome": item.disciplina_nome,
            "cor": item.cor,
            "observacoes": item.observacoes,
            "ordem": item.ordem,
        }
        for item in cronograma_itens
    ], ensure_ascii=False)

    # Dados da Agenda Acadêmica
    eventos_proximos = list(
        EventoAgenda.objects.filter(perfil=perfil, data__gte=hoje).order_by("data", "horario")[:10]
    )
    for ev in eventos_proximos:
        dias = (ev.data - hoje).days
        ev.dias_faltando = dias
        ev.e_hoje = (dias == 0)
        ev.e_amanha = (dias == 1)

    # Dados das Semanas de Provas
    semanas_provas_qs = SemanaProva.objects.filter(perfil=perfil).prefetch_related("avaliacoes").order_by("-data_inicio")
    semanas_provas = []
    todas_avaliacoes_futuras = []

    for sp in semanas_provas_qs:
        av_list = []
        for av in sp.avaliacoes.all().order_by("data", "horario"):
            dias = (av.data - hoje).days
            av.dias_faltando = dias
            av.dias_faltam = dias
            av.passou = (dias < 0)
            av.e_hoje = (dias == 0)
            av.e_amanha = (dias == 1)
            av_list.append(av)
            if dias >= 0:
                todas_avaliacoes_futuras.append(av)
        sp.avaliacoes_processadas = av_list
        semanas_provas.append(sp)

    todas_avaliacoes_futuras.sort(key=lambda x: (x.data, x.horario or datetime.time(23, 59)))
    proxima_avaliacao = todas_avaliacoes_futuras[0] if todas_avaliacoes_futuras else None

    disciplinas_json = json.dumps([d.nome for d in disciplinas_todas])

    context = {
        "perfil": perfil,
        "disciplinas": disciplinas,
        "conteudos": conteudos,
        "conteudo_selecionado": conteudo_selecionado,
        "disciplina_selecionada": disciplina_selecionada,
        "modo": modo,
        "secao": secao,
        "questao_atual": questao_atual,
        "questao_index": questao_index,
        "total_questoes": total_questoes,
        "sessao_id": sessao_id,
        "resultado": resultado,
        "historico": historico,
        "feedback": feedback,
        "cronograma_itens": cronograma_itens,
        "cronograma_itens_json": cronograma_itens_json,
        "disciplinas_json": disciplinas_json,
        "eventos_proximos": eventos_proximos,
        "semanas_provas": semanas_provas,
        "proxima_avaliacao": proxima_avaliacao,
        "hoje": hoje,
        "hoje_str": hoje.strftime("%Y-%m-%d"),
    }

    return render(request, "recuperaifpi.html", context)


@login_required
def recuperaifpi_responder(request):
    """Processa a resposta de uma questão no RecuperaIFPI."""
    if request.method != "POST":
        return redirect("recuperaifpi")

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        messages.error(request, "Acesso restrito para alunos do IFPI.")
        return redirect("recuperaifpi")

    questao_id = request.POST.get("questao_id")
    alternativa_id = request.POST.get("alternativa")
    sessao_id = request.POST.get("sessao_id")
    conteudo_id = request.POST.get("conteudo_id")
    disciplina_id = request.POST.get("disciplina_id")
    questao_index = request.POST.get("questao_index", "0")

    # Validar campos obrigatórios
    if not all([questao_id, alternativa_id, sessao_id, conteudo_id]):
        messages.error(request, "Dados incompletos. Tente novamente.")
        return redirect("recuperaifpi")

    try:
        questao_id = int(questao_id)
        alternativa_id = int(alternativa_id)
        sessao_id = int(sessao_id)
        conteudo_id = int(conteudo_id)
        questao_index = int(questao_index)
    except (ValueError, TypeError):
        messages.error(request, "Dados inválidos. Tente novamente.")
        return redirect("recuperaifpi")

    # Validar que a sessão pertence ao usuário e está ativa
    try:
        sessao = SessaoRecuperacao.objects.get(
            id=sessao_id, perfil=perfil, finalizada=False
        )
    except SessaoRecuperacao.DoesNotExist:
        messages.error(request, "Sessão de recuperação não encontrada ou já finalizada.")
        return redirect("recuperaifpi")

    # Validar questão e alternativa
    try:
        questao = Questao.objects.get(id=questao_id, conteudo_id=conteudo_id)
    except Questao.DoesNotExist:
        messages.error(request, "Questão não encontrada.")
        return redirect("recuperaifpi")

    try:
        alternativa = Alternativa.objects.get(id=alternativa_id, questao=questao)
    except Alternativa.DoesNotExist:
        messages.error(request, "Alternativa inválida para esta questão.")
        return redirect("recuperaifpi")

    # Verificar se já respondeu esta questão NESTA sessão (anti-duplicação)
    # Usamos a session do Django para rastrear questões respondidas nesta sessão
    chave_sessao = f"recupera_respondidas_{sessao_id}"
    respondidas = request.session.get(chave_sessao, [])

    if questao_id in respondidas:
        # Já respondida nesta sessão, avançar sem registrar novamente
        from urllib.parse import urlencode
        params = urlencode({
            "modo": "atividade",
            "conteudo": conteudo_id,
            "disciplina": disciplina_id or "",
            "sessao_id": sessao_id,
            "questao_index": questao_index + 1,
        })
        return redirect(f"/auth/recuperaifpi/?{params}")

    # RecuperaIFPI é modo de treino: não concede XP nem altera conquistas/ranking
    xp_ganho = 0

    # Atualizar sessão de recuperação
    if alternativa.e_correta:
        sessao.acertos += 1
    else:
        sessao.erros += 1
    sessao.xp_ganho = 0
    sessao.save(update_fields=["acertos", "erros", "xp_ganho"])

    # Marcar como respondida nesta sessão
    respondidas.append(questao_id)
    request.session[chave_sessao] = respondidas

    # Obter alternativa correta para o feedback
    alternativa_correta = Alternativa.objects.filter(
        questao=questao, e_correta=True
    ).first()

    # Guardar feedback na sessão (treino sem pontuação de XP)
    request.session["recupera_feedback"] = {
        "sessao_id": sessao_id,
        "acertou": alternativa.e_correta,
        "alternativa_escolhida_id": alternativa.id,
        "alternativa_correta_id": alternativa_correta.id if alternativa_correta else None,
        "alternativa_correta_letra": alternativa_correta.letra if alternativa_correta else "?",
        "xp_ganho": 0,
        "numero_tentativa": 1,
    }

    # Redirecionar de volta para a mesma questão (mostrando feedback) usando POST-Redirect-GET
    from urllib.parse import urlencode
    params = urlencode({
        "modo": "atividade",
        "conteudo": conteudo_id,
        "disciplina": disciplina_id or "",
        "sessao_id": sessao_id,
        "questao_index": questao_index,
    })
    return redirect(f"/auth/recuperaifpi/?{params}")


@login_required
def recuperaifpi_conteudos_api(request):
    """API endpoint para filtrar conteúdos por disciplina via AJAX."""
    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"error": "Acesso negado"}, status=403)

    disciplina_id = request.GET.get("disciplina_id", "")
    if disciplina_id:
        try:
            conteudos = Conteudo.objects.filter(
                disciplina_id=int(disciplina_id)
            ).order_by("nome")
        except (ValueError, TypeError):
            conteudos = Conteudo.objects.none()
    else:
        conteudos = Conteudo.objects.all().order_by("nome")

    data = [{"id": c.id, "nome": c.nome} for c in conteudos]
    return JsonResponse(data, safe=False)


# ==============================================================================
# RECUPERA IFPI — CRONOGRAMA DE ESTUDOS API
# ==============================================================================

@login_required
def recuperaifpi_cronograma_salvar(request):
    """Salva a grade semanal completa de estudos via AJAX POST."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    try:
        dados = json.loads(request.body.decode("utf-8"))
        itens_data = dados.get("itens", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Formato de dados JSON inválido"}, status=400)

    novos_itens = []
    for idx, item in enumerate(itens_data):
        dia_semana = int(item.get("dia_semana", 0))
        horario_inicio = str(item.get("horario_inicio", "14:00"))[:10]
        horario_fim = str(item.get("horario_fim", "15:00"))[:10]
        disciplina_nome = str(item.get("disciplina_nome", "Geral")).strip()[:100]
        cor = str(item.get("cor", "#0056d6"))[:20]
        observacoes = str(item.get("observacoes", "")).strip()[:255]

        if disciplina_nome:
            novos_itens.append(
                CronogramaEstudoItem(
                    perfil=perfil,
                    dia_semana=dia_semana,
                    horario_inicio=horario_inicio,
                    horario_fim=horario_fim,
                    disciplina_nome=disciplina_nome,
                    cor=cor,
                    observacoes=observacoes,
                    ordem=idx,
                )
            )

    with transaction.atomic():
        CronogramaEstudoItem.objects.filter(perfil=perfil).delete()
        if novos_itens:
            CronogramaEstudoItem.objects.bulk_create(novos_itens)

    return JsonResponse({
        "sucesso": True, "ok": True,
        "mensagem": "Cronograma salvo com sucesso!",
        "total_itens": len(novos_itens),
    })


@login_required
def recuperaifpi_cronograma_limpar(request):
    """Limpa todas as sessões do cronograma de estudos do aluno."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    CronogramaEstudoItem.objects.filter(perfil=perfil).delete()
    return JsonResponse({"sucesso": True, "ok": True, "mensagem": "Cronograma limpo com sucesso!"})


# ==============================================================================
# RECUPERA IFPI — AGENDA ACADÊMICA & SEMANAS DE PROVAS API
# ==============================================================================

@login_required
def recuperaifpi_agenda_eventos_api(request):
    """Retorna eventos e avaliações de provas para um mês/ano específico via JSON."""
    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    try:
        ano = int(request.GET.get("ano", timezone.localdate().year))
        mes = int(request.GET.get("mes", timezone.localdate().month))
    except (ValueError, TypeError):
        hoje = timezone.localdate()
        ano = hoje.year
        mes = hoje.month

    # Buscar eventos cadastrados na Agenda
    eventos_qs = EventoAgenda.objects.filter(
        perfil=perfil, data__year=ano, data__month=mes
    ).order_by("data", "horario")

    eventos = []
    for ev in eventos_qs:
        eventos.append({
            "id": ev.id,
            "tipo": "evento",
            "titulo": ev.titulo,
            "data": ev.data.strftime("%Y-%m-%d"),
            "dia": ev.data.day,
            "horario": ev.horario.strftime("%H:%M") if ev.horario else "",
            "descricao": ev.descricao,
            "categoria": ev.categoria,
            "categoria_display": ev.get_categoria_display(),
            "categoria_label": ev.get_categoria_display(),
            "cor": ev.cor,
            "concluido": ev.concluido,
        })

    # Buscar avaliações de Semanas de Provas no mesmo mês
    avaliacoes_qs = AvaliacaoSemanaProva.objects.filter(
        semana_prova__perfil=perfil, data__year=ano, data__month=mes
    ).select_related("semana_prova").order_by("data", "horario")

    for av in avaliacoes_qs:
        eventos.append({
            "id": av.id,
            "tipo": "avaliacao",
            "titulo": f"Prova: {av.disciplina_nome}",
            "data": av.data.strftime("%Y-%m-%d"),
            "dia": av.data.day,
            "horario": av.horario.strftime("%H:%M") if av.horario else "",
            "descricao": f"Período: {av.semana_prova.nome}\nConteúdo: {av.conteudo}" + (f"\nObs: {av.observacoes}" if av.observacoes else ""),
            "categoria": "avaliacao",
            "categoria_display": "Avaliacao",
            "categoria_label": "Avaliacao",
            "cor": "#dc2626",
            "concluido": False,
            "conteudo": av.conteudo,
            "semana_nome": av.semana_prova.nome,
        })

    return JsonResponse({"sucesso": True, "ok": True, "ano": ano, "mes": mes, "eventos": eventos})


@login_required

def _obter_dados_recupera(request):
    """Auxiliar para ler dados tanto de JSON body quanto de POST form-encoded."""
    if request.content_type == "application/json" or (request.body and request.body.strip().startswith(b"{")):
        try:
            return json.loads(request.body.decode("utf-8"))
        except Exception:
            pass
    return request.POST

def recuperaifpi_evento_criar(request):
    """Cria um novo compromisso na Agenda Acadêmica."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    titulo = dados.get("titulo", "").strip()
    data_str = dados.get("data", "").strip()
    horario_str = dados.get("horario", "").strip()
    descricao = dados.get("descricao", "").strip()
    categoria = dados.get("categoria", "outros").strip()
    cor = dados.get("cor", "#0056d6").strip()

    if not titulo or not data_str:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Título e Data são obrigatórios"}, status=400)

    try:
        data_obj = datetime.datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Data em formato inválido"}, status=400)

    horario_obj = None
    if horario_str:
        try:
            horario_obj = datetime.datetime.strptime(horario_str, "%H:%M").time()
        except ValueError:
            pass

    evento = EventoAgenda.objects.create(
        perfil=perfil,
        titulo=titulo,
        data=data_obj,
        horario=horario_obj,
        descricao=descricao,
        categoria=categoria,
        cor=cor,
    )

    return JsonResponse({
        "sucesso": True, "ok": True,
        "mensagem": "Compromisso adicionado com sucesso!",
        "evento": {
            "id": evento.id,
            "titulo": evento.titulo,
            "data": evento.data.strftime("%Y-%m-%d"),
            "horario": evento.horario.strftime("%H:%M") if evento.horario else "",
            "categoria": evento.categoria,
            "categoria_display": evento.get_categoria_display(),
            "descricao": evento.descricao,
            "cor": evento.cor,
        }
    })


@login_required
def recuperaifpi_evento_editar(request):
    """Edita um compromisso existente na Agenda Acadêmica."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    evento_id = dados.get("evento_id") or dados.get("id")
    evento = get_object_or_404(EventoAgenda, id=evento_id, perfil=perfil)

    titulo = dados.get("titulo", "").strip()
    data_str = dados.get("data", "").strip()
    horario_str = dados.get("horario", "").strip()
    descricao = dados.get("descricao", "").strip()
    categoria = dados.get("categoria", evento.categoria).strip()
    cor = dados.get("cor", evento.cor).strip()

    if not titulo or not data_str:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Título e Data são obrigatórios"}, status=400)

    try:
        evento.data = datetime.datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Data em formato inválido"}, status=400)

    if horario_str:
        try:
            evento.horario = datetime.datetime.strptime(horario_str, "%H:%M").time()
        except ValueError:
            evento.horario = None
    else:
        evento.horario = None

    evento.titulo = titulo
    evento.descricao = descricao
    evento.categoria = categoria
    evento.cor = cor
    evento.save()

    return JsonResponse({
        "sucesso": True, "ok": True,
        "mensagem": "Compromisso atualizado com sucesso!",
        "evento": {
            "id": evento.id,
            "titulo": evento.titulo,
            "data": evento.data.strftime("%Y-%m-%d"),
            "horario": evento.horario.strftime("%H:%M") if evento.horario else "",
            "categoria": evento.categoria,
            "categoria_display": evento.get_categoria_display(),
            "descricao": evento.descricao,
            "cor": evento.cor,
        }
    })


@login_required
def recuperaifpi_evento_excluir(request):
    """Exclui um compromisso da Agenda Acadêmica."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    evento_id = dados.get("evento_id") or dados.get("id")
    evento = get_object_or_404(EventoAgenda, id=evento_id, perfil=perfil)
    evento.delete()

    return JsonResponse({"sucesso": True, "ok": True, "mensagem": "Compromisso excluído com sucesso!"})


@login_required
def recuperaifpi_evento_concluir(request):
    """Alterna o status de concluído de um evento."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    evento_id = dados.get("evento_id") or dados.get("id")
    evento = get_object_or_404(EventoAgenda, id=evento_id, perfil=perfil)
    evento.concluido = not evento.concluido
    evento.save(update_fields=["concluido"])

    return JsonResponse({"sucesso": True, "ok": True, "concluido": evento.concluido})


@login_required
def recuperaifpi_semana_criar(request):
    """Cria um novo período de Semana de Provas."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    nome = dados.get("nome", "").strip()
    data_inicio_str = dados.get("data_inicio", "").strip()
    data_fim_str = dados.get("data_fim", "").strip()

    if not nome or not data_inicio_str or not data_fim_str:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Nome, Data de Início e Data de Término são obrigatórios"}, status=400)

    try:
        data_inicio = datetime.datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
        data_fim = datetime.datetime.strptime(data_fim_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Datas em formato inválido"}, status=400)

    if data_fim < data_inicio:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "A data de término não pode ser anterior à data de início"}, status=400)

    semana = SemanaProva.objects.create(
        perfil=perfil,
        nome=nome,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    return JsonResponse({
        "sucesso": True, "ok": True,
        "mensagem": "Semana de Provas criada com sucesso!",
        "semana": {
            "id": semana.id,
            "nome": semana.nome,
            "data_inicio": semana.data_inicio.strftime("%d/%m/%Y"),
            "data_fim": semana.data_fim.strftime("%d/%m/%Y"),
        }
    })


@login_required
def recuperaifpi_semana_excluir(request):
    """Exclui uma Semana de Provas e todas as suas avaliações."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    semana_id = dados.get("semana_id") or dados.get("semana_prova_id")
    semana = get_object_or_404(SemanaProva, id=semana_id, perfil=perfil)
    semana.delete()

    return JsonResponse({"sucesso": True, "ok": True, "mensagem": "Semana de Provas excluída com sucesso!"})


@login_required
def recuperaifpi_avaliacao_criar(request):
    """Cadastra uma avaliação/prova dentro de uma Semana de Provas."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    semana_id = dados.get("semana_id") or dados.get("semana_prova_id")
    semana = get_object_or_404(SemanaProva, id=semana_id, perfil=perfil)

    disciplina_nome = dados.get("disciplina_nome", "").strip()
    data_str = dados.get("data", "").strip()
    horario_str = dados.get("horario", "").strip()
    conteudo = dados.get("conteudo", "").strip()
    observacoes = dados.get("observacoes", "").strip()

    if not disciplina_nome or not data_str or not conteudo:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Disciplina, Data e Conteúdo são obrigatórios"}, status=400)

    try:
        data_obj = datetime.datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Data em formato inválido"}, status=400)

    horario_obj = None
    if horario_str:
        try:
            horario_obj = datetime.datetime.strptime(horario_str, "%H:%M").time()
        except ValueError:
            pass

    avaliacao = AvaliacaoSemanaProva.objects.create(
        semana_prova=semana,
        disciplina_nome=disciplina_nome,
        data=data_obj,
        horario=horario_obj,
        conteudo=conteudo,
        observacoes=observacoes,
    )

    hoje = timezone.localdate()
    dias = (avaliacao.data - hoje).days

    return JsonResponse({
        "sucesso": True, "ok": True,
        "mensagem": "Avaliação adicionada com sucesso!",
        "avaliacao": {
            "id": avaliacao.id,
            "semana_id": semana.id,
            "disciplina_nome": avaliacao.disciplina_nome,
            "data": avaliacao.data.strftime("%Y-%m-%d"),
            "data_formatada": avaliacao.data.strftime("%d/%m/%Y"),
            "horario": avaliacao.horario.strftime("%H:%M") if avaliacao.horario else "",
            "conteudo": avaliacao.conteudo,
            "observacoes": avaliacao.observacoes,
            "dias_faltando": dias,
            "e_hoje": (dias == 0),
        }
    })


@login_required
def recuperaifpi_avaliacao_editar(request):
    """Edita uma avaliação dentro de uma Semana de Provas."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    avaliacao_id = dados.get("avaliacao_id") or dados.get("id")
    avaliacao = get_object_or_404(AvaliacaoSemanaProva, id=avaliacao_id, semana_prova__perfil=perfil)

    disciplina_nome = dados.get("disciplina_nome", "").strip()
    data_str = dados.get("data", "").strip()
    horario_str = dados.get("horario", "").strip()
    conteudo = dados.get("conteudo", "").strip()
    observacoes = dados.get("observacoes", "").strip()

    if not disciplina_nome or not data_str or not conteudo:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Disciplina, Data e Conteúdo são obrigatórios"}, status=400)

    try:
        avaliacao.data = datetime.datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Data em formato inválido"}, status=400)

    if horario_str:
        try:
            avaliacao.horario = datetime.datetime.strptime(horario_str, "%H:%M").time()
        except ValueError:
            avaliacao.horario = None
    else:
        avaliacao.horario = None

    avaliacao.disciplina_nome = disciplina_nome
    avaliacao.conteudo = conteudo
    avaliacao.observacoes = observacoes
    avaliacao.save()

    hoje = timezone.localdate()
    dias = (avaliacao.data - hoje).days

    return JsonResponse({
        "sucesso": True, "ok": True,
        "mensagem": "Avaliação atualizada com sucesso!",
        "avaliacao": {
            "id": avaliacao.id,
            "disciplina_nome": avaliacao.disciplina_nome,
            "data": avaliacao.data.strftime("%Y-%m-%d"),
            "data_formatada": avaliacao.data.strftime("%d/%m/%Y"),
            "horario": avaliacao.horario.strftime("%H:%M") if avaliacao.horario else "",
            "conteudo": avaliacao.conteudo,
            "observacoes": avaliacao.observacoes,
            "dias_faltando": dias,
            "e_hoje": (dias == 0),
        }
    })


@login_required
def recuperaifpi_avaliacao_excluir(request):
    """Exclui uma avaliação de uma Semana de Provas."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.select_related("escola").get(usuario=request.user)
    if not eh_estudante_ifpi(perfil):
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Acesso negado"}, status=403)

    dados = _obter_dados_recupera(request)

    avaliacao_id = dados.get("avaliacao_id") or dados.get("id")
    avaliacao = get_object_or_404(AvaliacaoSemanaProva, id=avaliacao_id, semana_prova__perfil=perfil)
    avaliacao.delete()

    return JsonResponse({"sucesso": True, "ok": True, "mensagem": "Avaliação excluída com sucesso!"})


@login_required
def alternar_tema_api(request):
    """Permite alternar o tema (claro/escuro) do usuário via AJAX instantâneo."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "ok": False, "erro": "Método não permitido"}, status=405)

    perfil = Perfil.objects.get(usuario=request.user)
    dados = _obter_dados_recupera(request)

    if "tema_escuro" in dados:
        val = dados.get("tema_escuro")
        tema_escuro = (val is True or val == "true" or val == "1" or val == 1)
    else:
        tema_escuro = not perfil.tema_escuro

    perfil.tema_escuro = tema_escuro
    perfil.save()

    return JsonResponse({
        "sucesso": True,
        "ok": True,
        "tema_escuro": perfil.tema_escuro,
        "tema": "dark" if perfil.tema_escuro else "light",
        "mensagem": "Tema atualizado com sucesso!"
    })
