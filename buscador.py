"""Buscador THS Ofertas.

Lê os canais de ofertas que o Thiago segue no Telegram, cruza com o custo e o
preço de venda do GestãoClick e manda no robô @thsofertas_bot só o que compensa.
"""
import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

import regras

ARQ_ESTADO = "estado.json"
GESTAOCLICK_URL = os.environ.get("GESTAOCLICK_URL", "https://api.beteltecnologia.com")
CORES = {"preto", "preta", "branco", "branca", "azul", "verde", "rosa", "cinza", "prata",
         "dourado", "grafite", "lilas", "roxo", "vermelho", "amarelo", "laranja", "black",
         "white", "blue", "green", "pink", "gray", "grey", "silver", "gold", "titanio"}
MARCAS = {"samsung", "motorola", "moto", "apple", "xiaomi", "redmi", "galaxy", "jbl",
          "dell", "lenovo", "acer", "asus", "hp", "positivo", "philips", "walita", "amazon",
          "realme", "poco", "sony", "lg", "multilaser", "baseus", "anker", "ugreen"}
PALAVRAS_VAZIAS = {"de", "da", "do", "com", "e", "para", "smartphone", "celular", "cor",
                   "tela", "camera", "dual", "chip", "sim", "ram", "memoria", "interna",
                   "lancamento", "novo", "original", "-", "+"}
LOJAS = [
    ("Amazon", ["amazon.com.br", "amzn.to", "amzn.com"]),
    ("Mercado Livre", ["mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com", "meli.la"]),
    ("Magalu", ["magazineluiza.com.br", "magalu.com", "maga.lu"]),
    ("KaBuM", ["kabum.com.br"]),
    ("Casas Bahia", ["casasbahia.com.br"]),
    ("Ponto", ["pontofrio.com.br", "pontofrio.com"]),
    ("Extra", ["extra.com.br"]),
    ("Carrefour", ["carrefour.com.br"]),
    ("Americanas", ["americanas.com.br"]),
    ("Fast Shop", ["fastshop.com.br"]),
    ("Samsung", ["samsung.com"]),
    ("Apple", ["apple.com"]),
    ("Motorola", ["motorola.com"]),
    ("Xiaomi", ["mi.com", "xiaomi.com"]),
    ("Girafa", ["girafa.com.br"]),
    ("Shopee", ["shopee.com.br", "shope.ee", "shopee.com"]),
    ("AliExpress", ["aliexpress.com", "s.click.aliexpress.com", "a.aliexpress.com"]),
    ("Temu", ["temu.com"]),
    ("Shein", ["shein.com"]),
]


