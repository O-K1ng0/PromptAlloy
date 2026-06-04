# ⚡ PromptAlloy

**From idea to implementation blueprint — in one prompt.**

PromptAlloy is an AI-powered project blueprint generator. Describe what you want to build in plain English, answer a set of targeted clarifying questions (or let AI auto-answer them), and receive a single, self-contained prompt that any LLM can use to build your entire project from scratch — no follow-up questions needed.

---

## How It Works

1. **Describe** — Enter your project idea in plain English. Built-in validation rejects gibberish and ensures you provide a real description.
2. **Clarify** — The AI asks 8–12 targeted questions specific to your project type. Each question has a **Generate** button that auto-fills a smart default answer using AI.
3. **Generate** — Receive a complete project blueprint covering architecture, tech stack, folder structure, implementation steps, and deployment — all in one prompt, with no code snippets, just clear instructions.
4. **Export** — Copy to clipboard or download as Markdown, plain text, or JSON. Paste into ChatGPT, Claude, Gemini, or any LLM and start building.

---

## Quick Start

### 1. Clone & install
```bash
git clone <your-repo-url>
cd PromptAlloy
pip install -r requirements.txt
```

### 2. Configure your API key
```bash
cp .env.example .env
```
Open `.env` and replace `YOUR_API_KEY_HERE` with your API key. **Any OpenAI-compatible API works** — see the provider table below.

### 3. Run
```bash
python app.py
```
Open **http://localhost:5000** in your browser.

---

## Supported API Providers

PromptAlloy works with **any provider** that offers an OpenAI-compatible `chat/completions` endpoint. Set three values in your `.env` file:

| Provider | API Key Source | `OPENROUTER_API_URL` | `OPENROUTER_MODEL` |
|---|---|---|---|
| **OpenRouter** (recommended, free) | [openrouter.ai/keys](https://openrouter.ai/keys) | `https://openrouter.ai/api/v1/chat/completions` | `openrouter/auto` |
| **OpenAI** | [platform.openai.com](https://platform.openai.com/api-keys) | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` |
| **NVIDIA NIM** (free) | [build.nvidia.com](https://build.nvidia.com) | `https://integrate.api.nvidia.com/v1/chat/completions` | `deepseek-ai/deepseek-v4-flash` |
| **Groq** (free tier) | [console.groq.com](https://console.groq.com/keys) | `https://api.groq.com/openai/v1/chat/completions` | `llama-3.3-70b-versatile` |
| **Together AI** | [together.ai](https://api.together.xyz/settings/api-keys) | `https://api.together.xyz/v1/chat/completions` | `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` |
| **Ollama** (local, free) | No key needed | `http://localhost:11434/v1/chat/completions` | `llama3` |

### Example: Switching to Groq
```env
OPENROUTER_API_KEY=gsk_your_groq_key_here
OPENROUTER_API_URL=https://api.groq.com/openai/v1/chat/completions
OPENROUTER_MODEL=llama-3.3-70b-versatile
```
Restart the app and you're using Groq.

---

## Features

- **Smart Input Validation** — Rejects gibberish, random characters, and nonsense input before wasting an API call
- **Intelligent Clarification** — AI asks 8–12 questions relevant to your specific project type (web app, mobile, CLI, ML, etc.)
- **One-Click Auto-Answers** — Generate smart default answers for any clarification question instantly
- **Token-Efficient Blueprints** — Pure text instructions (no code blocks), dense and actionable, fits any LLM context window
- **Multi-Format Export** — Copy, or download as `.md`, `.txt`, or `.json`
- **Session History** — All generated blueprints saved and accessible across browser sessions, with confirmation before clearing
- **Provider Agnostic** — Works with any OpenAI-compatible API
- **Dark Luxury UI** — Deep navy theme with indigo/amber accents, animated background, and smooth transitions

---

## Project Structure

```
PromptAlloy/
├── app.py                # Flask backend + LLM orchestration + input validation
├── .env.example          # Configuration template (copy to .env)
├── requirements.txt      # Python dependencies
├── templates/
│   ├── index.html        # Main 3-step wizard UI
│   ├── session.html      # Session detail view (copy, save, close)
│   └── history.html      # History list page
├── static/
│   ├── logo.svg          # App logo (anvil + spark)
│   ├── favicon.svg       # Browser tab icon
│   ├── css/style.css     # Dark luxury theme
│   └── js/
│       ├── script.js     # Wizard logic, validation, auto-answer
│       ├── session.js    # Session detail + multi-format export
│       └── history.js    # History page logic
└── data/                 # Auto-created, stores history.json
```

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** | — | API key from any supported provider |
| `OPENROUTER_API_URL` | No | `https://openrouter.ai/api/v1/chat/completions` | Base URL for the chat completions endpoint |
| `OPENROUTER_MODEL` | No | `openrouter/auto` | Model name to use |
| `LLM_PROVIDER` | No | `openrouter` | Provider identifier (`openrouter`, `nvidia`, or `gemini`) |
| `GEMINI_API_KEY` | No | — | Google Gemini API key (used as fallback if primary provider fails) |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model name |

## Tech Stack

- **Backend**: Python 3.10+ / Flask
- **AI**: Any OpenAI-compatible API (with optional Gemini fallback)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Storage**: File-based JSON persistence

## License

All Rights Reserved. See [LICENSE](LICENSE) for details.
