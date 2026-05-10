import atexit
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import gradio as gr
import pyttsx3
import requests
import edge_tts
from faster_whisper import WhisperModel
from openai import OpenAI


# ============================================================
# My Local Voice ChatGPT
# ============================================================
# 功能：
# 1. 可以定义自己的 My ChatGPT：system prompt / 角色设定
# 2. 支持文字输入
# 3. 支持麦克风语音输入：录音 -> faster-whisper -> 文本
# 4. 支持语音输出：LLM 回答 -> edge-tts / pyttsx3 / OpenAI TTS
# 5. 支持老师头像：播放语音时 teacher_speaking.gif，停止/暂停时 teacher.gif
# 6. 支持 OpenAI API / Local LM Studio
# 7. 支持保存 / 读取设定，导出对话历史
# ============================================================


APP_DIR = Path(__file__).parent
PRESET_FILE = APP_DIR / "my_chatgpt_preset.json"
OPENAI_API_KEY_FILE = APP_DIR / "openai_api_key.txt"

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1/chat/completions")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5-1.5b-instruct-unsloth-bnb-thinker")

OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "nova")
EDGE_TTS_EN_VOICE = os.getenv("EDGE_TTS_EN_VOICE", "en-US-JennyNeural")
EDGE_TTS_ZH_VOICE = os.getenv("EDGE_TTS_ZH_VOICE", "zh-CN-XiaoxiaoNeural")

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL_NAME", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")


# Windows 上 edge-tts / aiohttp 有时会在 Proactor event loop 关闭连接时打印 ConnectionResetError。
# 切换到 SelectorEventLoop 通常更稳定。
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception as e:
        print("[edge-tts] Failed to set WindowsSelectorEventLoopPolicy:", e)


DEFAULT_MY_CHATGPT = """你是我的 TOEIC 英语听力练习导师。

你的目标：
帮助我用输入的 10 个英语单词，进行 TOEIC Part 3 / Part 4 风格的听力训练。

核心规则：
1. 当我输入 10 个英语单词时，你必须使用全部这 10 个单词，创作一篇自然的 TOEIC 英语听力短文。
2. 这篇短文要像 TOEIC 听力材料一样，可以是：
   - workplace announcement
   - business conversation
   - phone message
   - meeting update
   - travel / schedule / reservation information
   - office problem and solution
3. 短文长度控制在 120 到 180 个英文单词左右。
4. 英文难度控制在 TOEIC 600 到 800 分区间。
5. 文章中必须自然使用全部 10 个单词，不要生硬堆砌。
6. 生成短文后，必须准备 5 个理解问题。
7. 但是不要一次性把 5 个问题全部问出来。
8. 生成文章后，只提出第 1 个问题。
9. 我回答后，你要评价我的回答：
   - 先判断我的答案是否正确
   - 如果不完整，要指出缺少的信息
   - 给出更自然的英文回答示例
   - 用中文简短解释
10. 当我输入 next 时，你再提出下一个问题。
11. 依次完成第 1 到第 5 个问题。
12. 第 5 个问题完成后，给我一个总评：
   - 听力理解表现
   - 答题准确度
   - 需要复习的关键词
   - 建议我如何继续练习

非常重要：
- 你必须记住当前这篇短文和 5 个问题的顺序。
- 如果我还没有输入 10 个单词，请提醒我输入 10 个单词。
- 如果我输入的不是 10 个单词，请告诉我数量不对，并让我重新输入。
- 如果我输入中文，你可以用中文解释，但听力短文和问题必须主要使用英文。
- 不要提前公布所有 5 个问题。
- 不要在我回答前直接给出答案。
- 每次只问一个问题。
- 如果我说 repeat，请重复当前问题。
- 如果我说 article，请再次显示当前听力短文。
- 如果我说 answer，请给出当前问题的参考答案并解释。
- 如果我说 restart，请重新等待我输入新的 10 个单词。

输出流程：
第一步：我输入 10 个单词后，你输出：
1. TOEIC Listening Passage
2. Question 1

第二步：我回答 Question 1 后，你输出：
1. Evaluation
2. Better Answer
3. Short Chinese Explanation
4. 提醒我输入 next 进入下一题

第三步：我输入 next 后，你输出 Question 2。
后续问题依次进行，直到 Question 5 完成。

回答风格：
- 你要像一个耐心、专业、鼓励型的英语听力老师。
- 英文问题要自然，接近 TOEIC 真题风格。
- 中文解释要简洁清楚。
- 不要使用 markdown 星号。
"""

