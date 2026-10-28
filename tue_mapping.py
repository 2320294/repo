# Mapeamento normalizado de TUEs (Substitui ifs complexos em cadeia)
import re

MAPEAMENTO_TUES = [
    {
        "categoria": "chuveiros",
        "padroes": [r"chuve", r"torneira el[ée]trica", r"aquecedor de passagem", r"ferro el[ée]trico"]
    },
    {
        "categoria": "boiler",
        "padroes": [r"boiler", r"aquecedor central", r"acumula[çc][ãa]o"]
    },
    {
        "categoria": "eletrodomesticos",
        "padroes": [r"lava\s*e\s*seca", r"lavaseca", r"micro", r"forno", r"lava[-\s]lou[çc]a", r"secadora"]
    },
    {
        "categoria": "fogoes",
        "padroes": [r"fog[ãa]o", r"cooktop"]
    },
    {
        "categoria": "ar_condicionado",
        "padroes": [r"ar[-_\s]condicionado", r"split"]
    },
    {
        "categoria": "hidromassagem",
        "padroes": [r"hidromassagem", r"banheira el[ée]trica"]
    }
]

def classificar_tue(nome_tue):
    nome_lower = str(nome_tue or "").lower().strip()
    for grupo in MAPEAMENTO_TUES:
        for padrao in grupo["padroes"]:
            if re.search(padrao, nome_lower):
                return grupo["categoria"]
    return None
