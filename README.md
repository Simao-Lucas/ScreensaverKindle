# ScreensaverKindle

Painel web em Docker que converte imagens para o e-ink do Kindle Paperwhite e atualiza a pasta de **screensaver do KOReader**.

## O que faz (Fase 1)

1. Upload de PNG/JPG/WEBP (drag & drop)
2. Conversão automática: cover crop → grayscale → contraste → PNG `1072×1448`
3. Envio via SSH/SFTP para a pasta de screensaver do KOReader
4. A imagem aparece quando o Kindle entra em **sleep** (não abre o arquivo no visualizador)

## Requisitos

- Ubuntu com Docker e Docker Compose
- Kindle jailbroken com SSH acessível na rede (ex.: USBNetwork / wifi, porta `2222`)
- KOReader com screensaver por pasta de imagens customizadas

## Configurar o KOReader (uma vez)

1. No Kindle, a pasta padrão do app é `/mnt/us/screensaver` (criada no primeiro envio)
2. No KOReader: **Screen → Screensaver**
3. Escolha wallpaper / imagens da pasta (random ou single)
4. Aponte para a pasta `screensaver` (long-press para confirmar)
5. Ideal: deixe só essa pasta para o app (ele limpa PNG/JPG antigos a cada envio)

## Configuração do servidor

```bash
cp .env.example .env
nano .env
```

Variáveis importantes:

| Variável | Descrição | Default |
|---|---|---|
| `KINDLE_HOST` | IP do Kindle | — |
| `KINDLE_PORT` | Porta SSH | `2222` |
| `KINDLE_USER` | Usuário SSH | `root` |
| `KINDLE_PASSWORD` | Senha SSH | — |
| `KINDLE_WIDTH` / `KINDLE_HEIGHT` | Resolução alvo | `1072` / `1448` |
| `KINDLE_CONTRAST` | Contraste da conversão | `1.15` |
| `KINDLE_REMOTE_PATH` | PNG na pasta do screensaver | `/mnt/us/screensaver/current.png` |
| `KINDLE_CLEAR_SCREENSAVER_DIR` | Limpa outras imagens da pasta | `true` |
| `KINDLE_REFRESH_CMD` | Comando SSH opcional pós-envio | vazio |
| `PORT` | Porta HTTP publicada | `8080` |

## Subir no Ubuntu

```bash
docker compose up -d --build
```

Abra `http://IP-DO-SERVIDOR:8080`.

O compose publica a porta `${PORT:-8080}`. Se o container não alcança o Kindle (SSH no host funciona, no Docker não), use `network_mode: host` no `docker-compose.yml`.

### Se o container ficar reiniciando

```bash
docker compose logs --tail 100
docker compose ps
docker compose down
docker compose up -d --build
```

## Uso

1. Solte ou escolha uma imagem
2. Confira o preview em tons de cinza
3. Clique em **Enviar para Kindle**
4. Coloque o Kindle em sleep para ver a nova imagem

Status na UI: Convertida → Transferida → No screensaver.

## Estrutura

```
app/
  main.py             # rotas Flask
  image_pipeline.py   # conversão Pillow
  kindle_client.py    # SFTP + SSH (Paramiko)
  templates/          # UI
  static/
data/uploads/         # current.png + preview (volume)
Dockerfile
docker-compose.yml
.env.example
```
