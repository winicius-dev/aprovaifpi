from django.db import models
from django.contrib.auth.models import User


class Escola(models.Model):
    codigo_inep = models.CharField(max_length=20)
    nome = models.CharField(max_length=200)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=50)

    def __str__(self):
        return self.nome


class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=50)
    data_criacao = models.DateTimeField(auto_now_add=True)
    xp = models.IntegerField(default=0)
    avatar = models.ImageField(blank=True)
    escola = models.ForeignKey(Escola, on_delete=models.PROTECT)

    def __str__(self):
        return self.nome


class Disciplina(models.Model):
    nome = models.CharField(max_length=50)

    def __str__(self):
        return self.nome


class Conteudo(models.Model):
    nome = models.CharField(max_length=200)
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT)

    def __str__(self):
        return self.nome


class Questao(models.Model):
    id_original = models.CharField(max_length=50, unique=True, null=True, blank=True)
    enunciado = models.TextField()
    dificuldade = models.CharField(max_length=20)
    ano = models.IntegerField()
    conteudo = models.ForeignKey(Conteudo, on_delete=models.PROTECT)

    def __str__(self):
        return self.enunciado


class ImagemQuestao(models.Model):
    arquivo = models.ImageField(upload_to='questoes/')
    ordem = models.IntegerField()
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name='imagens')

    def __str__(self):
        return f"Imagem da questão {self.questao.id}"


class Alternativa(models.Model):
    letra = models.CharField(max_length=1)
    texto = models.TextField(blank=True)
    imagem = models.ImageField(upload_to='alternativas/', blank=True)
    e_correta = models.BooleanField()
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE)

    def __str__(self):
        return f"Alternativa da questão {self.questao.id}"


class TentativaQuestao(models.Model):
    xp_ganho = models.IntegerField()
    acertou = models.BooleanField()
    data_realizacao = models.DateTimeField(auto_now_add=True)
    numero_tentativa = models.IntegerField()
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE)
    questao = models.ForeignKey(Questao, on_delete=models.PROTECT)
    alternativa = models.ForeignKey(Alternativa, on_delete=models.PROTECT)

    def __str__(self):
        return f"Tentativa {self.numero_tentativa} - Questão {self.questao.id}"


class Conquista(models.Model):
    codigo = models.SlugField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255)
    requisito = models.CharField(max_length=255)
    xp_recompensa = models.IntegerField(default=0)
    ativa = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class ConquistaPerfil(models.Model):
    perfil = models.ForeignKey(
        Perfil,
        on_delete=models.CASCADE,
        related_name="conquistas"
    )
    conquista = models.ForeignKey(
        Conquista,
        on_delete=models.CASCADE,
        related_name="desbloqueios"
    )
    data_desbloqueio = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["perfil", "conquista"],
                name="unica_conquista_por_perfil"
            )
        ]
        ordering = ["data_desbloqueio"]

    def __str__(self):
        return f"{self.perfil.nome} - {self.conquista.nome}"