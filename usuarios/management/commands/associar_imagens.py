import re
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from usuarios.models import Questao, ImagemQuestao, Alternativa


EXTENSOES = r"(?:png|jpg|jpeg|webp)"


def normalizar_id(valor):
    return re.sub(r"^q", "", str(valor).strip(), flags=re.IGNORECASE)

class Command(BaseCommand):
    help = "Associa imagens existentes às questões e alternativas."

    def handle(self, *args, **options):
        pasta_questoes = Path(settings.MEDIA_ROOT) / "questoes"
        pasta_alternativas = Path(settings.MEDIA_ROOT) / "alternativas"

        if not pasta_questoes.exists():
            self.stdout.write(self.style.WARNING(
                f"Pasta não encontrada: {pasta_questoes}"
            ))
            return

        if not pasta_alternativas.exists():
            self.stdout.write(self.style.WARNING(
                f"Pasta não encontrada: {pasta_alternativas}"
            ))
            return

        questoes = {
            normalizar_id(q.id_original): q
            for q in Questao.objects.exclude(
                id_original__isnull=True
            ).exclude(id_original="")
        }

        associadas = 0
        ignoradas = 0

        padrao_enunciado = re.compile(
            rf"^q(.+?)_(\d+)\.({EXTENSOES})$",
            re.IGNORECASE,
        )

        for arquivo in pasta_questoes.iterdir():
            if not arquivo.is_file():
                continue

            correspondencia = padrao_enunciado.match(arquivo.name)
            if not correspondencia:
                continue

            id_original, ordem, _ = correspondencia.groups()
            questao = questoes.get(normalizar_id(id_original))

            if questao is None:
                self.stdout.write(
                    f"Questão não encontrada: {arquivo.name}"
                )
                ignoradas += 1
                continue

            ordem = int(ordem)

            imagem_existente = ImagemQuestao.objects.filter(
                questao=questao,
                ordem=ordem,
            ).first()

            if imagem_existente:
                self.stdout.write(
                    f"Já existe imagem na posição {ordem}: "
                    f"{arquivo.name}"
                )
                ignoradas += 1
                continue

            imagem = ImagemQuestao(
                questao=questao,
                ordem=ordem,
            )
            imagem.arquivo.name = f"questoes/{arquivo.name}"
            imagem.save()

            associadas += 1
            self.stdout.write(
                f"Enunciado associado: {arquivo.name}"
            )

        padrao_alternativa = re.compile(
            rf"^q(.+?)_([a-e])\.({EXTENSOES})$",
            re.IGNORECASE,
        )

        for arquivo in pasta_alternativas.iterdir():
            if not arquivo.is_file():
                continue

            correspondencia = padrao_alternativa.match(arquivo.name)
            if not correspondencia:
                continue

            id_original, letra, _ = correspondencia.groups()
            questao = questoes.get(normalizar_id(id_original))

            if questao is None:
                self.stdout.write(
                    f"Questão não encontrada: {arquivo.name}"
                )
                ignoradas += 1
                continue

            alternativa = Alternativa.objects.filter(
                questao=questao,
                letra__iexact=letra,
            ).first()

            if alternativa is None:
                self.stdout.write(
                    f"Alternativa {letra.upper()} não encontrada: "
                    f"{arquivo.name}"
                )
                ignoradas += 1
                continue

            if alternativa.imagem:
                self.stdout.write(
                    f"Alternativa já possui imagem: {arquivo.name}"
                )
                ignoradas += 1
                continue

            alternativa.imagem.name = f"alternativas/{arquivo.name}"
            alternativa.save(update_fields=["imagem"])

            associadas += 1
            self.stdout.write(
                f"Alternativa associada: {arquivo.name}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Concluído! Imagens associadas: {associadas}. "
            f"Itens ignorados: {ignoradas}."
        ))