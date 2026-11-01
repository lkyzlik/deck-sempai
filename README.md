
<p align="center">
  <picture>
    <img src="assets/logo.png" width="250" alt="DeckSempai logo">
  </picture>
</p>

<h1 align="center">DeckSempai</h1>

<p align="center">
    Assistant to the regional flashcard deck manager
</p>

## Features
* Import/export cards from/to Anki
* Automatically translate
* Automatically add pronunciation sounds
* Automatically add grammar help (articles, plurals, tenses, superlatives etc.)

<p align="center">
  <picture>
    <img src="assets/demo.gif" width="600" alt="DeckSempai demo">
  </picture>
</p>

## Installation

DeckSempai is installed with [uv](https://docs.astral.sh/uv/), a Python package and project manager.

### 1. Install uv

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Or with Homebrew: `brew install uv`. See the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for other options.

### 2. Install DeckSempai

```bash
uv tool install git+https://github.com/lkyzlik/deck-sempai.git
```

Or from a local clone:

```bash
git clone https://github.com/lkyzlik/deck-sempai.git
cd deck-sempai
uv tool install .
```

uv will fetch a suitable Python (>=3.13) automatically if needed. The `sempai` command is then available on your `PATH`:

```bash
sempai --help
```

To upgrade later, run `uv tool upgrade deck-sempai`; to remove it, `uv tool uninstall deck-sempai`.

## Integrations

Most features need a connection to another app or service:

| Integration | Used for | Requires |
|---|---|---|
| `anki` | Storing decks and cards | [Anki](https://apps.ankiweb.net) desktop app running, with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on |
| `ollama` | Translation and AI grammar help | [Ollama](https://ollama.com/download) running locally, with the configured model pulled |
| `ordnet` | Danish pronunciation and grammar lookups | Internet access to [ordnet.dk](https://ordnet.dk) |

Check that the integrations work with:

```bash
sempai status          # all integrations
sempai status anki     # just one
```

Any disconnected integration lists the steps to set it up. Unused integrations can be disabled with `enable = false` in the
config (`sempai config`).

## License

DeckSempai is released under the [MIT License](LICENSE).



