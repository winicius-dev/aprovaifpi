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
    ConquistaPerfil
)
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db import models
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Q, IntegerField
from django.db.models.functions import Coalesce




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


def desbloquear_conquista(perfil, codigo):
    conquista = Conquista.objects.filter(codigo=codigo, ativa=True).first()

    if conquista is None:
        return False

    _, criada = ConquistaPerfil.objects.get_or_create(perfil=perfil, conquista=conquista)

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