# ScreensaverKindle

Painel web em Docker para o Kindle jailbroken: **enviar livros** (Calibre) e **atualizar o screensaver** do KOReader.

## Fluxos

1. **Início** (`/`) — escolha Enviar Livro ou Screensaver
2. **Enviar Livro** (`/books`) — upload → escolha de formato → `ebook-convert` → SFTP em `/mnt/us/documents/`
3. **Screensaver** (`/screensaver`) — imagem e-ink → pasta do screensaver do KOReader

## Formatos de livro

**Entrada:** EPUB, PDF, MOBI, AZW/AZW3, DOCX, HTML, RTF, TXT, FB2, ODT, CBZ

**Saída (escolha na UI):** EPUB (default), PDF, MOBI, FB2, TXT

O KOReader lê EPUB/PDF/MOBI/FB2/TXT nativamente. AZW3/KFX proprietários devem ser convertidos (ex.: para EPUB).

## Requisitos

- Ubuntu + Docker Compose
- Kindle com SSH (`2222`) e KOReader
- Chave SSH em `secrets/id_rsa` (ou senha vazia, se o Kindle aceitar)

## Rede (hotspot)

```text
Internet (cabo) → Ubuntu (hotspot) → Kindle 10.42.0.x:2222
```

Compose usa `network_mode: host`.

## Subir

```bash
cp .env.example .env
mkdir -p secrets
cp ~/.ssh/id_ed25519 secrets/id_rsa   # ou id_rsa
chmod 600 secrets/id_rsa
docker compose up -d --build
```

A build instala o **Calibre** (imagem maior; primeira build demora).

Abra `http://IP-DO-SERVIDOR:8080`.

### Restart loop / porta ocupada

```bash
docker compose logs --tail 80
# no .env: PORT=8090
docker compose up -d --build
```

## Variáveis

| Variável | Default |
|---|---|
| `KINDLE_HOST` | — |
| `KINDLE_PORT` | `2222` |
| `KINDLE_SSH_KEY` | `/keys/id_rsa` |
| `KINDLE_REMOTE_PATH` | `/mnt/us/screensaver/current.png` |
| `KINDLE_DOCUMENTS_DIR` | `/mnt/us/documents` |
| `EBOOK_CONVERT_BIN` | `/usr/local/bin/ebook-convert` |
| `BOOK_MAX_CONTENT_LENGTH` | `209715200` (200 MB) |
| `PORT` | `8080` |

## Screensaver no KOReader

Screen → Screensaver → pasta `/mnt/us/screensaver` (long-press).