DEFAULT_FIRST_MESSAGE = """你好，我是你的本地语音版 My ChatGPT。

左边可以定义我的角色、回答风格、专业领域。
右边可以文字输入，也可以用麦克风语音输入。
"""

TEMP_AUDIO_FILES: List[str] = []


# ============================================================
# OpenAI / Local LLM
# ============================================================
def load_openai_api_key() -> str:
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key

    if OPENAI_API_KEY_FILE.exists():
        return OPENAI_API_KEY_FILE.read_text(encoding="utf-8").strip()

    return ""


def get_openai_client():
    api_key = load_openai_api_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def normalize_messages(chatbot_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    当前 Gradio 环境：
    - 不接受 gr.Chatbot(type="messages") 参数
    - 但内部默认使用 messages 格式

    因此 Chatbot value / history 使用：
      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    messages = []
    for item in chatbot_history or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content", "")
        if role in ("user", "assistant") and str(content).strip():
            messages.append({"role": role, "content": str(content)})
    return messages


def remove_initial_greeting(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    不把页面初始欢迎语发送给 LLM，避免干扰模型上下文。
    """
    if messages and messages[0].get("role") == "assistant" and DEFAULT_FIRST_MESSAGE.strip() in messages[0].get("content", ""):
        return messages[1:]
    return messages


def call_openai(system_prompt: str, user_message: str, history: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
    client = get_openai_client()
    if client is None:
        return (
            "OpenAI API Key 没有设置。\n\n"
            "设置方法一：在 PowerShell 中执行：\n"
            '$env:OPENAI_API_KEY="sk-你的key"\n'
            "python app.py\n\n"
            "设置方法二：在 app.py 同目录创建 openai_api_key.txt，把 key 写进去。"
        )

    messages = [{"role": "system", "content": system_prompt.strip()}]
    messages.extend(remove_initial_greeting(normalize_messages(history)))
    messages.append({"role": "user", "content": user_message.strip()})

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        return f"OpenAI API 调用失败：{e}"


def call_local_llm(system_prompt: str, user_message: str, history: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
    messages = [{"role": "system", "content": system_prompt.strip()}]
    messages.extend(remove_initial_greeting(normalize_messages(history)))
    messages.append({"role": "user", "content": user_message.strip()})

    try:
        response = requests.post(
            LOCAL_LLM_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": LOCAL_LLM_MODEL,
                "messages": messages,
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
                "stream": False,
            },
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return (
            "本地 LLM 调用失败：\n"
            f"{e}\n\n"
            "请确认：\n"
            "1. LM Studio Server 已启动。\n"
            "2. Server URL 是 http://localhost:1234/v1/chat/completions。\n"
            "3. 模型名和 LOCAL_LLM_MODEL 一致。\n"
            "4. 如果你使用 Ollama 或 llama.cpp，需要打开 OpenAI-compatible API。"
        )


def call_llm(provider: str, system_prompt: str, user_message: str, history: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
    if not system_prompt.strip():
        system_prompt = "You are a helpful assistant."

    if provider == "Local LM Studio":
        return call_local_llm(system_prompt, user_message, history, temperature, max_tokens)

    return call_openai(system_prompt, user_message, history, temperature, max_tokens)


# ============================================================
# Avatar
# ============================================================
def check_teacher_avatar_file() -> None:
    idle_path = APP_DIR / "teacher.gif"
    speaking_path = APP_DIR / "teacher_speaking.gif"

    if idle_path.exists():
        print("[Avatar] Found local idle teacher image:", idle_path)
    else:
        print("[Avatar] WARNING: teacher.gif not found next to app.py.")

    if speaking_path.exists():
        print("[Avatar] Found local speaking teacher image:", speaking_path)
    else:
        print("[Avatar] WARNING: teacher_speaking.gif not found next to app.py.")


def get_teacher_idle_path() -> str:
    path = APP_DIR / "teacher.gif"
    return str(path) if path.exists() else ""


def get_teacher_speaking_path() -> str:
    path = APP_DIR / "teacher_speaking.gif"
    return str(path) if path.exists() else get_teacher_idle_path()


def set_teacher_idle():
    return get_teacher_idle_path()


def set_teacher_speaking():
    return get_teacher_speaking_path()


# ============================================================
# Whisper
# ============================================================
print("[Whisper] Loading model:", WHISPER_MODEL_NAME, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
whisper_model = WhisperModel(
    WHISPER_MODEL_NAME,
    device=WHISPER_DEVICE,
    compute_type=WHISPER_COMPUTE_TYPE,
)


def transcribe_audio(audio_path: Optional[str]) -> str:
    if not audio_path:
        print("[Whisper] No audio_path received")
        return ""

    print("[Whisper] Transcribing audio:", audio_path)

    try:
        segments, info = whisper_model.transcribe(
            audio_path,
            initial_prompt="The speech may be Chinese, English, or Japanese.",
            vad_filter=False,
            beam_size=5,
        )

        texts = []
        print("[Whisper] Detected language:", info.language)
        print("[Whisper] Duration:", info.duration)

        for seg in segments:
            print("[Whisper] Segment:", seg.text)
            texts.append(seg.text.strip())

        text = " ".join(texts).strip()
        print("[Whisper] Final text:", text)
        return text

    except Exception as e:
        print("[Whisper] Error:", e)
        return ""


# ============================================================
# TTS
# ============================================================
def cleanup_temp_audio_files() -> None:
    global TEMP_AUDIO_FILES
    remaining = []

    for path in TEMP_AUDIO_FILES:
        try:
            if path and os.path.exists(path):
                os.remove(path)
                print("[TTS] Deleted old audio:", path)
        except Exception as e:
            print("[TTS] Failed to delete old audio:", path, e)
            remaining.append(path)

    TEMP_AUDIO_FILES = remaining


atexit.register(cleanup_temp_audio_files)


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text or "")


def clean_tts_text(text: str) -> str:
    text = text or ""
    # 让朗读更自然一点，避免读出太多 markdown 符号
    for token in ["**", "__", "```", "###", "##", "#"]:
        text = text.replace(token, "")
    return text.strip()


def select_voice(engine: pyttsx3.Engine, language: str) -> None:
    voices = engine.getProperty("voices")
    language = language.lower().strip()

    if language == "zh":
        preferred_keywords = [
            "huihui", "yaoyao", "xiaoxiao", "xiaoyi", "xiaobei",
            "kangkang", "chinese", "mandarin", "zh-cn", "zh_",
        ]
        for voice in voices:
            combined = f"{voice.name or ''} {voice.id or ''}".lower()
            if any(keyword in combined for keyword in preferred_keywords):
                engine.setProperty("voice", voice.id)
                print("[TTS] Selected Chinese voice:", voice.name)
                return
        print("[TTS] No Chinese voice found. Using default voice.")
        return

    female_keywords = ["zira", "aria", "jenny", "sonia", "hazel", "susan", "heather", "samantha", "female"]
    english_keywords = ["english", "en-us", "en-gb", "en_", "en-"]

    for voice in voices:
        combined = f"{voice.name or ''} {voice.id or ''}".lower()
        if any(k in combined for k in female_keywords) and any(k in combined for k in english_keywords):
            engine.setProperty("voice", voice.id)
            print("[TTS] Selected female English voice:", voice.name)
            return

    for voice in voices:
        combined = f"{voice.name or ''} {voice.id or ''}".lower()
        if any(k in combined for k in english_keywords):
            engine.setProperty("voice", voice.id)
            print("[TTS] Selected English voice:", voice.name)
            return

    print("[TTS] No English voice found. Using default voice.")


def create_pyttsx3_file(text: str, language: str = "en", cleanup_before: bool = True) -> Optional[str]:
    global TEMP_AUDIO_FILES

    text = clean_tts_text(text)
    if not text:
        return None

    if cleanup_before:
        cleanup_temp_audio_files()

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 165 if language == "en" else 175)
        engine.setProperty("volume", 1.0)
        select_voice(engine, language)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        engine.stop()

        TEMP_AUDIO_FILES.append(output_path)
        print("[pyttsx3] Saved audio:", output_path)
        return output_path
    except Exception as e:
        print("[pyttsx3] Error:", e)
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass
        return None


async def edge_tts_save_async(text: str, output_path: str, voice: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)


def create_edge_tts_file(text: str, language: str = "en", cleanup_before: bool = True) -> Optional[str]:
    global TEMP_AUDIO_FILES

    text = clean_tts_text(text)
    if not text:
        return None

    if cleanup_before:
        cleanup_temp_audio_files()

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    voice = EDGE_TTS_ZH_VOICE if language == "zh" or contains_cjk(text) else EDGE_TTS_EN_VOICE

    try:
        print("[edge-tts] Voice:", voice)
        asyncio.run(edge_tts_save_async(text, output_path, voice))

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise RuntimeError("edge-tts generated audio is empty or too small")

        TEMP_AUDIO_FILES.append(output_path)
        print("[edge-tts] Saved audio:", output_path)
        return output_path
    except Exception as e:
        print("[edge-tts] Error:", e)
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass

        print("[edge-tts] Falling back to pyttsx3.")
        return create_pyttsx3_file(text, language=language, cleanup_before=False)


def create_openai_tts_file(text: str, language: str = "en", cleanup_before: bool = True) -> Optional[str]:
    global TEMP_AUDIO_FILES

    text = clean_tts_text(text)
    if not text:
        return None

    client = get_openai_client()
    if client is None:
        print("[OpenAI TTS] No OpenAI API Key. Falling back to pyttsx3.")
        return create_pyttsx3_file(text, language=language, cleanup_before=cleanup_before)

    if cleanup_before:
        cleanup_temp_audio_files()

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name

    try:
        print("[OpenAI TTS] Model:", OPENAI_TTS_MODEL)
        print("[OpenAI TTS] Voice:", OPENAI_TTS_VOICE)

        with client.audio.speech.with_streaming_response.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=text,
            response_format="mp3",
        ) as response:
            response.stream_to_file(output_path)

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise RuntimeError("OpenAI TTS generated audio is empty or too small")

        TEMP_AUDIO_FILES.append(output_path)
        print("[OpenAI TTS] Saved audio:", output_path)
        return output_path
    except Exception as e:
        print("[OpenAI TTS] Error:", e)
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass

        print("[OpenAI TTS] Falling back to pyttsx3.")
        return create_pyttsx3_file(text, language=language, cleanup_before=False)


def synthesize_tts_file(tts_provider: str, text: str, cleanup_before: bool = True) -> Optional[str]:
    lang = "zh" if contains_cjk(text) else "en"

    if tts_provider == "OpenAI TTS API":
        return create_openai_tts_file(text, language=lang, cleanup_before=cleanup_before)

    if tts_provider == "pyttsx3":
        return create_pyttsx3_file(text, language=lang, cleanup_before=cleanup_before)

    return create_edge_tts_file(text, language=lang, cleanup_before=cleanup_before)


# ============================================================
# Gradio event functions
# ============================================================
def append_chat_history(chatbot_history: List[Dict[str, str]], user_message: str, assistant_reply: str) -> List[Dict[str, str]]:
    chatbot_history = chatbot_history or []
    chatbot_history = normalize_messages(chatbot_history)
    chatbot_history.append({"role": "user", "content": user_message})
    chatbot_history.append({"role": "assistant", "content": assistant_reply})
    return chatbot_history


def text_chat_once(
    provider: str,
    tts_provider: str,
    system_prompt: str,
    user_message: str,
    chatbot_history: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
):
    user_message = (user_message or "").strip()
    chatbot_history = chatbot_history or []

    if not user_message:
        return chatbot_history, "", None, get_teacher_idle_path(), ""

    reply = call_llm(provider, system_prompt, user_message, chatbot_history, temperature, max_tokens)
    audio_reply = synthesize_tts_file(tts_provider, reply, cleanup_before=True)
    new_history = append_chat_history(chatbot_history, user_message, reply)

    return new_history, "", audio_reply, get_teacher_speaking_path(), user_message


def voice_chat_once(
    provider: str,
    tts_provider: str,
    system_prompt: str,
    audio_path: Optional[str],
    chatbot_history: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
):
    chatbot_history = chatbot_history or []

    if not audio_path:
        return (
            chatbot_history,
            "没有收到录音文件。请先录音，停止录音后会自动发送。",
            None,
            gr.update(value=None),
            get_teacher_idle_path(),
        )

    transcript = transcribe_audio(audio_path)

    if not transcript:
        return (
            chatbot_history,
            "Whisper 没有识别到语音。请说长一点、声音大一点，并确认麦克风权限正常。",
            None,
            gr.update(value=None),
            get_teacher_idle_path(),
        )

    reply = call_llm(provider, system_prompt, transcript, chatbot_history, temperature, max_tokens)
    audio_reply = synthesize_tts_file(tts_provider, reply, cleanup_before=True)
    new_history = append_chat_history(chatbot_history, transcript, reply)

    return new_history, transcript, audio_reply, gr.update(value=None), get_teacher_speaking_path()


def clear_chat() -> List[Dict[str, str]]:
    return [{"role": "assistant", "content": DEFAULT_FIRST_MESSAGE}]


def save_my_chatgpt(system_prompt: str) -> str:
    data = {
        "system_prompt": system_prompt or "",
        "openai_model": OPENAI_MODEL,
        "local_llm_url": LOCAL_LLM_URL,
        "local_llm_model": LOCAL_LLM_MODEL,
        "openai_tts_model": OPENAI_TTS_MODEL,
        "openai_tts_voice": OPENAI_TTS_VOICE,
        "edge_tts_en_voice": EDGE_TTS_EN_VOICE,
        "edge_tts_zh_voice": EDGE_TTS_ZH_VOICE,
        "whisper_model": WHISPER_MODEL_NAME,
    }
    PRESET_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"已保存到：{PRESET_FILE}"


def load_my_chatgpt() -> Tuple[str, str]:
    if not PRESET_FILE.exists():
        return DEFAULT_MY_CHATGPT, "还没有保存过设定，已载入默认设定。"

    try:
        data = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
        return data.get("system_prompt", DEFAULT_MY_CHATGPT), f"已读取：{PRESET_FILE}"
    except Exception as e:
        return DEFAULT_MY_CHATGPT, f"读取失败，已载入默认设定：{e}"


def export_chat(chatbot_history: List[Dict[str, str]]) -> str:
    chatbot_history = normalize_messages(chatbot_history or [])
    lines = []

    for item in chatbot_history:
        role = item.get("role", "")
        content = item.get("content", "")
        if not content:
            continue

        if role == "user":
            lines.append(f"User:\n{content}\n")
        elif role == "assistant":
            lines.append(f"Assistant:\n{content}\n")

    output_path = APP_DIR / "chat_history.txt"
    output_path.write_text("\n".join(lines).strip(), encoding="utf-8")
    return str(output_path)


# ============================================================
# UI CSS
# ============================================================
CUSTOM_CSS = """
textarea {
  font-size: 16px !important;
  line-height: 1.55 !important;
}

#send_button button {
  min-height: 48px !important;
  font-size: 18px !important;
  font-weight: 700 !important;
}

#main_title {
  text-align: center;
  margin-bottom: 8px;
}

