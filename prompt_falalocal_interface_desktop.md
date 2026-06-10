# Prompt — Interface Profissional Desktop para o App FalaLocal

Você é um desenvolvedor frontend sênior e designer de produto.

Preciso que você crie uma interface profissional desktop para o meu app chamado **FalaLocal**, disponível neste repositório:


---

## Objetivo do app

O **FalaLocal** é um aplicativo simples e profissional para **geração de áudios a partir de texto**.

O usuário deve conseguir:

1. Criar áudios digitando um texto.
2. Escolher e ajustar configurações de voz.
3. Gerar o áudio.
4. Ouvir o áudio diretamente dentro do app.
5. Salvar e organizar os áudios gerados.
6. Separar os áudios por **pastas** ou **projetos**.
7. Acessar uma galeria inicial com os áudios já criados.
8. Ajustar configurações técnicas mais avançadas em uma tela própria.

O foco do app deve ser simplicidade, produtividade, organização e boa experiência de reprodução de áudio.

---

## Direção visual

Crie uma interface desktop profissional, moderna e limpa, com aparência de produto SaaS.

A interface deve transmitir:

- Clareza
- Organização
- Tecnologia
- Produtividade
- Confiabilidade
- Simplicidade

Use como inspiração visual produtos como:

- ElevenLabs
- Descript
- Notion
- Linear
- ChatGPT Desktop
- Spotify for Creators
- Microsoft Teams

Evite visual amador, excesso de cores, botões genéricos, telas poluídas ou layout sem hierarquia.

---

## Identidade visual

Nome do app: **FalaLocal**

Como o app trabalha com geração de áudio, voz e organização de conteúdos, a identidade visual deve remeter a:

- Voz
- Ondas sonoras
- Biblioteca de áudios
- Produção de conteúdo
- Organização por projetos

Sugestões visuais:

- Ícone com onda sonora, microfone minimalista ou balão de fala
- Paleta sóbria e tecnológica
- Tons principais sugeridos: azul, grafite, verde ou roxo escuro
- Fundo claro, com estrutura preparada para futuro modo escuro
- Cards com bordas suaves
- Tipografia moderna
- Ícones limpos
- Boa separação entre áreas da tela

---

## Estrutura principal da aplicação

A aplicação deve ter pelo menos 3 áreas principais:

1. **Galeria / Início**
2. **Criar Áudio**
3. **Configurações**

Essas áreas devem estar acessíveis por uma sidebar lateral.

---

# Tela 1 — Galeria / Início

Esta será a tela inicial do app.

Ela deve funcionar como uma biblioteca dos áudios gerados.

## Objetivo da tela

Permitir que o usuário visualize, organize, pesquise, reproduza e acesse os áudios criados.

## Elementos esperados

A tela deve conter:

- Header com título: “Galeria de Áudios”
- Campo de busca para procurar áudios
- Botão principal: “Novo áudio”
- Cards ou lista dos áudios gerados
- Filtros por pasta, projeto ou data
- Área lateral ou seção para pastas/projetos
- Estado vazio elegante para quando não houver áudios
- Indicação de duração do áudio
- Data de criação
- Nome do projeto/pasta
- Botões rápidos: reproduzir, pausar, editar, baixar, excluir ou mover

## Organização por pastas/projetos

Crie uma forma visual clara para organizar os áudios por:

- Projeto
- Pasta
- Categoria

Exemplo de pastas/projetos:

- Aulas
- Avisos para alunos
- Podcasts
- Vídeos
- Testes de voz
- Materiais institucionais

A interface deve permitir visualizar a ideia de que o usuário poderá futuramente criar, renomear e excluir pastas.

Pode usar dados mockados se ainda não houver backend.

---

# Reprodução de áudio dentro do app

A interface deve permitir que o usuário toque os áudios diretamente dentro do próprio app, sem precisar baixar o arquivo.

O app deve ter um player de áudio integrado e visualmente profissional.

## Na Galeria de Áudios

Cada áudio listado na galeria deve permitir:

- Reproduzir o áudio diretamente no card ou na linha da lista
- Pausar o áudio
- Ver o tempo atual e a duração total
- Visualizar uma barra de progresso
- Avançar ou voltar no áudio, se possível
- Identificar claramente qual áudio está tocando
- Impedir confusão quando vários áudios aparecem na tela

Quando um áudio estiver tocando, o card deve ter destaque visual discreto.

## Player global opcional

Além do player em cada card, pode existir um mini player fixo na parte inferior da interface, semelhante a apps de música ou podcast.

Esse mini player pode conter:

