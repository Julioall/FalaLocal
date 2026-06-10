# Kokoro pt_BR Desktop Local

Aplicativo desktop local para transformar texto em voz em portugues do Brasil usando Kokoro.

Depois que o modelo fica no cache local, a geracao roda sem ElevenLabs ou API externa.

## Modelo

- Modelo: `hexgrad/Kokoro-82M`
- Idioma: Brazilian Portuguese, `lang_code='p'`
- Vozes pt_BR: `pf_dora`, `pm_alex`, `pm_santa`
- Sample rate: 24000 Hz
- Licenca: Apache 2.0

Fontes:

- https://huggingface.co/hexgrad/Kokoro-82M
- https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md

## Requisitos

- Python 3.10+
- `uv` para preparar o ambiente Python
- `espeak-ng` instalado e disponivel no PATH, ou informado na interface

O app usa o pacote `kokoro` com `KPipeline(lang_code='p')`.

## Instalar no Windows

Abra o PowerShell na pasta do projeto e rode:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

Se o `espeak-ng` nao estiver instalado, use uma destas opcoes:

```powershell
winget install -e --id eSpeak-NG.eSpeak-NG
```

Ou baixe o instalador MSI oficial em:

```text
https://github.com/espeak-ng/espeak-ng/releases
```

Depois reinicie o PowerShell e rode `scripts/run.ps1` novamente. Se o instalador nao colocar o executavel no PATH, a app tenta detectar automaticamente `C:\Program Files\eSpeak NG\espeak-ng.exe`; tambem da para selecionar o executavel no campo `Executavel espeak-ng`.

## Instalar no Linux/WSL

Instale o `espeak-ng`:

```bash
sudo apt install espeak-ng
```

Depois rode:

```bash
./scripts/bootstrap.sh
./scripts/run.sh
```

Se o script nao tiver permissao de execucao:

```bash
chmod +x scripts/bootstrap.sh scripts/run.sh
```

## Usar a app

1. Digite o texto em portugues do Brasil.
2. Escolha a voz: `pf_dora`, `pm_alex` ou `pm_santa`.
3. Confira se `Executavel espeak-ng` aponta para `espeak-ng`.
4. Ajuste velocidade e pausa entre frases se necessario.
5. Clique em `Gerar WAV`.

Os arquivos sao salvos em `outputs/` por padrao.

## Configuracao por variavel de ambiente

Para apontar para um `espeak-ng` fora do PATH:

```bash
export TTS_ESPEAK=/caminho/para/espeak-ng
```

## Observacoes para producao interna

- Kokoro e o modo unico da app nesta versao.
- Este fluxo nao faz clonagem de voz.
- A primeira execucao precisa de internet para baixar o modelo; depois o cache local e reutilizado.
