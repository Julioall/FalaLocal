# TTS pt_BR Desktop Local

Aplicativo desktop local para transformar texto em voz em portugues do Brasil, com dois motores:

- **Kokoro-82M**: modo padrao, melhor qualidade, vozes pt_BR selecionaveis.
- **Piper pt_BR**: fallback rapido e leve em ONNX.

Depois que os modelos ficam no cache local, a geracao roda sem ElevenLabs ou API externa.

## Modelo padrao

- Modelo: `hexgrad/Kokoro-82M`
- Idioma: Brazilian Portuguese, `lang_code='p'`
- Vozes pt_BR: `pf_dora`, `pm_alex`, `pm_santa`
- Sample rate: 24000 Hz
- Licenca: Apache 2.0

Fontes:

- https://huggingface.co/hexgrad/Kokoro-82M
- https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md

## Fallback Piper

- Modelo: `Trelis/piper-pt-br-faber-medium`
- Idioma: Portuguese (Brazil), `pt_BR`
- Voz: masculina, `pt_BR-faber-medium`
- Formato: ONNX
- Tamanho: ~63 MB
- Sample rate: 22050 Hz
- Licenca do modelo: CC0/Public Domain conforme model card

Fonte: https://huggingface.co/Trelis/piper-pt-br-faber-medium

## Requisitos

- Python 3.10+
- `uv` para preparar o ambiente Python
- `espeak-ng` instalado e disponivel no PATH, ou informado na interface

O Kokoro usa o pacote `kokoro` com `KPipeline(lang_code='p')`. O Piper usa o caminho standalone ONNX do model card com `onnxruntime`, `huggingface_hub`, `soundfile` e `espeak-ng`.

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
2. Escolha o motor: `Kokoro - melhor qualidade` ou `Piper - rapido e leve`.
3. No Kokoro, escolha a voz: `pf_dora`, `pm_alex` ou `pm_santa`.
4. Confira se `Executavel espeak-ng` aponta para `espeak-ng`.
5. Ajuste velocidade, variacao e pausa entre frases se necessario.
6. Clique em `Gerar WAV`.

Os arquivos sao salvos em `outputs/` por padrao.

## Configuracao por variaveis de ambiente

Para trocar o modelo Piper:

```bash
export PIPER_TTS_MODEL=Trelis/piper-pt-br-faber-medium
```

Para apontar para um `espeak-ng` fora do PATH:

```bash
export PIPER_ESPEAK=/caminho/para/espeak-ng
```

## Observacoes para producao interna

- Kokoro e o modo recomendado para qualidade em pt_BR.
- Piper continua util quando a prioridade for simplicidade e previsibilidade.
- Nenhum dos dois fluxos faz clonagem de voz.
- A primeira execucao precisa de internet para baixar os modelos; depois o cache local e reutilizado.