- Nome do áudio em reprodução
- Projeto ou pasta
- Botão play/pause
- Barra de progresso
- Tempo atual / duração total
- Controle de volume
- Botão para baixar
- Botão para abrir detalhes do áudio

## Na tela de criação de áudio

Depois que o áudio for gerado, a tela deve exibir um player de preview com:

- Botão de play/pause
- Barra de progresso
- Duração do áudio
- Controle de volume
- Botão para baixar
- Botão para salvar em projeto/pasta
- Botão para gerar novamente

O usuário deve conseguir ouvir o resultado antes de salvar definitivamente.

## Requisitos do player

O player deve:

- Ter aparência moderna e integrada ao design do app
- Ser simples de usar
- Ter estados visuais de carregando, pronto, tocando, pausado e erro
- Funcionar com dados mockados inicialmente
- Estar preparado para receber futuramente uma URL real do áudio gerado pela API

Exemplo de estrutura mockada para áudio:

```ts
{
  id: "audio-001",
  title: "Aviso de aula ao vivo",
  project: "Aulas",
  folder: "Comunicados",
  duration: "00:42",
  createdAt: "2026-06-10",
  voice: "Voz feminina natural",
  status: "completed",
  audioUrl: "/mock/audio-aviso-aula.mp3"
}
```

Caso não exista um arquivo real de áudio no projeto, usar uma estrutura preparada para receber a URL posteriormente e simular o estado de reprodução visualmente.

---

# Tela 2 — Criar Áudio

Esta é a tela principal de produção.

## Objetivo da tela

Permitir que o usuário digite um texto, configure a voz, gere um áudio e escute o resultado antes de salvar.

## Estrutura esperada

A tela deve conter duas áreas principais:

### Área esquerda — Editor de texto

- Campo grande para digitar o texto
- Contador de caracteres
- Sugestão de limite de texto
- Botão para limpar texto
- Botão para colar texto
- Indicação de status: pronto, gerando, erro ou concluído

O editor deve ser confortável para escrever textos longos.

### Área direita — Configurações de voz

Painel lateral com ajustes como:

- Seleção de voz
- Idioma
- Tom da voz
- Velocidade
- Estabilidade
- Similaridade
- Clareza
- Estilo de narração
- Pausas
- Intensidade emocional

Esses campos podem ser mockados se ainda não houver integração real.

## Ações principais

A tela deve ter botões bem visíveis:

- “Gerar áudio”
- “Salvar como rascunho”
- “Pré-visualizar”
- “Cancelar”

Após gerar o áudio, deve aparecer uma área de preview com:

- Player de áudio integrado
- Nome do áudio
- Duração
- Botão para baixar
- Botão para salvar em pasta/projeto
- Botão para gerar novamente

---

# Tela 3 — Configurações

A tela de configurações deve ser voltada para ajustes mais finos e técnicos.

## Objetivo da tela

Permitir que o usuário ajuste preferências globais do app e parâmetros técnicos de geração.

## Seções sugeridas

### Preferências gerais

- Nome padrão dos arquivos
- Pasta padrão para novos áudios
- Formato padrão de exportação
- Idioma padrão
- Voz padrão

### Configurações de áudio

- Formato: MP3, WAV, OGG
- Qualidade do áudio
- Taxa de amostragem
- Normalização de volume
- Remoção de silêncio
- Volume padrão

### Configurações de geração

- Modelo de voz
- Temperatura/criatividade da geração, se aplicável
- Velocidade padrão
- Estabilidade padrão
- Similaridade padrão
- Limite de caracteres por geração

### Configurações técnicas

- Chave de API, se houver
- Endpoint da API
- Timeout de requisição
- Logs de geração
- Teste de conexão

### Aparência

- Tema claro/escuro
- Densidade da interface
- Idioma da interface

---

# Layout geral

Use um layout desktop-first com:

## Sidebar lateral

A sidebar deve conter:

- Logo/nome do app
- Menu principal
- Estado ativo do menu
- Área inferior com Configurações

Menus sugeridos:

- Galeria
- Criar Áudio
- Projetos
- Configurações

Caso “Projetos” não seja uma tela separada, pode aparecer apenas como seção dentro da Galeria.

## Header superior

O header deve conter:

- Título da tela atual
- Campo de busca quando fizer sentido
- Botão de ação principal
- Status do sistema ou da geração
- Avatar ou identificação do usuário, se aplicável

---

# Componentes esperados

Crie componentes reutilizáveis, como:

