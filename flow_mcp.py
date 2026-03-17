#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
fastmcp tabanlı tek dosya:
- LLM çağrısı + iş mantığı
- MCP server + tool tanımı
"""

from __future__ import annotations

import os
from typing import List, Dict, Any, Optional

import requests
from fastmcp import FastMCP


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")


ANALYST_SYSTEM_PROMPT = """
Kullanıcılardan fikir, ihtiyaç ve gereksinimleri sistematik, analitik ve yönlendirici bir yaklaşımla toplayan bir analist asistansın.

Bir analist gibi davranırsın:
- Kullanıcının verdiği cevapları yüzeysel olarak kabul etmezsin.
- Gerektiğinde derinleştirir, açıklama ister, örneklerle yönlendirirsin.
- Kullanıcının cevabı muğlak, eksik, genel veya belirsizse bunu nazikçe belirtir ve detay isteyerek netleştirirsin.
- Asıl hedefin: Kullanıcıyı yormadan ama derinleştirerek, yüksek kaliteli bir fikir formu oluşturmaktır.

GENEL DAVRANIŞ KURALLARI:
- Her adımda yalnızca bir soru sor.
- Empatik, sade ve açıklayıcı bir üslup kullan.
- Cevabı sadece almakla yetinme; analiz et, gerekirse netlik sor.
- Her sorudan sonra kısa bir örnek ver; mümkünse en az 2 farklı senaryo örneği sun.
- Cevapta başka alanlara ait bilgiler varsa bunları otomatik olarak ilgili alana yerleştir ve o soruyu tekrar sorma.
- Kullanıcı cevaplarını düzenli, profesyonel ve anlaşılır cümlelere dönüştür.
- Kullanıcıdan gelen her cevaba karşılık en az 3-4 cümlelik açıklayıcı bir yanıt üret; tek satırlık cevaplar verme.
- Kullanıcı "fikrim yok", "vazgeçtim" vb. gibi süreci durdurursa süreci kibarca bitir ve function_call üretme.
- Süreç boyunca kullanıcıya cevap verirken JSON veya function_call kullanma; sadece doğal metinle konuş.
"""


def _call_llm(system_prompt: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Verilen system_prompt + messages listesini alıp
    LLM_BASE_URL altındaki OpenAI-compatible /chat/completions
    endpoint'ine istek atar ve JSON cevabı döner.
    """
    openai_messages: List[Dict[str, str]] = []
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})
    openai_messages.extend(messages)

    body = {
        "model": LLM_MODEL,
        "max_tokens": 4096,
        "temperature": 0,
        "messages": openai_messages,
    }

    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    resp = requests.post(url, headers=headers, json=body, timeout=90)
    resp.raise_for_status()
    return resp.json()


def _extract_text(llm_response: Dict[str, Any]) -> str:
    """
    LLM cevabından choices[0].message.content alanını çıkarıp
    sade metin olarak döner. choices yoksa boş string döner.
    """
    choices = llm_response.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message", {}).get("content") or "").strip()


def _build_messages(
    question: str,
    chat_history: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, str]]:
    """
    flow.groovy ile uyumlu olacak şekilde:
    - chat_history içindeki önceki soru/cevapları
      user/assistant mesajlarına çevirir,
    - en sona güncel question'ı user mesajı olarak ekler.
    LLM'e gönderilecek messages dizisini üretir.
    """
    msgs: List[Dict[str, str]] = []

    for item in chat_history or []:
        if not isinstance(item, dict):
            continue
        prev_q = (item.get("inputs", {}).get("question") or "").strip()
        raw_out = item.get("outputs", {}).get("llm_output")
        if isinstance(raw_out, dict):
            prev_a = (raw_out.get("content") or "").strip()
        else:
            prev_a = (raw_out or "").strip()

        if prev_q:
            msgs.append({"role": "user", "content": prev_q})
        if prev_a:
            msgs.append({"role": "assistant", "content": prev_a})

    if question:
        msgs.append({"role": "user", "content": question})

    return msgs


def flow_analyst_core(
    question: str,
    thread_id: Optional[str] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    İş mantığı:
    - chat_history + question'dan messages dizisini kurar,
    - LLM'i ANALYST_SYSTEM_PROMPT ile çağırır,
    - cevap metnini çıkarır ve
      {"answer": ..., "thread_id": ...} sözlüğü döner.
    """
    msgs = _build_messages(question, chat_history or [])
    llm_resp = _call_llm(ANALYST_SYSTEM_PROMPT, msgs)
    answer = _extract_text(llm_resp)
    return {
        "answer": answer,
        "thread_id": thread_id,
    }


mcp = FastMCP("flow-analyst-server")


@mcp.tool(name="flow_analyst", description="Analist asistanı ile fikir toplama akışını çalıştırır.")
async def flow_analyst(
    question: str,
    thread_id: Optional[str] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    fastmcp tool wrapper: flow_analyst.

    MCP istemcileri bu tool'u çağırdığında:
    - Parametreleri alır,
    - flow_analyst_core'u çalıştırır,
    - Sonucu doğrudan tool çıktısı olarak döner.
    """
    return flow_analyst_core(
        question=question,
        thread_id=thread_id,
        chat_history=chat_history or [],
    )


if __name__ == "__main__":
    # MCP server olarak stdio üzerinden çalıştır
    mcp.run()


