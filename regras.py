# Regras do buscador THS Ofertas. Todos os valores em reais.

# Lojas que nunca entram (o Thiago não compra delas).
LOJAS_BLOQUEADAS = ["shopee", "aliexpress", "temu", "shein"]

# Celular e eletrônicos de giro rápido: lucro mínimo sobre o preço pago.
MARGEM_MIN = 0.25
# Notebook gira devagar: só se der pelo menos este lucro em reais.
LUCRO_MIN_NOTEBOOK = 600
# Acessório: a oferta tem que sair pelo menos 10% abaixo do custo do fornecedor.
DESCONTO_MIN_ACESSORIO = 0.10

# Como o robô descobre a categoria pelo nome do produto (ordem importa).
CATEGORIAS = [
    ("acessorio", ["cabo", "carregador", "fone", "earbuds", "buds", "mouse", "teclado",
                   "pelicula", "capa", "capinha", "fonte", "adaptador", "power bank",
                   "powerbank", "suporte", "headset", "pendrive", "cartao de memoria"]),
    ("notebook", ["notebook", "laptop", "macbook", "chromebook"]),
    ("celular", ["smartphone", "celular", "iphone", "galaxy", "moto ", "motorola",
                 "xiaomi", "redmi", "poco", "realme"]),
]

# Modelos para vigiar mesmo que não estejam no GestãoClick.
# termos: todos precisam aparecer no anúncio. preco_max: avisa abaixo disso.
# venda: quanto o Thiago vende na loja (None se ainda não definido).
LISTA_EXTRA = [
    {"nome": "Moto G35 5G 256 GB", "termos": ["g35", "256"], "preco_max": 899, "venda": 1250},
    {"nome": "Galaxy A36 5G 128 GB", "termos": ["a36", "128"], "preco_max": 1239, "venda": None},
    {"nome": "iPhone 16e 128 GB", "termos": ["iphone 16e", "128"], "preco_max": 3129, "venda": None},
    {"nome": "Echo Dot", "termos": ["echo dot"], "preco_max": 289, "venda": 450},
    {"nome": "Cafeteira Philips Walita EP1220", "termos": ["ep1220"], "preco_max": 1918, "venda": None},
]

# Modelos que o Thiago não coloca na loja.
IGNORAR = ["galaxy a07"]

# Palavras que acendem o alerta de risco no anúncio.
PALAVRAS_RISCO = ["usado", "seminovo", "vitrine", "recondicionado", "reembalado",
                  "open box", "internacional", "versao global", "importado", "sem nota"]
