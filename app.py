import re
import os
import json
import time
import random
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

DEFAULT_MODEL_CANDIDATES = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]
DEFAULT_PROVIDER = "openrouter"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"
DEFAULT_OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RATE_LIMIT_RETRIES = 3
DEFAULT_RETRY_SECONDS = 5
MAX_NETWORK_RETRIES = 3
BASE_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 20
MAX_HISTORY_ITEMS = 100
HISTORY_FILE = Path(__file__).resolve().parent / "data" / "history.json"

META_PROMPT_TEMPLATE = """You are an expert software architect. Generate a COMPLETE project blueprint from the user's idea and Q&A answers.

PROJECT DESCRIPTION:
"{user_input}"

{qa_section}━━━ BLUEPRINT REQUIREMENTS ━━━
Produce a single, self-contained prompt that an LLM can execute to build this project WITHOUT asking any follow-up questions.

INCLUDE (skip sections that don't apply):
1. **Architecture**: Tech stack (with brief rationale), folder structure, DB schema if needed
2. **Core Files**: List every file path with its purpose and what it should contain — describe the logic in plain English
3. **Setup**: Dependencies with versions, install commands, env vars, config requirements
4. **Implementation**: Step-by-step build order describing what each step does and how components connect
5. **Deploy & Test**: Testing approach, deployment steps

CRITICAL STYLE RULES:
- OUTPUT MUST BE PURE TEXT INSTRUCTIONS — NO code snippets, NO code blocks, NO inline code
- Describe what the code should do in plain English, not how it looks in syntax
- Example: Instead of showing a Python function, say "Create a function called X that takes parameters A and B, validates them, queries the database for Y, and returns the result as JSON"
- Use compact Markdown: ## headers, bullet lists, bold labels
- Be dense and precise — every sentence must carry information
- No filler phrases, no restating the obvious
- Merge related items (e.g. "Install X, Y, Z" not three separate bullets)
- Aim for 10,000–18,000 characters max — tight enough for any LLM context window
- If the project is simple, keep it short; complexity earns length

Return ONLY a raw JSON object — no markdown wrapper, no code blocks, no extra text:
{{"task_type": "project_type_detected", "refined_prompt": "the complete project blueprint prompt", "explanation": "3-5 key features included in this blueprint using • as bullet prefix", "style_used": "structured"}}"""


ASK_PROMPT_TEMPLATE = """You are an expert solution architect. Analyze the project idea and generate ONLY relevant clarifying questions specific to that project type. No generic questions. Every question must directly relate to building THIS specific project.

PROJECT DESCRIPTION:
"{user_input}"

{answers_section}STEP 1: IDENTIFY PROJECT TYPE
Determine the project category from: WEB APP | MOBILE APP | DESKTOP | CLI/LIBRARY | ML/DATA | INFRASTRUCTURE | AUTOMATION | HYBRID

STEP 2: GENERATE PROJECT-TYPE-SPECIFIC QUESTIONS ONLY
Ask ONLY questions that matter for THIS specific project type and idea. Skip entire categories that don't apply.

EXAMPLES BY PROJECT TYPE:

[WEB APP] - Tech stack, Frontend/Backend, Database, Auth, Real-time, Deployment, Scale
[MOBILE APP] - Platform (iOS/Android), App Store requirements, Device features, Offline mode, Push notifications
[CLI TOOL] - Input/Output formats, Dependencies, Installation, Cross-platform support, Performance
[ML/DATA] - Dataset size, Model type, Training pipeline, Inference needs, MLOps requirements
[AUTOMATION] - Triggers, Error handling, Logging, Scheduling, Integration points
[INFRASTRUCTURE] - Cloud provider, IaC tool, Monitoring, Scaling strategy, Backup/DR

RULES:
1. Ask 8-12 comprehensive questions that cover ALL aspects of this project
2. Each question must be:
   - Specific to THIS project (not generic checklist)
   - Directly answerable in 1-3 sentences
   - Non-overlapping with other questions
3. Skip entire question categories if irrelevant to this project type
4. MUST include ALL fields:
   - category: tech_stack | architecture | features | data | performance | security | deployment | integration | timeline | ux | operations
   - question: specific, clear, targeted question
   - hint: 2-3 word example
   - why: 1 sentence on importance
5. Never ask about things already stated in description
6. Never re-ask previously answered questions
7. Prioritize: most impactful → least impactful

CRITICAL: Be selective. Only ask what's needed for THEIR project, not a generic template.

Return ONLY a raw JSON object — no markdown, no code blocks:
{{"task_type": "detected_type", "questions": [{{"id": 1, "category": "tech_stack", "question": "Framework/language/database preferences?", "hint": "React, Django, PostgreSQL", "why": "Determines architecture"}}]}}"""


def extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response with multiple robust strategies."""
    if not text or not text.strip():
        return None
    text = text.strip()

    # Strategy 1: Strip markdown code fences first
    cleaned = text
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    # Strategy 2: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find balanced {...} using brace counting
    result = _find_balanced_json(cleaned)
    if result is not None:
        return result

    # Strategy 4: Try on original text (without code fence stripping)
    if cleaned != text:
        result = _find_balanced_json(text)
        if result is not None:
            return result

    # Strategy 5: Fix common JSON issues (trailing commas, single quotes)
    fixed = _fix_common_json_issues(cleaned)
    if fixed:
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    logger.error("All JSON extraction strategies failed. Raw text (first 1000 chars): %s", text[:1000])
    return None


def _find_balanced_json(text: str) -> dict | None:
    """Find first balanced top-level {...} block using brace counting."""
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            if in_string:
                escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Try fixing common issues in this candidate
                    fixed = _fix_common_json_issues(candidate)
                    if fixed:
                        try:
                            return json.loads(fixed)
                        except json.JSONDecodeError:
                            pass
                    # Continue looking for next top-level brace
                    next_start = text.find('{', i + 1)
                    if next_start == -1:
                        return None
                    return _find_balanced_json(text[next_start:])
    return None


def _fix_common_json_issues(text: str) -> str | None:
    """Fix trailing commas and other common LLM JSON mistakes."""
    if not text:
        return None
    # Remove trailing commas before } or ]
    fixed = re.sub(r',\s*([}\]])', r'\1', text)
    # Replace single quotes with double quotes (only outside existing double-quoted strings)
    # This is a best-effort heuristic
    if fixed != text:
        return fixed
    return fixed


def parse_retry_seconds(error_text: str) -> int | None:
    """Extract retry delay seconds from provider error text when available."""
    text = error_text.lower()

    patterns = [
        r"retry_delay\s*\{\s*seconds:\s*(\d+)",
        r"retry after\s*(\d+)\s*seconds?",
        r"try again in\s*(\d+)\s*seconds?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def parse_retry_seconds_from_headers(headers: dict) -> int | None:
    value = headers.get("Retry-After") if headers else None
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compute_backoff_seconds(attempt: int, retry_seconds: int | None = None) -> int:
    if retry_seconds is not None:
        return max(1, min(retry_seconds, MAX_BACKOFF_SECONDS))
    raw = BASE_BACKOFF_SECONDS * (2 ** attempt)
    jitter = random.uniform(0.0, 0.6)
    return max(1, min(int(raw + jitter), MAX_BACKOFF_SECONDS))


class GenerationError(Exception):
    def __init__(self, message: str, status_code: int = 500, retry_seconds: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_seconds = retry_seconds


def _ensure_history_store() -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]", encoding="utf-8")


def _read_history() -> list[dict]:
    _ensure_history_store()
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_history(items: list[dict]) -> None:
    _ensure_history_store()
    HISTORY_FILE.write_text(json.dumps(items[:MAX_HISTORY_ITEMS], ensure_ascii=False, indent=2), encoding="utf-8")


def generate_with_openrouter(prompt: str, api_key: str, model_name: str):
    api_urls_raw = os.getenv("OPENROUTER_API_URLS", "").strip()
    if api_urls_raw:
        api_urls = [u.strip() for u in api_urls_raw.split(",") if u.strip()]
    else:
        api_url = os.getenv("OPENROUTER_API_URL", DEFAULT_OPENROUTER_API_URL).strip() or DEFAULT_OPENROUTER_API_URL
        api_urls = [api_url]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 16384,
    }

    last_exception = None
    for api_url in api_urls:
        for attempt in range(MAX_NETWORK_RETRIES + 1):
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            except requests.RequestException as e:
                last_exception = e
                msg = str(e).lower()
                is_dns_error = "nameresolutionerror" in msg or "failed to resolve" in msg or "getaddrinfo failed" in msg
                if attempt < MAX_NETWORK_RETRIES:
                    time.sleep(compute_backoff_seconds(attempt))
                    continue
                if is_dns_error:
                    continue
                raise GenerationError(f"API network error: {e}", 503) from e

            response_text = response.text or ""
            if response.status_code == 429:
                retry_seconds = (
                    parse_retry_seconds_from_headers(response.headers)
                    or parse_retry_seconds(response_text)
                    or DEFAULT_RETRY_SECONDS
                )
                if attempt < MAX_RATE_LIMIT_RETRIES:
                    time.sleep(compute_backoff_seconds(attempt, retry_seconds))
                    continue
                raise GenerationError(
                    f"Rate limit hit. Please wait about {retry_seconds} seconds and try again.",
                    429,
                    retry_seconds,
                )

            if response.status_code in (401, 403):
                raise GenerationError("Invalid API key. Check OPENROUTER_API_KEY in your .env.", 401)

            if response.status_code >= 500 and attempt < MAX_NETWORK_RETRIES:
                time.sleep(compute_backoff_seconds(attempt))
                continue

            if not response.ok:
                try:
                    err_json = response.json()
                    err_message = (
                        err_json.get("error", {}).get("message")
                        or err_json.get("message")
                        or response_text
                    )
                except ValueError:
                    err_message = response_text
                raise GenerationError(f"API error: {err_message}", response.status_code)

            try:
                result = response.json()
            except ValueError as e:
                raise GenerationError("API returned invalid JSON.", 502) from e

            try:
                content = result["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as e:
                raise GenerationError("API response did not include message content.", 502) from e

            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )

            return str(content), model_name

    if last_exception:
        raise GenerationError(
            "API DNS resolution failed across all configured endpoints. "
            "Check your DNS/firewall/VPN and set OPENROUTER_API_URLS in .env if needed.",
            503,
        ) from last_exception
    raise GenerationError("API request failed unexpectedly.", 503)


def generate_with_model_fallback(prompt: str, preferred_model: str | None = None):
    """Try available model candidates and skip unsupported model names."""
    candidates = []
    if preferred_model:
        candidates.append(preferred_model)
    candidates.extend(DEFAULT_MODEL_CANDIDATES)

    # Preserve order while removing duplicates.
    unique_candidates = list(dict.fromkeys(candidates))

    last_error = None
    for model_name in unique_candidates:
        model = genai.GenerativeModel(model_name)
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                response = model.generate_content(prompt)
                return response, model_name
            except Exception as e:
                msg = str(e).lower()

                is_model_not_found = (
                    "not found" in msg
                    or "models/" in msg
                    or "listmodels" in msg
                    or "unsupported for generatecontent" in msg
                )
                if is_model_not_found:
                    last_error = e
                    break

                is_rate_limited = "quota" in msg or "429" in msg or "rate limit" in msg
                if is_rate_limited and attempt < MAX_RATE_LIMIT_RETRIES:
                    wait_seconds = parse_retry_seconds(str(e)) or DEFAULT_RETRY_SECONDS
                    # Keep wait bounded so requests do not hang too long.
                    time.sleep(min(wait_seconds, 20))
                    continue

                raise

    if last_error:
        raise last_error
    raise RuntimeError("No compatible Gemini model was found for this API key.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history")
def history_page():
    return render_template("history.html")


@app.route("/session")
def session_page():
    return render_template("session.html")


@app.route("/api/history", methods=["GET"])
def list_history():
    return jsonify({"items": _read_history()})


@app.route("/api/history", methods=["POST"])
def create_history_item():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid request body."}), 400

    session_id = str(payload.get("id", "")).strip()
    refined_prompt = str(payload.get("refinedPrompt", "")).strip()
    if not session_id or not refined_prompt:
        return jsonify({"error": "Missing required session fields."}), 400

    history = _read_history()
    history = [item for item in history if str(item.get("id", "")) != session_id]
    history.insert(0, payload)
    _write_history(history)
    return jsonify({"ok": True})


@app.route("/api/history", methods=["DELETE"])
def clear_history():
    _write_history([])
    return jsonify({"ok": True})


@app.route("/api/history/<session_id>", methods=["GET"])
def get_history_item(session_id: str):
    history = _read_history()
    for item in history:
        if str(item.get("id", "")) == session_id:
            return jsonify({"item": item})
    return jsonify({"error": "Session not found."}), 404


@app.route("/auto-answer", methods=["POST"])
def auto_answer():
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL
    api_key = os.getenv("GEMINI_API_KEY")
    preferred_model = os.getenv("GEMINI_MODEL", "").strip() or None

    if provider in ("openrouter", "nvidia") and not openrouter_api_key:
        return jsonify({"error": "API key not configured."}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body."}), 400

    project_desc = str(data.get("project_description", "")).strip()
    question = str(data.get("question", "")).strip()
    if not question:
        return jsonify({"error": "No question provided."}), 400

    prompt = f"""You are helping spec out a software project. Given the project description and a clarifying question, provide a concise, practical answer that makes smart default choices.

