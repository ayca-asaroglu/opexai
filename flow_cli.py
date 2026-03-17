#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
flow_cli.py

flow_mcp.py içindeki iş mantığını kullanarak
terminal üzerinden analist asistan ile sohbet etmeni sağlar.
"""

from typing import List, Dict, Any

from flow_mcp import flow_analyst_core


def main() -> None:
    print("Analist Asistan (flow_mcp) - Çıkmak için 'quit' yaz.\n")

    history: List[Dict[str, Any]] = []
    thread_id = "terminal-thread-1"

    while True:
        try:
            q = input("Sen : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nÇıkılıyor...")
            break

        if not q:
            continue
        if q.lower() in ("quit", "exit", "q"):
            print("Görüşmek üzere.")
            break

        try:
            result = flow_analyst_core(
                question=q,
                thread_id=thread_id,
                chat_history=history,
            )
        except Exception as e:
            print(f"Asistan : (Hata) {e}\n")
            continue

        answer = (result or {}).get("answer") or ""
        print(f"Asistan: {answer}\n")

        # History'yi flow.groovy ile uyumlu formatta güncelle
        history.append({
            "inputs": {"question": q},
            "outputs": {"llm_output": answer},
        })


if __name__ == "__main__":
    main()

