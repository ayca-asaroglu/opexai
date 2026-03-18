#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
flow_cli.py

flow_mcp.py içindeki iş mantığını kullanarak
terminal üzerinden analist asistan ile sohbet etmeni sağlar.
"""

from flow_mcp import flow_analyst_step_core


def main() -> None:
    print("Analist Asistan (flow_mcp) - Çıkmak için 'quit' yaz.\n")

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
            result = flow_analyst_step_core(question=q, thread_id=thread_id)
        except Exception as e:
            print(f"Asistan : (Hata) {e}\n")
            continue

        answer = (result or {}).get("answer") or ""
        print(f"Asistan: {answer}\n")


if __name__ == "__main__":
    main()

