"""Supervisor Agent — LLM-driven dynamic orchestration.

The Supervisor observes global state and reasons about which agent to call next.
LLM-driven with rule-based fallback.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState
from openlearning.log import get_logger

logger = get_logger("Supervisor")


# ── Supervisor Node ──────────────────────────────────────────

async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor node: observe state, decide next agent via LLM.

    Reads: current_agent, status, evaluation, reflection, iteration,
           collected_count, avg_quality_score, user_memory
    Writes: current_agent, supervisor_log
    """
    decision = await _llm_decide(state)

    # Append to decision log
    log = state.get("supervisor_log", [])
    import time
    log.append({
        "from": state.get("current_agent", "start"),
        "to": decision["next_agent"],
        "reason": decision["reason"],
        "ts": time.time(),
    })

    return {
        "current_agent": "supervisor",
        "supervisor_log": log,
        # Store decision for graph routing
        "_next_agent": decision["next_agent"],
    }


def supervisor_route(state: AgentState) -> str:
    """Read the supervisor's decision and return the next agent name.

    Called by graph conditional edges.
    """
    next_agent = state.get("_next_agent", "")
    if next_agent and next_agent in ("memory", "planner", "collector", "analyzer", "evaluator", "reflector", "builder", "end"):
        return next_agent

    # Fallback to rule-based
    return _rule_based_decide(state)


# ── LLM Decision ─────────────────────────────────────────────

async def _llm_decide(state: AgentState) -> dict[str, str]:
    """Use LLM to decide the next agent.

    Returns {"next_agent": "...", "reason": "..."}
    """
    try:
        from openlearning.llm import achat_json

        # Build concise state summary for the LLM
        current = state.get("current_agent", "start")
        status = state.get("status", "")
        iteration = state.get("iteration", 0)
        max_iter = state.get("max_iterations", 3)
        evaluation = state.get("evaluation", {})
        reflection = state.get("reflection", {})
        collected = state.get("collected_count", 0)
        avg_score = state.get("avg_quality_score", 0)
        user_memory = state.get("user_memory", {})
        mastery = user_memory.get("mastery", {})
        mastered_count = len(mastery.get("mastered", []))

        eval_pass = evaluation.get("pass", None)
        quality_pass = evaluation.get("quality", {}).get("pass", None)
        coverage_pass = evaluation.get("coverage", {}).get("pass", None)

        prompt = f"""你是 OpenLearning 的 Supervisor，负责决定下一步执行哪个 Agent。

当前状态：
- 刚刚执行完: {current}
- 迭代轮次: {iteration}/{max_iter}
- 已采集资源: {collected} 条
- 平均质量: {avg_score:.1f}/10
- 评估通过: {eval_pass}
  - 质量: {quality_pass}
  - 覆盖: {coverage_pass}
- 已掌握概念: {mastered_count} 个
- 系统状态: {status}

可用 Agent 及职责：
- memory: 查询用户记忆、偏好、已掌握概念
- planner: 分析需求、生成知识图谱和搜索词
- collector: 执行搜索、采集资源
- analyzer: 内容分析、知识提取
- evaluator: 规则引擎质量/覆盖/多样性检查
- reflector: 反思策略、决定是否需要补充
- builder: 生成学习系统站点
- end: 结束流程

请决定下一步执行哪个 Agent，以 JSON 格式输出：
{{"next_agent": "agent名", "reason": "决策理由"}}

决策原则：
1. 如果 status=done，选 end
2. 首次执行（current=start），选 memory
3. memory 完成后选 planner
4. 评估通过后选 builder
5. 评估未通过且还有迭代余量，选 reflector 再到 planner
6. 达到最大迭代次数，选 builder 强制生成"""

        result = await achat_json(
            messages=[{"role": "user", "content": prompt}],
            tier="standard",
            temperature=0.1,
        )

        next_agent = result.get("next_agent", "")
        reason = result.get("reason", "")

        # Validate agent name
        valid_agents = {"memory", "planner", "collector", "analyzer", "evaluator", "reflector", "builder", "end"}
        if next_agent in valid_agents:
            logger.info("LLM 决策: %s — %s", next_agent, reason)
            return {"next_agent": next_agent, "reason": reason}

    except Exception as e:
        logger.error("LLM 决策失败: %s, 回退规则路由", e)

    # Fallback to rule-based
    return {"next_agent": _rule_based_decide(state), "reason": "rule-based fallback"}


# ── Rule-Based Fallback ──────────────────────────────────────

def _rule_based_decide(state: AgentState) -> str:
    """Rule-based routing fallback."""
    current = state.get("current_agent", "")
    status = state.get("status", "")

    if status == "done":
        return "end"

    # First call or after supervisor
    if not current or current == "supervisor":
        # Check where we are in the pipeline
        if state.get("analyzed_resources"):
            # Already have analyzed resources, check evaluation
            evaluation = state.get("evaluation", {})
            if evaluation.get("pass", False):
                return "builder"
            if state.get("iteration", 0) >= state.get("max_iterations", 3):
                return "builder"
            return "reflector"
        if state.get("raw_resources"):
            return "analyzer"
        if state.get("search_queries"):
            return "collector"
        if state.get("knowledge_graph", {}).get("nodes"):
            return "collector"
        return "memory"

    # Standard routing
    routing = {
        "memory": "planner",
        "planner": "collector",
        "collector": "analyzer",
        "analyzer": "evaluator",
        "evaluator": _evaluator_route,
        "reflector": _reflector_route,
        "builder": "end",
    }

    handler = routing.get(current)
    if handler is None:
        return "end"
    if callable(handler):
        return handler(state)
    return handler


def _evaluator_route(state: AgentState) -> str:
    """Route after evaluation."""
    evaluation = state.get("evaluation", {})
    if evaluation.get("pass", False):
        return "builder"
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "builder"
    return "reflector"


def _reflector_route(state: AgentState) -> str:
    """Route after reflection."""
    reflection = state.get("reflection", {})
    if reflection.get("should_continue", False):
        return "planner"
    return "builder"
