"""
LangGraph-based orchestration flow definitions.

Extension points:
- Add additional nodes or branches for new workflows.
- Add persistence for state between requests.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from app.functions.registry import FunctionRegistry
from app.llm_provider.factory import LLMFactory
from app.llm_provider.models import LLMProviderConfig
from app.orchestration.prompts import ANALYST_SYSTEM_PROMPT, SIZING_SYSTEM_PROMPT, render_prompt


class FlowState(TypedDict, total=False):
    """
    Shared state for the LangGraph flow.

    Extension points:
    - Add tenant metadata or request IDs.
    - Add persistence hooks for audit logging.
    """

    messages: list[BaseMessage]
    idea_form: dict[str, Any] | None
    form_submitted: bool
    complexity: str | None
    analysis_note: str | None
    final_answer: str | None
    last_tool_calls: list[dict[str, Any]]


def build_initial_state(payload: Any) -> FlowState:
    """
    Build the initial LangGraph state from the request payload.

    Extension points:
    - Support additional input fields or metadata.
    """

    messages: list[BaseMessage] = []
    question = ""
    chat_history: list[dict[str, Any]] = []

    if isinstance(payload, dict):
        question = payload.get("question", "") or ""
        chat_history = payload.get("chat_history", []) or []
    else:
        question = str(payload)

    for item in chat_history:
        if not isinstance(item, dict):
            continue
        inputs = item.get("inputs", {})
        outputs = item.get("outputs", {})
        if inputs.get("question"):
            messages.append(HumanMessage(content=str(inputs.get("question"))))
        if outputs.get("llm_output"):
            messages.append(AIMessage(content=str(outputs.get("llm_output"))))

    if question:
        messages.append(HumanMessage(content=question))

    return {
        "messages": messages,
        "idea_form": None,
        "form_submitted": False,
        "complexity": None,
        "analysis_note": None,
        "final_answer": None,
        "last_tool_calls": [],
    }


def build_flow_graph(
    llm_factory: LLMFactory,
    function_registry: FunctionRegistry,
    config: LLMProviderConfig,
):
    """
    Build and compile the LangGraph orchestration flow.

    Extension points:
    - Add additional nodes for RAG or script execution.
    - Swap prompts or models for specific tenants.
    """

    tools = function_registry.as_langchain_tools()
    analyst_llm = llm_factory.build_chat_model(config).bind_tools(tools)
    sizing_llm = llm_factory.build_chat_model(config).bind_tools(tools)

    def analyst_node(state: FlowState) -> FlowState:
        system_prompt = render_prompt(
            ANALYST_SYSTEM_PROMPT,
            {"question": "", "chat_history": []},
        )
        messages = [SystemMessage(content=system_prompt)] + state.get("messages", [])
        response = analyst_llm.invoke(messages)
        tool_calls = _normalize_tool_calls(response)
        return {
            "messages": state.get("messages", []) + [response],
            "last_tool_calls": tool_calls,
        }

    def submit_tool_node(state: FlowState) -> FlowState:
        tool_calls = state.get("last_tool_calls", [])
        idea_form = _extract_tool_args(tool_calls, "submit_idea_form")
        tool_messages: list[BaseMessage] = []
        idea_payload = idea_form if isinstance(idea_form, dict) else None
        if idea_payload is not None:
            result = _execute_tool(function_registry, "submit_idea_form", idea_payload)
            tool_messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=_extract_tool_id(tool_calls, "submit_idea_form"),
                )
            )
        return {
            "idea_form": idea_payload,
            "form_submitted": idea_payload is not None,
            "messages": state.get("messages", []) + tool_messages,
        }

    def sizing_node(state: FlowState) -> FlowState:
        idea = state.get("idea_form") or {}
        system_prompt = render_prompt(SIZING_SYSTEM_PROMPT, {"idea": json.dumps(idea, ensure_ascii=False, indent=2)})
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Talep Bilgileri:\n{json.dumps(idea, ensure_ascii=False, indent=2)}"),
        ]
        response = sizing_llm.invoke(messages)
        tool_calls = _normalize_tool_calls(response)
        return {
            "messages": state.get("messages", []) + [response],
            "last_tool_calls": tool_calls,
        }

    def score_tool_node(state: FlowState) -> FlowState:
        tool_calls = state.get("last_tool_calls", [])
        score_args = _extract_tool_args(tool_calls, "score_complexity") or {}
        tool_messages: list[BaseMessage] = []
        if isinstance(score_args, dict) and score_args:
            result = _execute_tool(function_registry, "score_complexity", score_args)
            tool_messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=_extract_tool_id(tool_calls, "score_complexity"),
                )
            )
        return {
            "complexity": _safe_get(score_args, "T_Shirt_Size"),
            "analysis_note": _safe_get(score_args, "Analiz_Notu"),
            "messages": state.get("messages", []) + tool_messages,
        }

    def finalize_node(state: FlowState) -> FlowState:
        if state.get("complexity"):
            tshirt_size = state.get("complexity") or "Belirsiz"
            analysis_note = state.get("analysis_note") or "Analiz notu bulunamadı."
            final_answer = (
                "Fikriniz başarılı ile oluşturulmuştur.\n"
                f"Tahmini kompleksite değeri {tshirt_size} olarak belirlenmiştir.\n"
                f"Analiz Notu : {analysis_note}\n"
                "Sürecinizin devam etmesi için, 'Fikirlerim' sekmesi altından, "
                "oluşturduğunuz fikrin olgunlaştırmasını sağlamasınız."
            )
        else:
            final_answer = _last_ai_message_content(state.get("messages", [])) or ""
        return {"final_answer": final_answer}

    def route_after_analyst(state: FlowState) -> str:
        if _has_tool_call(state, "submit_idea_form"):
            return "submit_tool_node"
        return "finalize"

    def route_after_sizing(state: FlowState) -> str:
        if _has_tool_call(state, "score_complexity"):
            return "score_tool_node"
        return "finalize"

    graph = StateGraph(FlowState)
    graph.add_node("analyst_llm", analyst_node)
    graph.add_node("submit_tool_node", submit_tool_node)
    graph.add_node("sizing_llm", sizing_node)
    graph.add_node("score_tool_node", score_tool_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("analyst_llm")
    graph.add_conditional_edges(
        "analyst_llm",
        route_after_analyst,
        {"submit_tool_node": "submit_tool_node", "finalize": "finalize"},
    )
    graph.add_edge("submit_tool_node", "sizing_llm")
    graph.add_conditional_edges(
        "sizing_llm",
        route_after_sizing,
        {"score_tool_node": "score_tool_node", "finalize": "finalize"},
    )
    graph.add_edge("score_tool_node", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def _normalize_tool_calls(message: BaseMessage) -> list[dict[str, Any]]:
    """
    Normalize tool calls from a LangChain AIMessage.

    Extension points:
    - Add validation for supported tool call formats.
    """

    if not isinstance(message, AIMessage):
        return []

    raw_calls = message.tool_calls or []
    normalized: list[dict[str, Any]] = []
    for call in raw_calls:
        if isinstance(call, dict):
            name = call.get("name") or call.get("function", {}).get("name")
            args = call.get("args") or call.get("function", {}).get("arguments")
            call_id = call.get("id") or call.get("tool_call_id")
        else:
            name = getattr(call, "name", None)
            args = getattr(call, "args", None)
            call_id = getattr(call, "id", None)

        normalized.append(
            {
                "name": name,
                "args": _normalize_tool_args(args),
                "id": call_id,
            }
        )
    return normalized


def _normalize_tool_args(args: Any) -> Any:
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return args


def _has_tool_call(state: FlowState, name: str) -> bool:
    return any(call.get("name") == name for call in state.get("last_tool_calls", []))


def _extract_tool_args(tool_calls: list[dict[str, Any]], name: str) -> Any:
    for call in tool_calls:
        if call.get("name") == name:
            return call.get("args")
    return None


def _extract_tool_id(tool_calls: list[dict[str, Any]], name: str) -> str:
    for call in tool_calls:
        if call.get("name") == name:
            return str(call.get("id") or name)
    return name


def _execute_tool(registry: FunctionRegistry, name: str, args: Any) -> Any:
    function = registry.get(name)
    if isinstance(args, dict):
        return function(**args)
    return function(args)


def _safe_get(data: Any, key: str) -> Any:
    if isinstance(data, dict):
        return data.get(key)
    return None


def _last_ai_message_content(messages: list[BaseMessage]) -> str | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return str(message.content)
    return None