#main_title h1 {
  font-size: 30px;
  margin-bottom: 4px;
}

#main_title p {
  color: #666;
  font-size: 15px;
}

audio {
  width: 100% !important;
}
"""


# Gradio 6.0：css 放到 launch()，不要放到 Blocks()。
with gr.Blocks(title="My Local Voice ChatGPT") as demo:
    gr.HTML(
        """
        <div id="main_title">
          <h1>My Local Voice ChatGPT</h1>
          <p>本地运行 · 自定义 My ChatGPT · 文字输入 / 语音输入 · 自动朗读 · 老师头像切换</p>
        </div>
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## ① 定义 My ChatGPT")

            provider = gr.Radio(
                choices=["OpenAI API", "Local LM Studio"],
                value="OpenAI API",
                label="LLM 调用方式",
                info="想完全本地运行就选 Local LM Studio；想用 OpenAI 就选 OpenAI API。",
            )

            tts_provider = gr.Radio(
                choices=["edge-tts", "pyttsx3", "OpenAI TTS API"],
                value="OpenAI TTS API",
                label="TTS 朗读方式",
                info="edge-tts 需要联网；pyttsx3 更接近完全本地；OpenAI TTS API 需要 OpenAI Key。",
            )

            system_prompt = gr.Textbox(
                label="My ChatGPT 设定 / System Prompt",
                value=DEFAULT_MY_CHATGPT,
                lines=18,
                placeholder="在这里定义你的 My ChatGPT，比如：角色、语气、专业领域、回答格式、禁止事项等。",
            )

            with gr.Row():
                save_btn = gr.Button("保存设定")
                load_btn = gr.Button("读取设定")

            preset_status = gr.Textbox(
                label="设定保存状态",
                value="",
                lines=2,
                interactive=False,
            )

            with gr.Accordion("模型 / 语音连接信息", open=False):
                gr.Markdown(
                    f"""
OpenAI 模型：`{OPENAI_MODEL}`

本地 LLM URL：`{LOCAL_LLM_URL}`

本地模型名：`{LOCAL_LLM_MODEL}`

Whisper 模型：`{WHISPER_MODEL_NAME}` / `{WHISPER_DEVICE}` / `{WHISPER_COMPUTE_TYPE}`

OpenAI TTS：`{OPENAI_TTS_MODEL}` / `{OPENAI_TTS_VOICE}`

edge-tts 英文 Voice：`{EDGE_TTS_EN_VOICE}`

edge-tts 中文 Voice：`{EDGE_TTS_ZH_VOICE}`

PowerShell 修改例子：

`$env:LOCAL_LLM_MODEL="你的模型名"`

`$env:WHISPER_MODEL_NAME="base"`

`$env:EDGE_TTS_EN_VOICE="en-US-JennyNeural"`
"""
                )

            with gr.Accordion("生成参数", open=False):
                temperature = gr.Slider(
                    minimum=0,
                    maximum=1.5,
                    value=0.7,
                    step=0.1,
                    label="temperature",
                    info="越低越稳定，越高越有创造性。",
                )
                max_tokens = gr.Slider(
                    minimum=128,
                    maximum=4096,
                    value=1024,
                    step=128,
                    label="max_tokens",
                    info="回答最大长度。本地小模型建议 512-1024。",
                )

        with gr.Column(scale=1):
            teacher_image = gr.Image(
                value=get_teacher_idle_path(),
                label="Emily · Your AI Teacher",
                type="filepath",
                height=420,
                interactive=False,
            )

            audio_reply_output = gr.Audio(
                label="回答朗读",
                type="filepath",
                autoplay=True,
            )

            transcript_output = gr.Textbox(
                label="语音识别结果 / 最近一次输入",
                lines=4,
                interactive=False,
            )

        with gr.Column(scale=2):
            gr.Markdown("## ② 用户输入 / 对话")

            # 注意：你的 Gradio 不接受 type="messages"，但默认要求 messages 格式。
            # 所以这里不写 type 参数，但 value 使用 role/content 字典。
            chatbot = gr.Chatbot(
                label="对话窗口",
                value=[{"role": "assistant", "content": DEFAULT_FIRST_MESSAGE}],
                height=560,
            )

            user_input = gr.Textbox(
                label="文字输入",
                placeholder="在这里输入你的问题。例如：帮我解释 AWS VPC Flow Logs；或者：把下面这句话翻译成商务日语。",
                lines=4,
            )

            with gr.Row():
                send_btn = gr.Button("发送文字", elem_id="send_button")
                clear_btn = gr.Button("清空对话")
                export_btn = gr.Button("导出对话")

            gr.Markdown("### 语音输入")
            audio_input = gr.Audio(
                sources=["microphone"],
                type="filepath",
                label="麦克风录音输入（停止录音后自动发送给 LLM）",
            )

            export_file = gr.File(label="下载导出的对话记录")

    send_btn.click(
        fn=text_chat_once,
        inputs=[provider, tts_provider, system_prompt, user_input, chatbot, temperature, max_tokens],
        outputs=[chatbot, user_input, audio_reply_output, teacher_image, transcript_output],
    )

    user_input.submit(
        fn=text_chat_once,
        inputs=[provider, tts_provider, system_prompt, user_input, chatbot, temperature, max_tokens],
        outputs=[chatbot, user_input, audio_reply_output, teacher_image, transcript_output],
    )

    clear_btn.click(
        fn=clear_chat,
        inputs=None,
        outputs=[chatbot],
    )

    save_btn.click(
        fn=save_my_chatgpt,
        inputs=[system_prompt],
        outputs=[preset_status],
    )

    load_btn.click(
        fn=load_my_chatgpt,
        inputs=None,
        outputs=[system_prompt, preset_status],
    )

    export_btn.click(
        fn=export_chat,
        inputs=[chatbot],
        outputs=[export_file],
    )

    # 老师头像：播放音频时切换到 teacher_speaking.gif，暂停/停止时切回 teacher.gif。
    try:
        audio_reply_output.play(fn=set_teacher_speaking, inputs=None, outputs=teacher_image)
        audio_reply_output.pause(fn=set_teacher_idle, inputs=None, outputs=teacher_image)
        audio_reply_output.stop(fn=set_teacher_idle, inputs=None, outputs=teacher_image)
    except Exception as e:
        print("[Avatar] Audio event binding skipped:", e)

    # 录音停止后自动执行：Whisper -> LLM -> TTS -> 更新对话历史。
    _voice_outputs = [
        chatbot,
        transcript_output,
        audio_reply_output,
        audio_input,
        teacher_image,
    ]

    try:
        audio_input.stop_recording(
            fn=voice_chat_once,
            inputs=[provider, tts_provider, system_prompt, audio_input, chatbot, temperature, max_tokens],
            outputs=_voice_outputs,
        )
    except Exception as e:
        print("[UI] audio_input.stop_recording binding failed, fallback to change:", e)
        try:
            audio_input.change(
                fn=voice_chat_once,
                inputs=[provider, tts_provider, system_prompt, audio_input, chatbot, temperature, max_tokens],
                outputs=_voice_outputs,
            )
        except Exception as change_error:
            print("[UI] audio_input.change binding also failed:", change_error)


if __name__ == "__main__":
    check_teacher_avatar_file()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        allowed_paths=[str(APP_DIR), tempfile.gettempdir()],
        css=CUSTOM_CSS,
    )
