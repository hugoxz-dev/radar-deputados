"""Nomes legíveis das categorias da CEAP.

A Câmara publica as categorias em maiúsculas, às vezes com ponto final e
vírgula fora do lugar ("HOSPEDAGEM ,EXCETO DO PARLAMENTAR NO DISTRITO FEDERAL.").
No banco guardamos o texto original (é o que liga a nota à categoria);
para exibir, usamos estes nomes. Categoria nova que a Câmara criar cai no
tratamento genérico de `nome_categoria`.
"""

NOMES_AMIGAVEIS: dict[str, str] = {
    "divulgacao-da-atividade-parlamentar": "Divulgação da atividade parlamentar",
    "locacao-ou-fretamento-de-veiculos-automotores": "Locação de veículos",
    "passagem-aerea-sigepa": "Passagens aéreas (SIGEPA)",
    "manutencao-de-escritorio-de-apoio-a-atividade-parlamentar": "Manutenção de escritório",
    "combustiveis-e-lubrificantes": "Combustíveis e lubrificantes",
    "hospedagem-exceto-do-parlamentar-no-distrito-federal": "Hospedagem (fora do DF)",
    "locacao-ou-fretamento-de-aeronaves": "Fretamento de aeronaves",
    "telefonia": "Telefonia",
    "complementacao-do-auxilio-moradia": "Complementação do auxílio-moradia",
    "servico-de-seguranca-prestado-por-empresa-especializada": "Segurança privada",
    "servico-de-taxi-pedagio-e-estacionamento": "Táxi, pedágio e estacionamento",
    "passagem-aerea-reembolso": "Passagens aéreas (reembolso)",
    "fornecimento-de-alimentacao-do-parlamentar": "Alimentação",
    "passagem-aerea-rpa": "Passagens aéreas (RPA)",
    "locacao-ou-fretamento-de-embarcacoes": "Fretamento de embarcações",
    "passagens-terrestres-maritimas-ou-fluviais": "Passagens terrestres, marítimas ou fluviais",
    "servicos-postais": "Serviços postais",
    "assinatura-de-publicacoes": "Assinatura de publicações",
    "passagem-aerea-missao-oficial": "Passagens aéreas (missão oficial)",
    "participacao-em-curso-palestra-ou-evento-similar": "Cursos, palestras e eventos",
    "consultorias-pesquisas-e-trabalhos-tecnicos": "Consultorias e trabalhos técnicos",
    "aquisicao-de-tokens-e-certificados-digitais": "Certificados digitais",
}


def nome_categoria(slug: str, descricao: str) -> str:
    if slug in NOMES_AMIGAVEIS:
        return NOMES_AMIGAVEIS[slug]
    texto = descricao.strip().rstrip(".").replace(" ,", ", ").lower()
    return texto[:1].upper() + texto[1:]