- `Sidebar`
- `Header`
- `AudioCard`
- `AudioList`
- `ProjectList`
- `FolderCard`
- `AudioPlayer`
- `MiniPlayer`
- `AudioProgressBar`
- `VolumeControl`
- `PlaybackButton`
- `TextEditor`
- `VoiceSettingsPanel`
- `SettingsSection`
- `MetricCard`
- `EmptyState`
- `PrimaryButton`
- `SearchInput`
- `StatusBadge`
- `PageContainer`

---

# Dashboard inicial opcional

Na Galeria, além dos áudios, pode haver pequenos indicadores no topo:

- Total de áudios
- Áudios gerados hoje
- Projetos ativos
- Tempo total de áudio gerado

Esses dados podem ser mockados inicialmente.

---

# Requisitos de UX

A interface deve:

- Ser simples de entender
- Priorizar a criação rápida de áudio
- Facilitar a organização dos arquivos
- Permitir reprodução dos áudios dentro do app
- Ter boa hierarquia visual
- Ter espaçamento consistente
- Ter botões com estados de hover, active e disabled
- Ter estados de carregamento
- Ter estados vazios bem escritos
- Ter mensagens de erro e sucesso
- Ter feedback visual ao gerar áudio
- Ter player de áudio visualmente agradável
- Não parecer um painel administrativo genérico

---

# Requisitos técnicos

Analise a stack do projeto antes de implementar.

Se o projeto já tiver uma stack definida, mantenha a stack existente.

Caso o projeto esteja vazio ou sem estrutura frontend definida, utilize:

- React
- TypeScript
- Vite
- Tailwind CSS
- Lucide React para ícones

Estrutura sugerida:

```text
src/
  components/
    layout/
    ui/
    audio/
    projects/
    settings/
  pages/
    GalleryPage.tsx
    CreateAudioPage.tsx
    SettingsPage.tsx
  data/
    mockAudios.ts
    mockProjects.ts
    mockVoices.ts
  styles/
  App.tsx
  main.tsx
```

---

# Dados mockados

Enquanto não houver backend, crie dados mockados para:

- Áudios gerados
- Projetos
- Pastas
- Vozes disponíveis
- Configurações padrão

Exemplo de áudio:

```ts
{
  id: "audio-001",
  title: "Aviso de aula ao vivo",
  project: "Aulas",
  folder: "Comunicados",
  duration: "00:42",
  createdAt: "2026-06-10",
  voice: "Voz feminina natural",
  status: "completed",
  audioUrl: "/mock/audio-aviso-aula.mp3"
}
```

Exemplo de projeto:

```ts
{
  id: "project-001",
  name: "Aulas",
  totalAudios: 12,
  lastUpdated: "2026-06-10"
}
```

---

# Critérios de qualidade

A entrega deve:

- Rodar sem erros
- Ter aparência profissional
- Ter componentes reutilizáveis
- Ter código limpo e organizado
- Usar nomes claros
- Ter responsividade mínima
- Ser otimizada para desktop
- Ser fácil de evoluir
- Usar dados mockados de forma organizada
- Não quebrar funcionalidades existentes
- Ter player de áudio integrado e funcional ou simulado de forma clara enquanto não houver arquivo real

---

# Restrições

- Não criar backend complexo se ainda não existir.
- Não remover arquivos importantes.
- Não alterar regras de negócio sem necessidade.
- Não usar bibliotecas pesadas sem justificativa.
- Não deixar textos genéricos como “Lorem ipsum”.
- Não criar uma interface infantil ou colorida demais.
- Não fazer apenas uma landing page; preciso de uma interface real de aplicativo.
- Não deixar todas as funcionalidades em uma única tela desorganizada.
- Não depender de download para ouvir os áudios; a reprodução deve acontecer dentro do app.

---

# Entrega esperada

Implemente a interface no projeto.

Ao final, informe:

1. Quais arquivos foram criados.
2. Quais arquivos foram alterados.
3. Como rodar o projeto localmente.
4. Quais dados estão mockados.
5. Como a navegação entre telas foi organizada.
6. Como o player de áudio foi implementado ou preparado.
7. Quais pontos podem ser conectados futuramente ao backend/API de geração de áudio.

---

# Resultado esperado

Quero que o **FalaLocal** tenha uma interface desktop profissional para geração, reprodução e organização de áudios, com:

- Galeria inicial de áudios
- Organização por pastas ou projetos
- Reprodução dos áudios dentro do app
- Player integrado nos cards ou na lista
- Mini player global opcional
- Tela dedicada para criação de áudio
- Painel de ajustes de voz
- Player de preview após geração
- Tela de configurações técnicas
- Visual moderno e pronto para apresentação
