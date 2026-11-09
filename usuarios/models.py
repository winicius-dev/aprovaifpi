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
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    escola = models.ForeignKey(Escola, on_delete=models.PROTECT)
    banner_1 = models.ForeignKey('Conquista', null=True, blank=True, on_delete=models.SET_NULL, related_name="perfil_banner_1")
    banner_2 = models.ForeignKey('Conquista', null=True, blank=True, on_delete=models.SET_NULL, related_name="perfil_banner_2")
    tema_escuro = models.BooleanField(default=False, verbose_name="Tema Escuro Ativado")

    def __str__(self):
        return self.nome

    def get_banners_equipados(self):
        """Retorna até 2 banners equipados garantindo mérito em ConquistaPerfil."""
        desbloqueadas_ids = set(self.conquistas.values_list("conquista_id", flat=True))
        banners = []
        if self.banner_1 and self.banner_1.id in desbloqueadas_ids and self.banner_1.ativa:
            banners.append(self.banner_1)
        if self.banner_2 and self.banner_2.id in desbloqueadas_ids and self.banner_2.ativa and (self.banner_2 != self.banner_1):
            banners.append(self.banner_2)
        return banners


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


class SessaoRecuperacao(models.Model):
    """Sessão de atividade de recuperação no RecuperaIFPI."""
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="sessoes_recuperacao")
    conteudo = models.ForeignKey(Conteudo, on_delete=models.PROTECT)
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    total_questoes = models.IntegerField(default=0)
    acertos = models.IntegerField(default=0)
    erros = models.IntegerField(default=0)
    xp_ganho = models.IntegerField(default=0)
    finalizada = models.BooleanField(default=False)

    class Meta:
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"Sessão {self.id} - {self.perfil.nome} - {self.conteudo.nome}"

    @property
    def percentual(self):
        if self.total_questoes == 0:
            return 0
        return round(self.acertos / self.total_questoes * 100, 1)


class CronogramaEstudoItem(models.Model):
    """Sessão de estudo semanal no cronograma interativo."""
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="cronograma_itens")
    dia_semana = models.IntegerField(help_text="0=Segunda, 1=Terça, 2=Quarta, 3=Quinta, 4=Sexta, 5=Sábado, 6=Domingo")
    horario_inicio = models.CharField(max_length=10, default="14:00")
    horario_fim = models.CharField(max_length=10, default="15:00")
    disciplina_nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=20, default="#0056d6")
    observacoes = models.CharField(max_length=255, blank=True, default="")
    ordem = models.IntegerField(default=0)

    class Meta:
        ordering = ["dia_semana", "horario_inicio", "ordem"]

    def __str__(self):
        return f"{self.perfil.nome} - Dia {self.dia_semana}: {self.disciplina_nome} ({self.horario_inicio}-{self.horario_fim})"


class EventoAgenda(models.Model):
    """Compromisso pessoal na Agenda Acadêmica."""
    CATEGORIAS = [
        ("provas", "Provas"),
        ("trabalhos", "Trabalhos"),
        ("atividades", "Atividades"),
        ("eventos", "Eventos escolares"),
        ("palestras", "Palestras"),
        ("lembretes", "Lembretes"),
        ("outros", "Outros"),
    ]

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="eventos_agenda")
    titulo = models.CharField(max_length=150)
    data = models.DateField()
    horario = models.TimeField(null=True, blank=True)
    descricao = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default="outros")
    cor = models.CharField(max_length=20, default="#0056d6")
    concluido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data", "horario"]

    def __str__(self):
        return f"{self.titulo} - {self.data} ({self.perfil.nome})"


class SemanaProva(models.Model):
    """Período de semana de provas."""
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="semanas_provas")
    nome = models.CharField(max_length=150, help_text="Ex: Provas do 1º Bimestre")
    data_inicio = models.DateField()
    data_fim = models.DateField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"{self.nome} ({self.data_inicio} até {self.data_fim})"


class AvaliacaoSemanaProva(models.Model):
    """Avaliação individual dentro de uma semana de provas."""
    semana_prova = models.ForeignKey(SemanaProva, on_delete=models.CASCADE, related_name="avaliacoes")
    disciplina_nome = models.CharField(max_length=100)
    data = models.DateField()
    horario = models.TimeField(null=True, blank=True)
    conteudo = models.TextField(help_text="Conteúdo que será cobrado")
    observacoes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["data", "horario"]

    def __str__(self):
        return f"{self.disciplina_nome} - {self.data} ({self.semana_prova.nome})"
