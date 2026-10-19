import csv
import re
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from usuarios.models import Disciplina, Conteudo, Questao, Alternativa

class Command(BaseCommand):
    help = "Importa questões de um arquivo CSV do Google Planilhas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            default="questoes.csv",
            help="Caminho do arquivo CSV."
        )

    def handle(self, *args, **options):
        caminho = Path(options["arquivo"])

        if not caminho.is_absolute():
            caminho = Path.cwd() / caminho

        if not caminho.exists():
            raise CommandError(f"Arquivo não encontrado: {caminho}")

        try:
            with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
                amostra = arquivo.read(8192)
                arquivo.seek(0)

                try:
                    delimitador = csv.Sniffer().sniff(
                        amostra, delimiters=";,\t"
                    ).delimiter
                except csv.Error:
                    delimitador = ","

                leitor = csv.DictReader(arquivo, delimiter=delimitador)

                colunas_obrigatorias = {
                    "ID da Questão",
                    "Ano/Edição da Prova",
                    "Disciplina",
                    "Assunto Principal",
                    "Enunciado",
                    "Texto Alternativa A",
                    "Alternativa B",
                    "Alternativa C",
                    "Alternativa D",
                    "Alternativa E",
                    "Gabarito Correto",
                    "Nível de Dificuldade",
                }

                if not leitor.fieldnames:
                    raise CommandError("O CSV nao possui cabeçalho.")

                cabecalhos = {
                    nome.strip().lstrip("\ufeff")
                    for nome in leitor.fieldnames
                    if nome
                }

                faltantes = colunas_obrigatorias - cabecalhos

                if faltantes:
                    raise CommandError(
                        "Colunas ausentes no CSV: "
                        + ", ".join(sorted(faltantes))
                    )

                criadas = 0
                ignoradas = 0
                erros = []

                for numero_linha, linha in enumerate(leitor, start=2):
                    try:
                        with transaction.atomic():
                            dados = {
                                chave.strip().lstrip("\ufeff"): (
                                    valor.strip()
                                    if valor is not None
                                    else ""
                                )
                                for chave, valor in linha.items()
                                if chave is not None
                            }

                            id_original = dados["ID da Questão"]
                            ano_texto = dados["Ano/Edição da Prova"]
                            disciplina_nome = dados["Disciplina"]
                            conteudo_nome = dados["Assunto Principal"]
                            enunciado = dados["Enunciado"]
                            dificuldade = dados["Nível de Dificuldade"]
                            gabarito = dados["Gabarito Correto"].strip().upper()

                            if not id_original:
                                raise ValueError("ID da Questão vazio.")

                            if not ano_texto.isdigit():
                                raise ValueError(
                                    f"Ano inválido: {ano_texto!r}. "
                                    "Por enquanto, informe apenas o ano."
                                )

                            if not disciplina_nome or not conteudo_nome:
                                raise ValueError(
                                    "Disciplina e assunto são obrigatórios."
                                )

                            if not enunciado:
                                raise ValueError("Enunciado vazio.")

                            if dificuldade.lower() not in {
                                "fácil", "facil", "médio", "medio", "difícil",
                                "dificil", "fácil", "medio", "média", "media",
                                "difícil", "dificil"
                            }:
                                raise ValueError(
                                    f"Nível de dificuldade inválido: {dificuldade!r}."
                                )

                            if gabarito not in {"A", "B", "C", "D", "E"}:
                                raise ValueError(
                                    f"Gabarito inválido: {gabarito!r}."
                                )

                            if Questao.objects.filter(id_original=id_original).exists():
                                ignoradas += 1
                                continue

                            alternativas = {}
                            for letra in "ABCDE":
                                coluna = (
                                    "Texto Alternativa A"
                                    if letra == "A"
                                    else f"Alternativa {letra}"
                                )
                                texto = dados.get(coluna, "").strip()

                                texto = re.sub(
                                    rf"^\s*{letra.lower()}\)\s*",
                                    "",
                                    texto,
                                    flags=re.IGNORECASE
                                )

                                if not texto:
                                    raise ValueError(
                                        f"Alternativa {letra} vazia."
                                    )

                                alternativas[letra] = texto

                            disciplina, _ = Disciplina.objects.get_or_create(
                                nome=disciplina_nome
                            )

                            conteudo, _ = Conteudo.objects.get_or_create(
                                nome=conteudo_nome,
                                disciplina=disciplina
                            )

                            questao = Questao.objects.create(
                                id_original=id_original,
                                ano=int(ano_texto),
                                dificuldade=dificuldade,
                                enunciado=enunciado,
                                conteudo=conteudo
                            )

                            for letra, texto in alternativas.items():
                                Alternativa.objects.create(
                                    questao=questao,
                                    letra=letra,
                                    texto=texto,
                                    e_correta=(letra == gabarito)
                                )

                            criadas += 1

                    except Exception as erro:
                        erros.append(
                            f"Linha {numero_linha} "
                            f"(ID {linha.get('ID da Questão', '?')}): {erro}"
                        )

        except UnicodeDecodeError as erro:
            raise CommandError(
                "Nao foi possível ler o CSV como UTF-8. "
                "Exporte novamente pelo Google Planilhas."
            ) from erro

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluida. criadas: {criadas}; "
                f"ignoradas pq ja existem: {ignoradas}; "
                f"com erro: {len(erros)}."
            )
        )

        for erro in erros:
            self.stderr.write(self.style.ERROR(erro))