# ---------------------------------------------------------------- utilidades
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    texto = texto.lower()
    texto = re.sub(r"(\d+)\s*(gb|tb)\b", r"\1\2", texto)
    texto = re.sub(r"[^a-z0-9+ ]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def numero(valor):
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")  # R$ 3.100 = três mil e cem
    try:
        return float(s)
    except ValueError:
        return 0.0


def reais(valor):
    s = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def carregar_estado():
    try:
        with open(ARQ_ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def salvar_estado(estado):
    with open(ARQ_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False)


# ---------------------------------------------------------------- leitura do anúncio
RE_PARCELA = re.compile(r"(\d{1,2})\s*x\s*(de\s*)?r\$\s*[\d.,]+", re.I)
RE_PRECO = re.compile(r"r\$\s*([\d.]+(?:,\d{1,2})?)", re.I)
RE_SEM_JUROS = re.compile(r"(\d{1,2})\s*x\s*sem\s*juros", re.I)


def extrair_preco(texto):
    """Menor preço do anúncio, ignorando o valor das parcelas."""
    sem_parcelas = RE_PARCELA.sub(" ", texto)
    precos = [numero(p) for p in RE_PRECO.findall(sem_parcelas)]
    precos = [p for p in precos if p >= 10]
    return min(precos) if precos else None


def extrair_parcelas(texto):
    m = RE_SEM_JUROS.search(texto)
    return int(m.group(1)) if m else None


def identificar_loja(url):
    dominio = urlparse(url).netloc.lower()
    for nome, dominios in LOJAS:
        if any(dominio == d or dominio.endswith("." + d) for d in dominios):
            return nome
    return None


def resolver_link(url):
    """Segue links encurtados até a loja de verdade."""
    try:
        r = requests.get(url, allow_redirects=True, timeout=10, stream=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.close()
        return r.url
    except requests.RequestException:
        return url


def loja_bloqueada(loja):
    return bool(loja) and any(b in loja.lower().replace(" ", "") for b in regras.LOJAS_BLOQUEADAS)


def riscos(texto):
    t = normalizar(texto)
    return [p for p in regras.PALAVRAS_RISCO if p in t]


# ---------------------------------------------------------------- comparação com o estoque
def categoria(nome):
    n = " " + normalizar(nome) + " "
    for cat, palavras in regras.CATEGORIAS:
        if any(p in n for p in palavras):
            return cat
    return "outros"


def tokens_produto(nome):
    """Separa as palavras obrigatórias (modelo, memória) das opcionais."""
    obrigatorios, opcionais = [], []
    for tok in normalizar(nome).split():
        if tok in PALAVRAS_VAZIAS:
            continue
        tem_digito = any(c.isdigit() for c in tok)
        ram = re.fullmatch(r"(\d+)gb", tok) and int(tok[:-2]) <= 16
        if tok in CORES or ram or len(tok) > 7 or tok == "5g" or tok == "4g":
            opcionais.append(tok)
        elif tem_digito:
            obrigatorios.append(tok)
        else:
            opcionais.append(tok)
    return obrigatorios, opcionais


def nota_combinacao(produto, palavras_anuncio):
    obrig, opc = produto["_tokens"]
    if not obrig:
        return 0.0
    if not all(t in palavras_anuncio for t in obrig):
        return 0.0
    if not opc:
        return 1.0
    principais = [t for t in opc if t not in CORES and t not in MARCAS
                  and not re.fullmatch(r"\d+gb", t) and t not in ("5g", "4g")]
    if not principais:
        return 1.0
    return sum(t in palavras_anuncio for t in principais) / len(principais)


def achar_produto(texto, produtos):
    palavras = set(normalizar(texto).split())
    melhor, melhor_nota = None, 0.0
    for p in produtos:
        nota = nota_combinacao(p, palavras)
        if nota > melhor_nota or (nota == melhor_nota and melhor and
                                  len(p["_tokens"][0]) > len(melhor["_tokens"][0])):
            melhor, melhor_nota = p, nota
    return melhor if melhor_nota >= 0.6 else None


def preparar_produtos(produtos):
    for p in produtos:
        p["_tokens"] = tokens_produto(p["nome"])
        p["categoria"] = categoria(p["nome"])
    return produtos


def avaliar_estoque(produto, preco):
    """Decide se a oferta compensa comparando com o GestãoClick."""
    custo, venda, cat = produto["custo"], produto["venda"], produto["categoria"]
    referencia = custo or venda
    if not referencia or preco < referencia * 0.4 or (venda and preco > venda * 1.3):
        return None  # preço fora de faixa: provavelmente outro produto (capa, peça etc.)
    lucro = venda - preco if venda else None
    pct = lucro / preco if lucro is not None else None
    if cat == "acessorio":
        if custo and preco <= custo * (1 - regras.DESCONTO_MIN_ACESSORIO):
            return "COMPRA", f"{(1 - preco / custo) * 100:.0f}% abaixo do custo do seu fornecedor", lucro, pct
        return None
    if cat == "notebook":
        if lucro is not None and lucro >= regras.LUCRO_MIN_NOTEBOOK:
            return "COMPRA", f"lucro de {reais(lucro)} no notebook", lucro, pct
        return None
    if pct is not None and pct >= regras.MARGEM_MIN:
        return "COMPRA", f"margem de {pct * 100:.0f}%", lucro, pct
    if custo and preco < custo:
        return "ESTOQUE", f"{reais(custo - preco)} abaixo do que você pagou da última vez", lucro, pct
    return None


def avaliar_lista_extra(texto, preco):
    t = normalizar(texto)
    for item in regras.LISTA_EXTRA:
        if all(normalizar(termo) in t for termo in item["termos"]) and preco <= item["preco_max"]:
            if preco < item["preco_max"] * 0.4:
                continue
            venda = item["venda"]
            lucro = venda - preco if venda else None
            pct = lucro / preco if lucro is not None else None
            if pct is not None and pct >= regras.MARGEM_MIN:
                return item["nome"], "COMPRA", f"margem de {pct * 100:.0f}%", lucro, pct
            return item["nome"], "ESTOQUE", f"abaixo do seu teto de {reais(item['preco_max'])}", lucro, pct
    return None


# ---------------------------------------------------------------- GestãoClick
def carregar_gestaoclick(estado):
    acesso = os.environ.get("GESTAOCLICK_ACCESS_TOKEN")
    segredo = os.environ.get("GESTAOCLICK_SECRET_TOKEN")
    if not acesso or not segredo:
        return [], "chaves do GestãoClick ainda não configuradas"
    cache = estado.get("produtos")
    if cache and time.time() - cache.get("ts", 0) < 6 * 3600:
        return cache["lista"], None
    headers = {"access-token": acesso, "secret-access-token": segredo}
    produtos, pagina = [], 1
    try:
        while pagina <= 200:
            r = requests.get(f"{GESTAOCLICK_URL}/produtos", headers=headers,
                             params={"pagina": pagina}, timeout=30)
            r.raise_for_status()
            dados = r.json()
            for p in dados.get("data", []):
                produtos.append({"nome": p.get("nome", ""),
                                 "custo": numero(p.get("valor_custo")),
                                 "venda": numero(p.get("valor_venda")),
                                 "estoque": numero(p.get("estoque"))})
            meta = dados.get("meta", {}) or {}
            total = int(numero(meta.get("total_paginas")) or 1)
            if pagina >= total or not dados.get("data"):
                break
            pagina += 1
            time.sleep(0.4)
    except (requests.RequestException, ValueError) as erro:
        if cache:
            return cache["lista"], None
        return [], f"não consegui ler o GestãoClick ({erro})"
    estado["produtos"] = {"ts": time.time(), "lista": produtos}
    return produtos, None


# ---------------------------------------------------------------- envio
def enviar(texto):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["CHAT_ID"]
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={"chat_id": chat, "text": texto, "parse_mode": "HTML",
                        "disable_web_page_preview": False}, timeout=20)


def montar_alerta(nome, loja, preco, parcelas, veredito, motivo, lucro, pct,
                  produto, link, canal, avisos, cupom):
    e = html.escape
    titulo = "🟢 COMPRA" if veredito == "COMPRA" else "🟡 BOM PRA ESTOQUE"
    linhas = [f"<b>{titulo}</b>: {e(motivo)}", f"<b>{e(nome)}</b>",
              f"{e(loja or 'Loja não identificada')}: <b>{reais(preco)}</b>"
              + (f" ou {parcelas}x sem juros" if parcelas else "")]
    if produto:
        partes = []
        if produto["custo"]:
            partes.append(f"seu custo: {reais(produto['custo'])}")
        if produto["venda"]:
            partes.append(f"sua venda: {reais(produto['venda'])}")
        if partes:
            linhas.append(" | ".join(partes).capitalize())
    if lucro is not None:
        linhas.append(f"Lucro: {reais(lucro)} ({pct * 100:.0f}%)")
    if cupom:
        linhas.append(f"Cupom no anúncio: {e(cupom)}")
    if avisos:
        linhas.append("⚠️ Atenção: " + e(", ".join(avisos)))
    linhas.append(f'<a href="{e(link)}">Abrir anúncio</a>')
    linhas.append(f"Fonte: {e(canal)} | {datetime.now(timezone(timedelta(hours=-3))):%d/%m %H:%M}")
    return "\n".join(linhas)


def extrair_cupom(texto):
    m = re.search(r"cupom[:\s]+([A-Z0-9]{4,20})", texto)
    return m.group(1) if m else None


# ---------------------------------------------------------------- análise de uma mensagem
def analisar(texto, links, produtos, canal):
    """Devolve o texto do alerta, ou None se não compensa."""
    if not texto or not links:
        return None
    t = normalizar(texto)
    if any(normalizar(i) in t for i in regras.IGNORAR):
        return None
    preco = extrair_preco(texto)
    if not preco:
        return None
    link = links[0]
    loja = identificar_loja(link)
    if loja is None:
        link = resolver_link(link)
        loja = identificar_loja(link)
    if loja_bloqueada(loja):
        return None
    avisos = riscos(texto)
    if loja is None:
        return None  # só anúncio direto de loja conhecida
    parcelas, cupom = extrair_parcelas(texto), extrair_cupom(texto)

    produto = achar_produto(texto, produtos) if produtos else None
    if produto:
        resultado = avaliar_estoque(produto, preco)
        if resultado:
            veredito, motivo, lucro, pct = resultado
            return montar_alerta(produto["nome"], loja, preco, parcelas, veredito, motivo,
                                 lucro, pct, produto, link, canal, avisos, cupom)
    extra = avaliar_lista_extra(texto, preco)
    if extra:
        nome, veredito, motivo, lucro, pct = extra
        return montar_alerta(nome, loja, preco, parcelas, veredito, motivo, lucro, pct,
                             None, link, canal, avisos, cupom)
    return None


# ---------------------------------------------------------------- Telegram (sua conta)
def links_da_mensagem(msg):
    links = []
    for ent, txt in (msg.get_entities_text() or []):
        url = getattr(ent, "url", None) or (txt if txt.startswith("http") else None)
        if url:
            links.append(url)
    if not links:
        links = re.findall(r"https?://\S+", msg.message or "")
    for linha in getattr(msg, "buttons", None) or []:
        for b in linha:
            if getattr(b, "url", None):
                links.append(b.url)
    return links


def eh_canal_de_oferta(dialogo):
    ent = dialogo.entity
    if getattr(ent, "broadcast", False):
        return True
    nome = normalizar(dialogo.name)
    return getattr(ent, "megagroup", False) and any(
        p in nome for p in ("oferta", "promo", "cupom", "achado", "desconto", "kabum"))


def rodar():
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    estado = carregar_estado()
    agora = datetime.now(timezone.utc)
    ultimo = estado.get("ultimo_ciclo")
    desde = datetime.fromisoformat(ultimo) - timedelta(minutes=2) if ultimo else agora - timedelta(minutes=20)
    desde = max(desde, agora - timedelta(minutes=60))
    vistos = {k: v for k, v in estado.get("vistos", {}).items() if time.time() - v < 3 * 86400}

    produtos, erro_gc = carregar_gestaoclick(estado)
    produtos = preparar_produtos([dict(p) for p in produtos])

    with TelegramClient(StringSession(os.environ["TELEGRAM_SESSAO"]),
                        int(os.environ["TELEGRAM_API_ID"]),
                        os.environ["TELEGRAM_API_HASH"]) as cliente:
        os.environ["CHAT_ID"] = str(cliente.get_me().id)
        from types import SimpleNamespace
        from telethon.tl.functions.channels import JoinChannelRequest
        canais = []
        for nome in regras.CANAIS:
            try:
                ent = cliente.get_entity(nome)
                try:
                    cliente(JoinChannelRequest(ent))
                except Exception:
                    pass
                canais.append(SimpleNamespace(entity=ent, id=ent.id, name=getattr(ent, "title", nome)))
            except Exception as erro:
                print(f"canal {nome}: {erro}")

        if os.environ.get("MODO_TESTE") == "1":
            enviar("✅ <b>Robô THS Ofertas funcionando</b>\n"
                   f"Produtos do GestãoClick: {len(produtos)}"
                   + (f" ({html.escape(erro_gc)})" if erro_gc else "") + "\n"
                   f"Canais de ofertas lidos: {len(canais)}\n"
                   + html.escape(", ".join(d.name for d in canais[:15]) or "nenhum ainda"))

        if erro_gc and erro_gc != estado.get("ultimo_erro"):
            enviar(f"⚠️ {html.escape(erro_gc)}. Sigo vigiando só a lista extra.")
        estado["ultimo_erro"] = erro_gc

        enviados = 0
        for d in canais:
            for msg in cliente.iter_messages(d.entity, limit=150):
                if msg.date < desde:
                    break
                chave = f"{d.id}:{msg.id}"
                if chave in vistos or not msg.message:
                    continue
                vistos[chave] = time.time()
                alerta = analisar(msg.message, links_da_mensagem(msg), produtos, d.name)
                if not alerta:
                    continue
                assinatura = normalizar(alerta.split("\n")[1]) + str(extrair_preco(msg.message))
                if assinatura in vistos:
                    continue  # mesma oferta repetida em outro canal
                vistos[assinatura] = time.time()
                enviar(alerta)
                enviados += 1
                time.sleep(1)

    estado["vistos"] = vistos
    estado["ultimo_ciclo"] = agora.isoformat()
    salvar_estado(estado)
    print(f"{len(canais)} canais lidos, {enviados} alertas enviados.")


if __name__ == "__main__":
    rodar()
