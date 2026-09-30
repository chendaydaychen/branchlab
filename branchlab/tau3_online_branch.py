"""Online multi-branch tau3 prototype with a single shared LLM/tool prefix.

The prefix is executed once against a transaction-aware environment and is
cut only at an ENV -> AGENT boundary before any mutation.  Each continuation
gets an isolated airline database, an independent agent/user state rebuilt
from the shared message history, and the same immutable-prefix read cache.

This is intentionally an application-level prefix fork.  DeepSeek does not
expose provider KV-cache cloning; provider prompt-cache accounting therefore
remains separate from the read/prefix sharing reported here.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

from tau2.data_model.message import AssistantMessage, Message, UserMessage
from tau2.data_model.tasks import InitialState
from tau2.domains.airline.environment import get_environment, get_tasks
from tau2.orchestrator.orchestrator import Orchestrator, Role
from tau2.runner.build import build_agent, build_user
from tau2.runner.simulation import run_simulation

from branchlab.tau3_tx_environment import SharedReadCache, TransactionalEnvironment
from branchlab.deepseek_client import complete_with_usage
from branchlab.semantic_contracts import SemanticContract
from branchlab.semantic_contract_experiment import POLICY, prompt_for_context


ROOT = Path(__file__).resolve().parents[1]


def load_saved_contract(task_id: str) -> SemanticContract:
    path = ROOT / "results" / "semantic_contract_canary" / f"task{task_id}.json"
    if not path.is_file():
        raise SystemExit(f"saved semantic contract not found: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not record.get("schema_valid") or "contract" not in record:
        raise SystemExit(f"saved semantic contract is invalid: {path}")
    return SemanticContract.from_dict(record["contract"])


def ensure_key() -> None:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return
    secret = Path.home() / ".config" / "branchlab" / "deepseek_api_key"
    if not secret.is_file() or (secret.stat().st_mode & 0o777) != 0o600:
        raise SystemExit("DeepSeek key missing or secret-file mode is not 600")
    os.environ["DEEPSEEK_API_KEY"] = secret.read_text(encoding="utf-8").strip()


def message_costs(messages: list[Message]) -> tuple[float, float]:
    agent = sum(
        float(message.cost or 0.0)
        for message in messages
        if isinstance(message, AssistantMessage)
    )
    user = sum(
        float(message.cost or 0.0)
        for message in messages
        if isinstance(message, UserMessage)
    )
    return agent, user


def contract_context(messages: list[Message]) -> str:
    payload = []
    for message in messages:
        value = message.model_dump(mode="json")
        payload.append(
            {
                key: value[key]
                for key in ("role", "content", "tool_calls", "id", "error")
                if key in value and value[key] not in (None, [], "")
            }
        )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def generate_online_contract(
    *, task_id: str, operation: str, prefix: list[Message], model: str
) -> tuple[SemanticContract, dict[str, Any]]:
    messages = prompt_for_context(
        task_id=task_id,
        operation=operation,
        context=contract_context(prefix),
        policy=POLICY.read_text(encoding="utf-8"),
    )
    started = time.perf_counter()
    response = complete_with_usage(
        messages, model=model, temperature=0.0, max_tokens=800
    )
    elapsed = time.perf_counter() - started
    contract = SemanticContract.from_dict(json.loads(response.content))
    return contract, {
        "source": "online-generated",
        "model": response.model,
        "usage": response.usage,
        "duration_s": elapsed,
        "contract": contract.to_dict(),
    }


def build_orchestrator(
    *,
    task,
    mode: str,
    model: str,
    temperature: float,
    seed: int,
    shared_cache: SharedReadCache,
    branch_id: str = "default",
    semantic_contract: SemanticContract | None = None,
) -> tuple[Orchestrator, TransactionalEnvironment]:
    environment = TransactionalEnvironment(
        get_environment(),
        mode,
        shared_cache=shared_cache,
        branch_id=branch_id,
        semantic_contract=semantic_contract,
    )
    llm_args = {"temperature": temperature}
    agent = build_agent(
        "llm_agent", environment, llm=model, llm_args=llm_args, task=task
    )
    user = build_user(
        "user_simulator", environment, task, llm=model, llm_args=llm_args
    )
    orchestrator = Orchestrator(
        domain="airline",
        agent=agent,
        user=user,
        environment=environment,
        task=task,
        max_steps=100,
        max_errors=10,
        seed=seed,
        timeout=900,
    )
    return orchestrator, environment


def run_shared_prefix(
    *,
    task,
    mode: str,
    model: str,
    temperature: float,
    seed: int,
    target_reads: int,
    shared_cache: SharedReadCache,
    semantic_contract: SemanticContract | None = None,
) -> tuple[list[Message], dict[str, Any], float]:
    orchestrator, environment = build_orchestrator(
        task=task,
        mode=mode,
        model=model,
        temperature=temperature,
        seed=seed,
        shared_cache=shared_cache,
        branch_id="prefix",
        semantic_contract=semantic_contract,
    )
    started = time.perf_counter()
    orchestrator._run_start_time = None
    orchestrator._run_start_perf = started
    orchestrator.initialize()
    prefix: list[Message] | None = None
    probe_cost = 0.0
    probed_writes: list[dict[str, Any]] = []
    while not orchestrator.done:
        if target_reads > 0:
            at_safe_boundary = (
                orchestrator.from_role == Role.ENV
                and orchestrator.to_role == Role.AGENT
                and environment.metrics.read_calls >= target_reads
                and environment.metrics.write_calls == 0
            )
            if at_safe_boundary:
                prefix = deepcopy(orchestrator.trajectory)
                break

        # Automatic mode probes the next agent decision.  If it proposes the
        # first mutation, fork from the immediately preceding safe input
        # boundary; the write itself has not reached the environment.
        before_agent = None
        before_cost = (0.0, 0.0)
        if target_reads == 0 and orchestrator.to_role == Role.AGENT:
            before_agent = deepcopy(orchestrator.trajectory)
            before_cost = message_costs(before_agent)
        orchestrator.step()
        orchestrator._check_termination()
        if (
            target_reads == 0
            and before_agent is not None
            and orchestrator.from_role == Role.AGENT
            and orchestrator.message is not None
            and orchestrator.message.is_tool_call()
            and any(
                environment._is_write(call.name)
                for call in orchestrator.message.tool_calls
            )
        ):
            probed_writes = [
                {"operation": call.name, "arguments": call.arguments}
                for call in orchestrator.message.tool_calls
                if environment._is_write(call.name)
            ]
            prefix = before_agent
            after_cost = message_costs(orchestrator.trajectory)
            probe_cost = (after_cost[0] + after_cost[1]) - (
                before_cost[0] + before_cost[1]
            )
            break
        if environment.metrics.write_calls:
            raise RuntimeError(
                "prefix reached a mutation before the requested safe fork boundary"
            )
    if orchestrator.done:
        raise RuntimeError("simulation terminated before a safe prefix fork")
    if prefix is None:
        raise RuntimeError("no safe prefix fork was found")

    agent_cost, user_cost = message_costs(prefix)
    elapsed = time.perf_counter() - started
    metadata = {
        "messages": len(prefix),
        "tool_calls": environment.metrics.tool_calls,
        "read_calls": environment.metrics.read_calls,
        "physical_reads": environment.metrics.physical_reads,
        "agent_cost_usd": agent_cost,
        "user_cost_usd": user_cost,
        "scheduler_probe_cost_usd": probe_cost,
        "duration_s": elapsed,
        "probed_writes": probed_writes,
    }
    orchestrator.agent.stop(orchestrator.message, orchestrator.agent_state)
    orchestrator.user.stop(orchestrator.message, orchestrator.user_state)
    return prefix, metadata, elapsed


def task_with_prefix(task, prefix: list[Message]):
    branch_task = task.model_copy(deep=True)
    if branch_task.initial_state is None:
        branch_task.initial_state = InitialState(message_history=deepcopy(prefix))
    else:
        branch_task.initial_state.message_history = deepcopy(prefix)
    return branch_task


def render_report(payload: dict[str, Any]) -> str:
    prefix = payload["prefix"]
    aggregate = payload["aggregate"]
    cutpoint = (
        "自动首次写意图"
        if payload["prefix_reads_target"] == 0
        else f"固定 {payload['prefix_reads_target']} 次读"
    )
    lines = [
        "# τ³ 在线多分支执行试验",
        "",
        "本试验在线执行一次公共前缀，在首次写入前、环境结果返回 Agent 的安全边界冻结状态；随后从同一消息历史启动多个隔离数据库分支，并共享不可变前缀的只读缓存。DeepSeek 不提供 KV-cache 克隆接口，因此模型侧只利用服务商自己的 prompt cache，未计作 BranchLab 的系统级共享收益。",
        "",
        "## 配置",
        "",
        f"- 任务：τ³ airline task {payload['task_id']}",
        f"- 模型：{payload['model']}",
        f"- 事务模式：{payload['mode']}",
        f"- 分支数：{payload['branches']}",
        f"- continuation 执行：{payload['execution']}",
        f"- 语义契约来源：{payload.get('contract_source', 'none')}",
        f"- 公共前缀：{prefix['messages']} 条消息、{prefix['read_calls']} 次逻辑读、{prefix['physical_reads']} 次物理读",
        f"- 切点：{cutpoint}",
        "",
        "## 结果",
        "",
        "| 分支 | seed | reward | DB match | 时延(s) | continuation cost($) | 物理读 | 共享读命中 | 验证失败 | 契约编译/检查/拒绝 |",
        "|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    for branch in payload["branch_results"]:
        metrics = branch["transaction_metrics"]
        lines.append(
            f"| {branch['branch']} | {branch['seed']} | {branch['reward']:.3f} | "
            f"{'✓' if branch['db_match'] else '✗'} | {branch['duration_s']:.2f} | "
            f"{branch['continuation_cost_usd']:.4f} | {metrics['physical_reads']} | "
            f"{metrics['shared_read_hits']} | {metrics['validation_failures']} | "
            f"{metrics.get('contract_compilations', 0)}/{metrics.get('contract_checks', 0)}/{metrics.get('contract_rejections', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 聚合",
            "",
            f"- 成功分支：{aggregate['successful_branches']}/{payload['branches']}",
            f"- 选中分支：{aggregate['winner_branch']}",
            f"- 实际总成本（公共前缀一次 + 切点 probe + 所有 continuation）：${aggregate['actual_total_cost_usd']:.4f}",
            f"- 契约生成时延：{aggregate.get('contract_generation_wallclock_s', 0.0):.2f}s（货币成本未并入上述 LiteLLM 成本，单独报告 token）",
            f"- 实测总墙钟时间：{aggregate['total_wallclock_s']:.2f}s（公共阶段 {aggregate['prefix_wallclock_s']:.2f}s + continuation {aggregate['continuation_wallclock_s']:.2f}s）",
            f"- 独立执行估算成本：${aggregate['independent_estimated_cost_usd']:.4f}",
            f"- 公共前缀节省的物理读：{aggregate['prefix_physical_reads_saved']} 次（{aggregate['prefix_read_reduction_pct']:.1f}%）",
            f"- 全流程物理读：实际 {aggregate['actual_total_physical_reads']} 次，独立分支估算 {aggregate['independent_estimated_physical_reads']} 次，减少 {aggregate['total_physical_read_reduction_pct']:.1f}%",
            "",
            "注意：这是在线多分支可执行性与共享机制的 pilot，不是最终统计结论；论文主表仍需覆盖更多任务、多个随机种子，并加入 2PL/OCC 的相同调度器对照。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("2pl", "occ", "branchlab"), default="branchlab")
    parser.add_argument("--task-id", default="11")
    parser.add_argument("--model", default="deepseek/deepseek-flash")
    parser.add_argument("--branches", type=int, default=3)
    parser.add_argument(
        "--prefix-reads",
        type=int,
        default=0,
        help="0 automatically forks immediately before the first proposed write",
    )
    parser.add_argument("--seed", type=int, default=700)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument(
        "--execution", choices=("sequential", "parallel"), default="parallel"
    )
    parser.add_argument(
        "--saved-contract",
        action="store_true",
        help="load the task's saved LLM contract, harden it, and bind it on first write",
    )
    parser.add_argument(
        "--online-contract",
        action="store_true",
        help="make exactly one capped DeepSeek call after the first-write probe",
    )
    parser.add_argument("--contract-model", default="deepseek-chat")
    args = parser.parse_args()
    if args.branches < 1:
        raise SystemExit("--branches must be at least 1")
    if args.saved_contract and args.online_contract:
        raise SystemExit("choose only one of --saved-contract and --online-contract")
    ensure_key()

    task = next(task for task in get_tasks("base") if str(task.id) == args.task_id)
    semantic_contract = load_saved_contract(args.task_id) if args.saved_contract else None
    contract_meta: dict[str, Any] = {
        "source": "saved" if args.saved_contract else "none",
        "duration_s": 0.0,
        "usage": {},
    }
    shared_cache = SharedReadCache()
    prefix, prefix_meta, _ = run_shared_prefix(
        task=task,
        mode=args.mode,
        model=args.model,
        temperature=args.temperature,
        seed=args.seed,
        target_reads=args.prefix_reads,
        shared_cache=shared_cache,
        semantic_contract=semantic_contract,
    )
    if args.online_contract:
        probed_writes = prefix_meta.get("probed_writes") or []
        if len(probed_writes) != 1:
            raise RuntimeError(
                f"online contract canary requires exactly one probed write, got {len(probed_writes)}"
            )
        semantic_contract, contract_meta = generate_online_contract(
            task_id=args.task_id,
            operation=probed_writes[0]["operation"],
            prefix=prefix,
            model=args.contract_model,
        )
    prefix_agent_cost = prefix_meta["agent_cost_usd"]
    prefix_user_cost = prefix_meta["user_cost_usd"]
    prefix_cost = prefix_agent_cost + prefix_user_cost
    probe_cost = prefix_meta["scheduler_probe_cost_usd"]

    def run_branch(index: int) -> dict[str, Any]:
        seed = args.seed + index + 1
        branch_task = task_with_prefix(task, prefix)
        orchestrator, environment = build_orchestrator(
            task=branch_task,
            mode=args.mode,
            model=args.model,
            temperature=args.temperature,
            seed=seed,
            shared_cache=shared_cache,
            branch_id=f"task-{args.task_id}/candidate-{index + 1}",
            semantic_contract=semantic_contract,
        )
        simulation = run_simulation(orchestrator)
        total_cost = float(simulation.agent_cost or 0.0) + float(simulation.user_cost or 0.0)
        return {
            "branch": index + 1,
            "seed": seed,
            "reward": float(simulation.reward_info.reward or 0.0),
            "db_match": bool(simulation.reward_info.db_check.db_match),
            "duration_s": float(simulation.duration or 0.0),
            "total_cost_with_copied_prefix_usd": total_cost,
            "continuation_cost_usd": max(0.0, total_cost - prefix_cost),
            "termination_reason": str(simulation.termination_reason),
            "transaction_metrics": environment.metrics_dict(),
            "simulation": simulation.model_dump(mode="json"),
        }

    continuation_started = time.perf_counter()
    if args.execution == "parallel":
        with ThreadPoolExecutor(max_workers=args.branches) as executor:
            futures = [executor.submit(run_branch, index) for index in range(args.branches)]
            results = [future.result() for future in as_completed(futures)]
        results.sort(key=lambda item: item["branch"])
    else:
        results = [run_branch(index) for index in range(args.branches)]
    continuation_wallclock = time.perf_counter() - continuation_started

    winner = max(
        results,
        key=lambda item: (item["reward"], item["db_match"], -item["duration_s"]),
    )
    actual_cost = (
        prefix_cost
        + probe_cost
        + sum(item["continuation_cost_usd"] for item in results)
    )
    independent_cost = sum(item["total_cost_with_copied_prefix_usd"] for item in results)
    naive_prefix_reads = prefix_meta["physical_reads"] * args.branches
    actual_prefix_reads = prefix_meta["physical_reads"]
    saved_reads = naive_prefix_reads - actual_prefix_reads
    continuation_logical_reads = sum(
        item["transaction_metrics"]["read_calls"] for item in results
    )
    continuation_physical_reads = sum(
        item["transaction_metrics"]["physical_reads"] for item in results
    )
    actual_total_physical_reads = actual_prefix_reads + continuation_physical_reads
    independent_total_physical_reads = naive_prefix_reads + continuation_logical_reads
    payload = {
        "task_id": args.task_id,
        "model": args.model,
        "mode": args.mode,
        "branches": args.branches,
        "temperature": args.temperature,
        "base_seed": args.seed,
        "prefix_reads_target": args.prefix_reads,
        "execution": args.execution,
        "saved_contract": args.saved_contract,
        "online_contract": args.online_contract,
        "contract_source": contract_meta["source"],
        "contract_generation": contract_meta,
        "prefix": prefix_meta,
        "branch_results": results,
        "aggregate": {
            "successful_branches": sum(item["reward"] == 1.0 for item in results),
            "winner_branch": winner["branch"],
            "actual_total_cost_usd": actual_cost,
            "independent_estimated_cost_usd": independent_cost,
            "cost_saved_usd": independent_cost - actual_cost,
            "prefix_physical_reads_saved": saved_reads,
            "prefix_read_reduction_pct": 100.0 * saved_reads / naive_prefix_reads
            if naive_prefix_reads
            else 0.0,
            "actual_total_physical_reads": actual_total_physical_reads,
            "independent_estimated_physical_reads": independent_total_physical_reads,
            "total_physical_read_reduction_pct": 100.0
            * (independent_total_physical_reads - actual_total_physical_reads)
            / independent_total_physical_reads
            if independent_total_physical_reads
            else 0.0,
            "prefix_wallclock_s": prefix_meta["duration_s"],
            "contract_generation_wallclock_s": contract_meta.get("duration_s", 0.0),
            "continuation_wallclock_s": continuation_wallclock,
            "total_wallclock_s": prefix_meta["duration_s"]
            + contract_meta.get("duration_s", 0.0)
            + continuation_wallclock,
        },
    }
    contract_suffix = "_contract_online" if args.online_contract else ("_contract_saved" if args.saved_contract else "")
    stem = f"tau3_online_branch_{args.mode}_task{args.task_id}_b{args.branches}_s{args.seed}{contract_suffix}"
    json_path = ROOT / "results" / f"{stem}.json"
    md_path = ROOT / "results" / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({**payload, "branch_results": [
        {key: value for key, value in item.items() if key != "simulation"}
        for item in results
    ]}, indent=2, ensure_ascii=False))
    print(f"json: {json_path}")
    print(f"report: {md_path}")


if __name__ == "__main__":
    main()