PROJECT: \"{project_desc}\"

QUESTION: \"{question}\"

Rules:
- Answer in 1-3 sentences max
- Pick sensible, modern defaults (e.g. React for frontend, PostgreSQL for DB, JWT for auth)
- Be specific and decisive, not wishy-washy
- Just the answer text, no quotes, no prefixes"""

    try:
        answer_text = _call_llm(prompt, provider, openrouter_api_key, openrouter_model, api_key, preferred_model)
        # Clean up: remove quotes, "Answer:" prefix, extra whitespace
        answer_text = answer_text.strip().strip('"').strip()
        if answer_text.lower().startswith("answer:"):
            answer_text = answer_text[7:].strip()
        return jsonify({"answer": answer_text})
    except GenerationError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _validate_meaningful_text(text: str) -> str | None:
    """Return an error message if text is gibberish/random, else None."""
    if not text or not text.strip():
        return "Please provide a description."

    cleaned = text.strip()

    if len(cleaned) < 10:
        return "Description is too short. Please write at least a sentence about your project idea."

    if re.search(r'(.)\1{4,}', cleaned):
        return "Please provide a meaningful project description, not repeated characters."

    words = re.findall(r'[a-zA-Z]{3,}', cleaned)
    if len(words) < 3:
        return "Please describe your project idea in plain English with at least a few words."

    def _is_gibberish_word(word: str) -> bool:
        w = word.lower()
        if len(w) < 4:
            return False
        vowels = sum(1 for c in w if c in 'aeiou')
        ratio = vowels / len(w)
        if ratio < 0.15 or ratio > 0.85:
            return True
        # Long consonant runs (4+ consonants in a row)
        if re.search(r'[^aeiou]{4,}', w):
            return True
        # Repeated chars (3+)
        if re.search(r'(.)\1{2,}', w):
            return True
        # No common English bigrams — strong gibberish signal for longer words
        common = ['th','he','in','er','an','re','on','at','en','nd',
                   'ti','es','or','te','of','ed','is','it','al','ar',
                   'st','to','nt','ng','se','ha','as','ou','io','le',
                   've','co','me','de','hi','ri','ro','ic','ne','ea',
                   'ra','ce','li','ch','ll','be','ma','si','om','ur',
                   'la','no','ta','el','ni','di','na','pe','ec','ca',
                   'ad','bi','bu','da','do','fi','fo','ge','gi','go',
                   'gr','gu','ho','hu','id','im','ke','ki','lo','lu',
                   'mi','mo','mu','ob','op','ot','pa','pi','po','pr',
                   'pu','qu','sa','sc','sh','sk','sl','sm','sn','so',
                   'sp','sq','su','sw','sy','tr','tu','ty','ul','um',
                   'un','up','us','ut','vi','vo','wa','we','wi','wo']
        found = sum(1 for bg in common if bg in w)
        if len(w) >= 6 and found == 0:
            return True
        return False

    gibberish_words = [w for w in words if _is_gibberish_word(w)]
    real_words = [w for w in words if not _is_gibberish_word(w)]

    # Any gibberish word present → reject
    if gibberish_words:
        return (
            "Part of your description doesn't look like real words. "
            "Please describe your project clearly in plain English."
        )

    if len(real_words) < 3:
        return "Please describe your project idea with at least a few clear words."

    return None


def _call_llm(prompt: str, provider: str, openrouter_api_key: str, openrouter_model: str, api_key: str, preferred_model: str | None) -> str:
    """Shared LLM call logic with provider fallback. Returns raw text."""
    if provider in ("openrouter", "nvidia"):
        try:
            text, _ = generate_with_openrouter(prompt, openrouter_api_key, openrouter_model)
            return text
        except GenerationError as e:
            if api_key and e.status_code >= 500:
                genai.configure(api_key=api_key)
                response, _ = generate_with_model_fallback(prompt, preferred_model)
                return response.text
            raise
    else:
        genai.configure(api_key=api_key)
        response, _ = generate_with_model_fallback(prompt, preferred_model)
        return response.text


@app.route("/ask", methods=["POST"])
def ask():
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL
    api_key = os.getenv("GEMINI_API_KEY")
    preferred_model = os.getenv("GEMINI_MODEL", "").strip() or None

    if provider in ("openrouter", "nvidia") and not openrouter_api_key:
        return jsonify({"error": "API key not configured. Add OPENROUTER_API_KEY to your .env file."}), 500
    if provider == "gemini" and not api_key:
        return jsonify({"error": "API key not configured. Add GEMINI_API_KEY to your .env file."}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body."}), 400

    user_input = data.get("description", "").strip()
    answers = data.get("answers", [])
    asked_questions = data.get("asked_questions", [])
    if not user_input:
        return jsonify({"error": "Please provide a description."}), 400
    if len(user_input) > 2000:
        return jsonify({"error": "Description too long (max 2000 characters)."}), 400

    validation_error = _validate_meaningful_text(user_input)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    safe_input = user_input.replace("\\", "\\\\").replace('"', '\\"')

    # Include already provided answers to generate focused follow-up questions.
    if answers and isinstance(answers, list):
        lines = ["ALREADY PROVIDED ANSWERS (do not repeat these as questions):\n"]
        for qa in answers:
            q = str(qa.get("question", "")).strip()
            a = str(qa.get("answer", "")).strip()
            if q and a:
                lines.append(f"  Q: {q}\n  A: {a}\n")
        answers_section = "\n".join(lines) + "\n\n"
    else:
        answers_section = ""

    if asked_questions and isinstance(asked_questions, list):
        asked_lines = ["ALREADY ASKED QUESTIONS (ask only NEW additional questions):\n"]
        for q in asked_questions:
            question_text = str(q).strip()
            if question_text:
                asked_lines.append(f"  - {question_text}")
        asked_section = "\n".join(asked_lines) + "\n\n"
    else:
        asked_section = ""

    prompt = ASK_PROMPT_TEMPLATE.format(user_input=safe_input, answers_section=f"{answers_section}{asked_section}")

    try:
        result = None
        last_text = ""
        for _attempt in range(2):
            last_text = _call_llm(prompt, provider, openrouter_api_key, openrouter_model, api_key, preferred_model)
            logger.debug("/ask raw LLM response (first 500 chars): %s", last_text[:500])
            result = extract_json(last_text)
            if result is not None and isinstance(result.get("questions"), list):
                break
            logger.warning("/ask parse attempt %d failed, retrying...", _attempt + 1)
            result = None
            time.sleep(1)

        if result is None:
            logger.error("/ask could not parse after retries. Full response: %s", last_text[:2000])
            return jsonify({"error": "Could not parse AI response. Please try again."}), 500
        if "questions" not in result or not isinstance(result.get("questions"), list):
            return jsonify({"error": "AI response missing questions. Please try again."}), 500

        normalized_questions = []
        asked_set = {
            str(q).strip().lower()
            for q in asked_questions
            if isinstance(q, str) and str(q).strip()
        }

        for idx, q in enumerate(result.get("questions", []), start=1):
            if not isinstance(q, dict):
                continue
            question_text = str(q.get("question", "")).strip()
            if not question_text:
                continue
            question_key = question_text.lower()
            if question_key in asked_set:
                continue

            normalized_questions.append(
                {
                    "id": int(q.get("id", idx)) if str(q.get("id", "")).isdigit() else idx,
                    "category": str(q.get("category", "scope")).strip().lower() or "scope",
                    "question": question_text,
                    "hint": str(q.get("hint", "")).strip(),
                    "why": str(q.get("why", "")).strip(),
                }
            )
            asked_set.add(question_key)

        if not normalized_questions:
            return jsonify({"error": "Could not generate usable questions. Please try again."}), 500

        result["questions"] = normalized_questions

        return jsonify(result)

    except GenerationError as e:
        payload = {"error": e.message}
        if e.retry_seconds is not None:
            payload["retry_seconds"] = e.retry_seconds
        return jsonify(payload), e.status_code
    except Exception as e:
        return jsonify({"error": f"Failed to generate questions: {str(e)}"}), 500


@app.route("/generate", methods=["POST"])
def generate():
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL
    api_key = os.getenv("GEMINI_API_KEY")
    preferred_model = os.getenv("GEMINI_MODEL", "").strip() or None
    if provider in ("openrouter", "nvidia") and not openrouter_api_key:
        return jsonify({"error": "API key not configured. Add OPENROUTER_API_KEY to your .env file."}), 500
    if provider == "gemini" and not api_key:
        return jsonify({"error": "API key not configured. Add GEMINI_API_KEY to your .env file."}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body."}), 400

    user_input = data.get("description", "").strip()
    style = data.get("style", "auto")

    if not user_input:
        return jsonify({"error": "Please provide a description."}), 400
    if len(user_input) > 2000:
        return jsonify({"error": "Description too long (max 2000 characters)."}), 400

    validation_error = _validate_meaningful_text(user_input)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    if style not in ("auto", "structured", "conversational"):
        style = "auto"

    # Safely embed user input in the prompt
    safe_input = user_input.replace("\\", "\\\\").replace('"', '\\"')

    # Build Q&A section from user's clarifying answers
    answers = data.get("answers", [])
    if answers and isinstance(answers, list):
        qa_lines = ["CLARIFYING Q&A (weave these answers naturally into the prompt):\n"]
        for qa in answers:
            q = str(qa.get("question", "")).strip()
            a = str(qa.get("answer", "")).strip()
            if q and a:
                qa_lines.append(f"  Q: {q}\n  A: {a}\n")
        qa_section = "\n".join(qa_lines) + "\n\n"
    else:
        qa_section = ""

    prompt = META_PROMPT_TEMPLATE.format(style="structured", user_input=safe_input, qa_section=qa_section)

    try:
        if provider not in ("openrouter", "nvidia", "gemini"):
            return jsonify({"error": "Unsupported LLM_PROVIDER. Use 'nvidia', 'openrouter', or 'gemini'."}), 400

        result = None
        last_text = ""
        model_used = openrouter_model if provider in ("openrouter", "nvidia") else "gemini"
        for _attempt in range(2):
            last_text = _call_llm(prompt, provider, openrouter_api_key, openrouter_model, api_key, preferred_model)
            logger.debug("/generate raw LLM response (first 500 chars): %s", last_text[:500])
            result = extract_json(last_text)
            if result is not None and "refined_prompt" in result:
                break
            logger.warning("/generate parse attempt %d failed, retrying...", _attempt + 1)
            result = None
            time.sleep(1)

        if result is None:
            logger.error("/generate could not parse after retries. Full response: %s", last_text[:2000])
            return jsonify({"error": "Could not parse AI response. Please try again."}), 500

        required_fields = ["task_type", "refined_prompt", "explanation", "style_used"]
        for field in required_fields:
            if field not in result:
                return jsonify({"error": f"Incomplete AI response (missing: {field}). Try again."}), 500

        result["model_used"] = model_used
        result["provider_used"] = provider
        return jsonify(result)

    except GenerationError as e:
        payload = {"error": e.message}
        if e.retry_seconds is not None:
            payload["retry_seconds"] = e.retry_seconds
        return jsonify(payload), e.status_code

    except Exception as e:
        msg = str(e)
        if "api_key" in msg.lower() or "api key" in msg.lower() or "401" in msg:
            return jsonify({"error": "Invalid API key. Check your GEMINI_API_KEY in .env."}), 401
        if "quota" in msg.lower() or "429" in msg:
            retry_seconds = parse_retry_seconds(msg) or DEFAULT_RETRY_SECONDS
            return jsonify({
                "error": f"Rate limit hit. Please wait about {retry_seconds} seconds and try again.",
                "retry_seconds": retry_seconds,
            }), 429
        return jsonify({"error": f"Generation failed: {msg}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
