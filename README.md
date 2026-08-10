# ScreensaverKindle

Painel web em Docker que converte imagens para o e-ink do Kindle Paperwhite e atualiza a pasta de **screensaver do KOReader**.

## O que faz (Fase 1)

1. Upload de PNG/JPG/WEBP (drag & drop)
2. Conversão automática: cover crop → grayscale → contraste → PNG `1072×1448`
3. Envio via SSH/SFTP para a pasta de screensaver do KOReader
4. A imagem aparece quando o Kindle entra em **sleep**

## Requisitos

- Ubuntu com Docker e Docker Compose
- Kindle jailbroken com SSH (porta `2222`)
- KOReader com screensaver por pasta de imagens

## Rede (hotspot)

Caso típico deste projeto:

```text
Internet (cabo) → Ubuntu (hotspot) → Kindle em 10.42.0.33:2222
```

O compose usa `network_mode: host` para o container enxergar essa rede do hotspot (em bridge o `10.42.0.x` costuma falhar).

## SSH: IP+porta não bastam sozinhos

No terminal, isto:

```bash
ssh -p 2222 root@10.42.0.33
```

parece “só IP e porta”, mas o OpenSSH autentica em silêncio — quase sempre com um arquivo em `~/.ssh/` (`id_ed25519` / `id_rsa`), ou com senha vazia.

Para ver qual é o seu caso:

```bash
ssh -v -p 2222 root@10.42.0.33 2>&1 | grep -Ei "Authentications that can continue|Offering|Accepted"
```

- `Accepted publickey` → copie a chave para o Docker:

```bash
mkdir -p secrets
cp ~/.ssh/id_ed25519 secrets/id_rsa   # ou: cp ~/.ssh/id_rsa secrets/id_rsa
chmod 600 secrets/id_rsa
```

- `Accepted password` (senha vazia) → deixe `KINDLE_PASSWORD=` no `.env`; a chave é opcional

No `.env`:

```env
KINDLE_HOST=10.42.0.33
KINDLE_PORT=2222
KINDLE_USER=root
KINDLE_PASSWORD=
KINDLE_SSH_KEY=/keys/id_rsa
KINDLE_REMOTE_PATH=/mnt/us/screensaver/current.png
KINDLE_REFRESH_CMD=
```

## Configurar o KOReader (uma vez)

1. Pasta padrão: `/mnt/us/screensaver` (criada no primeiro envio)
2. KOReader: **Screen → Screensaver** → pasta de imagens → long-press em `screensaver`

## Subir no servidor

```bash
cp .env.example .env
nano .env
docker compose up -d --build
```

Abra `http://IP-DO-SERVIDOR:8080` (ou a porta definida em `PORT`).

### Restart loop

```bash
docker compose logs --tail 80
```

Causa comum com `network_mode: host`: **porta 8080 já em uso**. No `.env` use outra, ex. `PORT=8090`, e suba de novo:

```bash
docker compose down
docker compose up -d --build
```

## Uso

1. Solte ou escolha uma imagem
2. Confira o preview
3. **Enviar para Kindle**
4. Coloque o Kindle em sleep para ver a imagem
