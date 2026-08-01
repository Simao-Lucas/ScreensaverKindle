# ScreensaverKindle

Painel web em Docker que converte imagens para o e-ink do Kindle Paperwhite e envia via SCP/SSH.

## O que faz (Fase 1)

1. Upload de PNG/JPG/WEBP (drag & drop)
2. Conversão automática: cover crop → grayscale → contraste → PNG `1072×1448`
3. Envio para o Kindle (`SCP`) e disparo do comando de refresh (`SSH`)

## Requisitos

- Ubuntu com Docker e Docker Compose
- Kindle jailbroken com SSH acessível na rede (ex.: USBNetwork / wifi, porta `2222`)
- KOReader (ou outro comando) capaz de abrir o PNG remoto

## Configuração

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
| `KINDLE_REMOTE_PATH` | Caminho do PNG no Kindle | `/mnt/us/display/current.png` |
| `KINDLE_REFRESH_CMD` | Comando SSH após o upload | `koreader.sh …/current.png` |
| `PORT` | Porta HTTP (host network) | `8080` |

Ajuste `KINDLE_REFRESH_CMD` quando descobrir o comando certo no seu KOReader/KUAL.

## Subir no Ubuntu

```bash
docker compose up -d --build
```

Abra `http://IP-DO-SERVIDOR:8080`.

O compose usa `network_mode: host` para o container enxergar o Kindle na LAN sem NAT extra.

Logs:

```bash
docker compose logs -f
```

Parar:

```bash
docker compose down
```

## Uso

1. Solte ou escolha uma imagem
2. Confira o preview em tons de cinza
3. Clique em **Enviar para Kindle**

Status na UI: Convertida → Transferida → Exibida.

## Estrutura

```
app/
  main.py             # rotas Flask
  image_pipeline.py   # conversão Pillow
  kindle_client.py    # SCP + SSH (Paramiko)
  templates/          # UI
  static/
data/uploads/         # current.png + preview (volume)
Dockerfile
docker-compose.yml
.env.example
```

## Nota sobre o refresh

Se o upload funcionar mas a tela não mudar, o problema quase sempre é `KINDLE_REFRESH_CMD`. No Kindle, confira o script do KUAL/KOReader e atualize a variável no `.env`, depois:

```bash
docker compose up -d
```
