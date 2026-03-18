#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
fastmcp tabanlı tek dosya:
- LLM çağrısı + iş mantığı
- MCP server + tool tanımı
"""

from __future__ import annotations

import json
import os
import uuid
from typing import List, Dict, Any, Optional

import requests
from fastmcp import FastMCP


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")

# ============================================================
# STEP-BASED ANALYST (kısa prompt + memory cache)
# ============================================================

AMAC_ENUM = [
    "Özel bankacılıkta karlı büyüme",
    "Ticari bankacılıkta karlı büyüme",
    "Tüzel mobilde işbirlikleri yoluyla kazanımın artması ve müşteri aktifliğini artıracak yeni ürünlerin hayata geçmesi",
    "Şubelerin hızını ve satış potansiyelini artıracak veriye dayalı operasyonel karar süreçlerinin otomatik hale getirilmesi",
    "Operasyonel verimlilik için manuel olan süreçlerin teknoloji ile yeniden tasarlanması",
    "Regülatif /Yasal",
    "Müşteri Deneyimini İyileştirme/Memnuniyetini Artırmak",
]

KANAL_ENUM = [
    "Çağrı Merkezi",
    "İnternet Bankacılığı",
    "Mobil Bankacılık",
    "Şube",
    "ATM",
    "Web",
    "Video Bankacılık",
    "IVR",
    "Servis Bankacılığı",
]

STEP_ORDER: List[str] = [
    "problem",
    "mevcut_durum",
    "fikrin_ozeti",
    "amac",
    "fikrin_aciklamasi",
    "cozum_tipi",
    "kanallar",
    "hedef_kitle",
    "kpi",
    "confirm",
]

STEP_PROMPTS: Dict[str, str] = {
    "problem": 'problem alanını doldur: "Bu fikir ile hangi problemi çözmeyi hedefliyorsunuz?"',
    "mevcut_durum": 'mevcut_durum alanını doldur: "Şu an bu ihtiyaç nasıl karşılanıyor?"',
    "fikrin_ozeti": 'fikrin_ozeti alanını doldur: "Fikrin kısa ve net adı nedir?"',
    "amac": (
        'amac alanını doldur: "Bu fikir hangi amaca hizmet ediyor?" '
        "Sadece şu seçeneklerden birini seç: " + " | ".join(AMAC_ENUM)
    ),
    "fikrin_aciklamasi": 'fikrin_aciklamasi alanını doldur: "Fikrin detaylı açıklaması nedir?"',
    "cozum_tipi": 'cozum_tipi alanını doldur: "Kabaca nasıl bir çözüm yapılmasını istiyorsunuz?"',
    "kanallar": (
        'kanallar alanını doldur: "Bu geliştirme hangi kanallarda kullanılacak?" '
        "Uygun kanalları seç ve dizi döndür. Olası değerler: " + " | ".join(KANAL_ENUM)
    ),
    "hedef_kitle": 'hedef_kitle alanını doldur: "Bu çözümün hedef kitlesi kimler?"',
    "kpi": 'kpi opsiyonel: "Bu fikir ile hangi metriklerde fark yaratmayı hedefliyorsun?" (yoksa null bırak)',
    "confirm": (
        "Tüm alanlar doluysa kurumsal bir özet oluştur ve kullanıcıdan onay iste. "
        "Kullanıcı onay verirse is_confirmed=true döndür."
    ),
}

_STATE_CACHE: Dict[str, Dict[str, Any]] = {}


def _new_state() -> Dict[str, Any]:
    return {
        "current_step": STEP_ORDER[0],
        "fields": {
            "problem": None,
            "mevcut_durum": None,
            "fikrin_ozeti": None,
            "amac": None,
            "fikrin_aciklamasi": None,
            "cozum_tipi": None,
            "kanallar": [],
            "hedef_kitle": None,
            "kpi": None,
        },
        "is_confirmed": False,
        "history": [],  # [{role, content}] kısa chat context
    }


def _summarize_fields(fields: Dict[str, Any]) -> str:
    lines: List[str] = []
    for k in [
        "problem",
        "mevcut_durum",
        "fikrin_ozeti",
        "amac",
        "fikrin_aciklamasi",
        "cozum_tipi",
        "kanallar",
        "hedef_kitle",
        "kpi",
    ]:
        v = fields.get(k)
        if v is None:
            continue
        if isinstance(v, list) and not v:
            continue
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) if lines else "(henüz alan dolmadı)"


def _next_step_name(current_step: str) -> str:
    try:
        idx = STEP_ORDER.index(current_step)
    except ValueError:
        return STEP_ORDER[0]
    return STEP_ORDER[min(idx + 1, len(STEP_ORDER) - 1)]


def _merge_extracted(fields: Dict[str, Any], extracted: Dict[str, Any]) -> None:
    if not isinstance(extracted, dict):
        return
    for k, v in extracted.items():
        if k not in fields:
            continue
        if k == "kanallar":
            if isinstance(v, list):
                cleaned = [x for x in v if isinstance(x, str) and x.strip()]
                fields["kanallar"] = cleaned
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        fields[k] = v


def _parse_json_from_llm(text: str) -> Dict[str, Any]:
    """
    JSON mode destekli backendlerde doğrudan JSON gelir.
    Yine de olası fence/backtick durumları için toleranslı parse eder.
    """
    t = (text or "").strip()
    if not t:
        return {}
    if t.startswith("```"):
        t = t.strip("`")
        t = t.replace("json", "", 1).strip()
    try:
        return json.loads(t)
    except Exception:
        # Son çare: JSON objesi gibi görünen kısmı yakalamaya çalış
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(t[start : end + 1])
            except Exception:
                return {}
        return {}


def _call_llm_json(system_prompt: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    JSON output bekleyen chat/completions çağrısı.
    OpenAI-style response_format destekliyse kullanır.
    """
    openai_messages: List[Dict[str, str]] = []
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})
    openai_messages.extend(messages)

    body: Dict[str, Any] = {
        "model": LLM_MODEL,
        "max_tokens": 2048,
        "temperature": 0,
        "messages": openai_messages,
        "response_format": {"type": "json_object"},
    }

    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    resp = requests.post(url, headers=headers, json=body, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return _parse_json_from_llm(content)


def _call_llm_tools(
    system_prompt: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Tool-calling destekli chat/completions çağrısı.
    Dönen assistant message + tool_calls bilgisini olduğu gibi döndürür.
    """
    openai_messages: List[Dict[str, str]] = []
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})
    openai_messages.extend(messages)

    body: Dict[str, Any] = {
        "model": LLM_MODEL,
        "max_tokens": 1200,
        "temperature": 0,
        "messages": openai_messages,
        "tools": tools,
        "tool_choice": "auto",
    }

    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    resp = requests.post(url, headers=headers, json=body, timeout=90)
    resp.raise_for_status()
    return resp.json()


def _extract_assistant_message_and_tool_calls(
    llm_response: Dict[str, Any],
) -> tuple[str, List[Dict[str, Any]]]:
    choices = llm_response.get("choices") or []
    if not choices:
        return "", []
    msg = (choices[0].get("message") or {}) if isinstance(choices[0], dict) else {}
    content = (msg.get("content") or "").strip()
    tool_calls = msg.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        tool_calls = []
    return content, tool_calls


def _safe_json_loads(s: Any) -> Dict[str, Any]:
    if not isinstance(s, str):
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def _tools_for_step(step: str) -> List[Dict[str, Any]]:
    """
    Her adımda sadece ilgili alanı yazdıracak tool verilir.
    """
    if step == "kanallar":
        return [
            {
                "type": "function",
                "function": {
                    "name": "set_kanallar",
                    "description": "Kanallar alanını doldurur/günceller.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "kanallar": {
                                "type": "array",
                                "items": {"type": "string", "enum": KANAL_ENUM},
                            }
                        },
                        "required": ["kanallar"],
                    },
                },
            }
        ]

    if step == "amac":
        return [
            {
                "type": "function",
                "function": {
                    "name": "set_amac",
                    "description": "Amac alanını doldurur/günceller.",
                    "parameters": {
                        "type": "object",
                        "properties": {"amac": {"type": "string", "enum": AMAC_ENUM}},
                        "required": ["amac"],
                    },
                },
            }
        ]

    if step == "confirm":
        return [
            {
                "type": "function",
                "function": {
                    "name": "confirm_form",
                    "description": "Kullanıcının form onayını işaretler.",
                    "parameters": {
                        "type": "object",
                        "properties": {"is_confirmed": {"type": "boolean"}},
                        "required": ["is_confirmed"],
                    },
                },
            }
        ]

    field_map = {
        "problem": "problem",
        "mevcut_durum": "mevcut_durum",
        "fikrin_ozeti": "fikrin_ozeti",
        "fikrin_aciklamasi": "fikrin_aciklamasi",
        "cozum_tipi": "cozum_tipi",
        "hedef_kitle": "hedef_kitle",
        "kpi": "kpi",
    }
    field_name = field_map.get(step)
    if not field_name:
        return []

    return [
        {
            "type": "function",
            "function": {
                "name": "set_text_field",
                "description": f"{field_name} alanını doldurur/günceller.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                    },
                    "required": ["value"],
                },
            },
        }
    ]


def _default_question_for_step(step: str) -> str:
    """
    Bazı modeller tool_call yapıp content boş dönebilir.
    Bu durumda kullanıcıya gösterilecek fallback soruyu üretir.
    """
    prompts = {
        "problem": "Bu fikir ile hangi problemi çözmeyi hedefliyorsunuz? (Kısaca problemi anlatır mısınız?)",
        "mevcut_durum": "Şu an bu ihtiyaç nasıl karşılanıyor? (Mevcut süreç/çözüm var mı?)",
        "fikrin_ozeti": "Fikrinizin kısa ve net adı nedir?",
        "amac": "Bu fikir hangi amaca hizmet ediyor? (Listeden birini seçebilir misiniz?)",
        "fikrin_aciklamasi": "Fikrin detaylı açıklamasını paylaşır mısınız? (Kapsamı ve beklenen sonucu dahil)",
        "cozum_tipi": "Kabaca nasıl bir çözüm yapılmasını istiyorsunuz? (Örn: yeni ekran, otomasyon, entegrasyon)",
        "kanallar": "Bu geliştirme hangi kanallarda kullanılacak? (Birden fazla seçebilirsiniz)",
        "hedef_kitle": "Bu çözümün hedef kitlesi kimler?",
        "kpi": "Bu fikir ile hangi metriklerde fark yaratmayı hedefliyorsunuz? (Yoksa 'yok' diyebilirsiniz)",
        "confirm": "Toplanan bilgileri özetleyip onayınızı alacağım. Onaylıyor musunuz? (Evet/Hayır)",
    }
    return prompts.get(step, "Devam edebilmem için biraz daha detay paylaşır mısınız?")


def _build_step_system_prompt(current_step: str, fields: Dict[str, Any]) -> str:
    step_prompt = STEP_PROMPTS.get(current_step, STEP_PROMPTS[STEP_ORDER[0]])
    fields_summary = _summarize_fields(fields)
    return f"""
Mevcut toplanan alanlar:
{fields_summary}

Şu anki adım: {current_step}
Görev: {step_prompt}

Kurallar:
- Kullanıcıya sadece 1 soru sor.
- Cevap muğlak/eksikse netleştirici soru sor.
- Kısa cevap verme; 3-4 cümleyle açıklayıcı ol, 1-2 örnek ekle.
- Kullanıcı 'vazgeçtim' vb. derse süreci kibarca kapat.

Tool Kullanımı:
- Bu adımın alanını doldurabiliyorsan, mutlaka ilgili tool'u çağır.
- Tool argümanlarında sadece ilgili alanı gönder.
- Kullanıcıya göstereceğin mesajı normal içerik (content) olarak yaz.
"""
mcp = FastMCP("flow-analyst-server")


@mcp.tool(
    name="submit_idea_form",
    description=(
        "Analiz sonucu olgunlaşan fikri form formatında submit eder. "
        "Genellikle analist sohbeti tamamlandıktan ve kullanıcı onay verdikten sonra çağrılır."
    ),
)
async def submit_idea_form(
    fikrin_ozeti: str,
    fikrin_aciklamasi: str,
    amac: str,
    problem: str,
    cozum_tipi: str,
    kanallar: List[str],
    mevcut_durum: str,
    hedef_kitle: str,
    kpi: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Groovy tarafındaki SUBMIT_IDEA_FORM_TOOL şemasının MCP karşılığı.

    İlk aşamada sadece formu alıp, normalize edilmiş şekilde geri döner.
    İleride burada Jira kaydı oluşturma / ScriptRunner endpoint çağırma gibi
    entegrasyonlar eklenebilir.
    """
    return {
        "fikrin_ozeti": fikrin_ozeti,
        "fikrin_aciklamasi": fikrin_aciklamasi,
        "amac": amac,
        "problem": problem,
        "cozum_tipi": cozum_tipi,
        "kanallar": kanallar,
        "mevcut_durum": mevcut_durum,
        "hedef_kitle": hedef_kitle,
        "kpi": kpi,
    }

def flow_analyst_step_core(
    question: str,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Step-based core iş mantığı (CLI ve MCP ortak).

    Memory-cache yaklaşımı:
    - thread_id yoksa yeni üretir ve state oluşturur.
    - thread_id varsa cache'den state yükler.
    - current_step'e göre LLM'e kısa prompt + state özeti gönderir.
    - JSON çıktı ile fields merge edilir, step ilerletilir, history güncellenir.
    """
    tid = thread_id or str(uuid.uuid4())
    state = _STATE_CACHE.get(tid) or _new_state()

    current_step = state.get("current_step") or STEP_ORDER[0]
    fields = state.get("fields") or {}
    history: List[Dict[str, str]] = state.get("history") or []

    msgs: List[Dict[str, str]] = []
    # kısa history (son 6 mesaj)
    if history:
        msgs.extend(history[-6:])
    msgs.append({"role": "user", "content": question})

    # Step-based akışta sistem promptu SADECE ilgili adım promptudur
    system_prompt = _build_step_system_prompt(current_step=current_step, fields=fields)
    tools = _tools_for_step(current_step)

    assistant_message = ""
    extracted: Dict[str, Any] = {}
    is_confirmed = False

    def run_llm_for_step(step: str) -> tuple[str, Dict[str, Any], bool]:
        sp = _build_step_system_prompt(current_step=step, fields=fields)
        t = _tools_for_step(step)

        if t:
            raw = _call_llm_tools(sp, msgs, t)
            content, tool_calls = _extract_assistant_message_and_tool_calls(raw)

            local_extracted: Dict[str, Any] = {}
            local_confirmed = False

            for tc in tool_calls:
                fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                name = fn.get("name")
                args = _safe_json_loads(fn.get("arguments"))

                if name == "set_text_field":
                    val = (args.get("value") or "").strip() if isinstance(args, dict) else ""
                    if val:
                        local_extracted[step] = val

                elif name == "set_kanallar":
                    chans = args.get("kanallar") if isinstance(args, dict) else None
                    if isinstance(chans, list):
                        local_extracted["kanallar"] = [
                            c for c in chans if isinstance(c, str) and c.strip()
                        ]

                elif name == "set_amac":
                    amac_val = args.get("amac") if isinstance(args, dict) else None
                    if isinstance(amac_val, str) and amac_val.strip():
                        local_extracted["amac"] = amac_val.strip()

                elif name == "confirm_form":
                    local_confirmed = (
                        bool(args.get("is_confirmed")) if isinstance(args, dict) else False
                    )

            # Tool call gelmediyse fallback: JSON-mode ile dene (tek sefer)
            if not local_extracted and not local_confirmed and not content:
                j = _call_llm_json(sp, msgs)
                content = (j.get("assistant_message") or "").strip()
                local_extracted = j.get("extracted") or {}
                local_confirmed = bool(j.get("is_confirmed"))

            return content, local_extracted, local_confirmed

        # Safety fallback (normalde STEP_ORDER hepsi tool'a sahip)
        j = _call_llm_json(sp, msgs)
        return (
            (j.get("assistant_message") or "").strip(),
            j.get("extracted") or {},
            bool(j.get("is_confirmed")),
        )

    # 1) Önce current_step için LLM çalıştır
    assistant_message, extracted, is_confirmed = run_llm_for_step(current_step)

    _merge_extracted(fields, extracted)

    # step ilerletme
    if is_confirmed:
        state["is_confirmed"] = True
        state["current_step"] = "done"
    else:
        # Alan dolduysa sıradaki step'e geç; dolmadıysa aynı step'te kal
        field_is_filled = False
        if current_step == "kanallar":
            field_is_filled = bool(fields.get("kanallar"))
        elif current_step == "confirm":
            field_is_filled = False
        else:
            v = fields.get(current_step)
            field_is_filled = bool(v) and (not isinstance(v, str) or bool(v.strip()))

        state["current_step"] = _next_step_name(current_step) if field_is_filled else current_step

    # Bazı modeller tool_call sonrası content boş dönebilir.
    # Bu durumda aynı turda bir sonraki step için 1 kez daha LLM çağırıp soruyu üret.
    if not assistant_message and not state.get("is_confirmed"):
        next_step_for_user = state.get("current_step") or current_step
        if next_step_for_user != "done" and next_step_for_user != current_step:
            assistant_message, extracted2, is_confirmed2 = run_llm_for_step(next_step_for_user)
            _merge_extracted(fields, extracted2)
            if is_confirmed2:
                state["is_confirmed"] = True
                state["current_step"] = "done"

    # Hâlâ boşsa fallback metin bas
    if not assistant_message:
        step_for_user = state.get("current_step") or current_step
        assistant_message = (
            "Teşekkürler. Form onaylandı."
            if step_for_user == "done"
            else _default_question_for_step(step_for_user)
        )

    # history güncelle (user+assistant)
    if question:
        history.append({"role": "user", "content": question})
    if assistant_message:
        history.append({"role": "assistant", "content": assistant_message})
    state["history"] = history[-20:]
    state["fields"] = fields

    _STATE_CACHE[tid] = state

    return {
        "answer": assistant_message,
        "thread_id": tid,
        "current_step": state.get("current_step"),
        "is_confirmed": state.get("is_confirmed", False),
        "fields": state.get("fields"),
    }


@mcp.tool(
    name="flow_analyst_step",
    description=(
        "Step-based analist akışı. Thread bazlı memory cache ile state tutar; "
        "her çağrıda sadece ilgili alanın kısa promptunu kullanır ve JSON çıktıyla state'i günceller."
    ),
)
async def flow_analyst_step(
    question: str,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    return flow_analyst_step_core(question=question, thread_id=thread_id)


if __name__ == "__main__":
    # MCP server olarak stdio üzerinden çalıştır
    mcp.run()


