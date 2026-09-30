# Introduction（中文初稿）

> 文献检索截至 2026 年 9 月。文中的 2026 年工作目前均为 arXiv 预印本，投稿时应再次核对其版本与发表状态。

大语言模型驱动的数据智能体正在将自然语言请求转化为跨越推理、检索和工具调用的长程任务。例如，智能体可以读取用户与订单信息，查询多个航班，比较改签方案，并最终调用数据库接口完成退款、换票或支付。ReAct 等工作使模型能够交替进行推理与行动 [1]；Tree of Thoughts 和 Language Agent Tree Search（LATS）进一步允许模型生成、评估并回溯多条候选路径 [2,3]。这使一种新的系统负载逐渐出现：智能体不再只执行一条预先编写的事务程序，而是在运行时读取外部状态、产生若干推测分支，并根据中间结果选择其中一条对真实世界生效。我们将这类负载称为**多分支 Agent 推测事务**。

这类负载的关键问题在于，智能体所依赖的环境并非静态上下文，而是会被其他用户、服务和智能体并发修改的共享状态。以航空改签为例，智能体可能先读取订单、乘客、航班和价格信息，再并行探索“保留原行程”“改签到较早航班”和“改签到更便宜航班”三种方案。三个候选通常具有相同的对话历史和查询前缀，却会在后续产生不同的工具调用与写操作。在探索期间，目标航班的余票、价格或订单状态又可能发生变化。如果三个候选从头独立执行，系统会重复支付相同的模型推理和数据库读取开销；如果它们直接共享可变状态，一个失败或被放弃的分支又可能污染其他分支；如果提交时只要任一读值变化就整体回滚，则与任务无关的变化也会造成昂贵的重新推理。因而，这里的事务正确性不再仅取决于数据库记录是否变化，还取决于**哪个分支观察了什么、哪些计算可以复用，以及变化后的状态是否仍满足用户任务的语义**。

数据库事务为并发执行提供了成熟基础。两阶段锁（2PL）通过在事务期间持有锁来阻止冲突访问；乐观并发控制（OCC）则允许事务先执行，并在提交阶段验证其读写依赖 [10]。然而，二者隐含的执行单元仍是一条确定的读写序列。对于持续时间长、工具调用间隔不规则且访问集合在线生成的 Agent 工作流，长时间持锁会放大阻塞，而按物理读集进行严格验证又会将“数据发生变化”等同于“任务已经失效”。ATCC 已观察到 Agentic Transaction 的长时延、非确定访问模式和昂贵回滚等特征，并在运行期自适应选择乐观或悲观执行 [8]；面向可撤销 LLM 事务的工作则借助应用不变量协调长生命周期操作 [9]。这些方法改进了传统事务的执行策略，但它们主要决定一条 Agent 事务何时加锁、验证或撤销，尚未把同一任务内部的多个推测分支及其共享计算纳入事务模型。

与此同时，Agent 系统领域正在从不同角度建立事务边界。Cordon 将工具意图、结果血缘、影子状态、外部副作用和审计元数据绑定到任务级语义事务中，以支持提交、回滚与恢复 [6]；Agentic Transaction 工作重新解释了 Agent 场景下的 ACID，并提出语义依赖感知隔离等机制 [7]。这些工作证明了“Agent 需要事务”这一方向的重要性，但重点分别是不可逆外部效果的封装和一般性的语义 ACID 保证。另一方面，SGLang 的 RadixAttention 和 Preble 能在模型服务层复用提示词前缀或 KV cache [4,5]，却无法判断一次数据库查询结果在何种快照上仍然有效，也不管理分支私有写入。ToT 和 LATS 管理推理树，却不提供数据库隔离与提交语义 [2,3]。因此，现有研究仍留下一个具体而重要的空白：**如何在统一的事务抽象中同时管理数据状态、分支状态与任务语义，并以此支撑两种关键能力：安全地复用分支间计算，以及依据可验证的任务语义而非物理版本变化实施并发控制。**

解决这一问题面临两组相互关联的挑战。第一，**如何通过统一状态管理实现安全的跨分支计算共享**。分支生命周期与数据库生命周期并不一致：候选在共享前缀之后动态分叉，只有一个分支最终提交。系统既要统一追踪数据版本、分支血缘、消息历史、工具观察和任务约束，又要隔离各分支的暂存写入，保证被放弃分支没有外部可见效果。与此同时，相同调用并不天然意味着结果可复用；工具读取只有在参数、权限、底层快照和副作用属性均兼容时才能共享，否则一次陈旧观察会被传播到所有候选。

第二，**如何把开放式任务语义转化为确定、可验证的并发控制条件**。自然语言任务包含用户授权、业务前置条件和数值容忍范围，但传统并发控制只观察记录版本和读写冲突。例如，目标机票价格下降仍满足用户确认的最高支付金额，而价格上涨、订单被取消或所有者变化则会破坏原有授权。严格 OCC 无法区分这两类变化，简单忽略版本变化又可能错误接受有害状态。直接让 LLM 在提交时判断是否安全同样不可取，因为提交决策需要确定性、可复现和可审计。系统需要利用 LLM 理解任务，将开放式语义编译为结构化契约，再由可信的确定性验证器在提交阶段检查最小语义依赖、硬谓词和允许变化区间。

本文提出 **BranchLab**，一个面向多分支 Agent 推测执行的事务运行时。BranchLab 的核心观点是：**传统数据库事务主要管理数据状态，而 Agent 推测事务必须联合管理数据状态、分支状态与任务语义。** 为此，我们将一次任务建模为三元状态 $T=\langle D,B,S\rangle$：$D$ 表示带版本的数据观察与暂存写集，$B$ 表示分支树、分支私有上下文及其生命周期，$S$ 表示用户授权、业务前置条件和可接受变化范围。在这一抽象上，BranchLab 围绕计算共享和语义并发控制提供两组相互配合的机制。

第一，BranchLab 通过**统一状态管理实现跨分支计算共享**。系统将数据版本、分支血缘和任务上下文关联起来，构造写入隔离的推测分支树：公共阶段只执行一次，并在首次写意图之前自动分叉；公共消息与只读观察可以继承，而后续消息、读写集和暂存更新进入分支私有命名空间。共享项由规范化工具名与参数、初始数据库快照标识和访问属性共同索引，只有可证明为只读且快照兼容的工具结果才能跨分支复用。由此，BranchLab 把“共享前缀”从模型侧 KV 优化扩展为覆盖模型上下文、工具执行和数据观察的事务级计算共享。

第二，BranchLab 通过**LLM 编译、确定性执行的语义契约实施并发控制**。在事务执行前或语义信息形成时，LLM 将用户请求、业务策略和目标写操作转换为结构化契约；契约显式声明操作对象、用户授权、最小语义依赖、必须保持的硬谓词以及允许变化的数值区间。提交阶段不再调用 LLM 进行自由判断，而由确定性验证器在最新状态上解释该契约：无害变化可以安全重基，有害变化则拒绝提交。数值额度的并发放宽与 Escrow 对长事务中聚合量的预留思想有关 [13]，而“仅在不变量需要时协调”也与 I-confluence 一脉相承 [11]；不同之处在于，BranchLab 利用 LLM 从运行时任务中生成契约，而验证与提交仍由可复现的事务机制完成。

我们在公开工具型 Agent 基准 $\tau$-bench/其后续 $\tau^3$ Airline 环境 [12] 上实现并评估 BranchLab，并以 2PL 和严格 OCC 作为基线。对 26 个含写任务、每个任务 3 次执行得到的 78 条真实 DeepSeek 轨迹进行分析后，我们发现 772 次工具调用中有 337 次（43.7%）可由公共前缀共享消除；642 次只读调用中有 391 次（60.9%）是精确重复读。在包含写操作的 71 条轨迹上进行同轨迹配对扰动时，BranchLab 接受了全部 71 个语义无害变化、拒绝了全部 71 个有害变化，在该测试集中未出现错误接受或错误拒绝；其物理读取数相对 2PL 从 642 降至 252，减少 60.7%。在一个真实在线三候选 pilot 中，三种系统均保持 3/3 任务成功与数据库状态匹配；BranchLab 相对独立 2PL 将墙钟时间降低 30.1%、模型成本降低 62.6%、物理读取降低 68.4%。该在线结果用于验证机制能够转化为端到端收益，而非声称跨任务总体显著性；更大规模、多任务与多随机种子的在线评估仍是完整论文需要补充的部分。

本文的贡献如下：

1. 我们刻画了多分支 Agent 推测事务这一新型负载，并提出联合数据状态、分支状态和任务语义的事务抽象；在此基础上设计快照安全的公共前缀执行和分支私有状态机制，以减少模型推理、工具调用与数据读取中的重复计算。
2. 我们提出由 LLM 生成、由确定性验证器执行的语义契约机制，将自然语言中的用户授权、业务前置条件、最小语义依赖和允许变化区间转化为可审计的提交条件，从而区分物理冲突与任务冲突并实施语义并发控制。
3. 我们基于公开 Agent 工作负载和真实模型轨迹，与 2PL、严格 OCC 进行配对比较，初步结果表明 BranchLab 能同时减少重复计算与 OCC 假冲突，并保持对所测有害变化的拒绝能力。

## 参考文献

[1] Shunyu Yao, et al. [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629). ICLR, 2023.

[2] Shunyu Yao, et al. [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601). NeurIPS, 2023.

[3] Andy Zhou, et al. [Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models](https://arxiv.org/abs/2310.04406). ICML, 2024.

[4] Lianmin Zheng, et al. [SGLang: Efficient Execution of Structured Language Model Programs](https://arxiv.org/abs/2312.07104). NeurIPS, 2024.

[5] Eliot Sheng, et al. [Preble: Efficient Distributed Prompt Scheduling for LLM Serving](https://arxiv.org/abs/2407.00023). 2024.

[6] Zheng Chen, et al. [Cordon: Semantic Transactions for Tool-Using LLM Agents](https://arxiv.org/abs/2606.17573). arXiv preprint, 2026.

[7] Zhaoyan Sun, Xiaoxiao Wang, and Guoliang Li. [Agentic Transaction: Towards ACID-Compliant Agent Systems](https://arxiv.org/abs/2608.13900). arXiv preprint, 2026.

[8] Weixing Zhou, et al. [ATCC: Adaptive Concurrency Control for Unforeseen Agentic Transactions](https://arxiv.org/abs/2603.13906). arXiv preprint, 2026.

[9] Jinghan Zeng, Eugene Wu, and Sanjay Krishnan. [A Simple and Fast Way to Handle Semantic Errors in Transactions](https://arxiv.org/abs/2412.12493). arXiv preprint, 2024.

[10] H. T. Kung and John T. Robinson. [On Optimistic Methods for Concurrency Control](https://www.eecs.harvard.edu/~htk/publication/1981-tods-kung-robinson.pdf). ACM Transactions on Database Systems, 6(2):213–226, 1981.

[11] Peter Bailis, et al. [Coordination Avoidance in Database Systems](https://www.vldb.org/pvldb/vol8/p185-bailis.pdf). PVLDB, 8(3):185–196, 2014.

[12] Shunyu Yao, Noah Shinn, Pedram Razavi, and Karthik Narasimhan. [$\tau$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://arxiv.org/abs/2406.12045). ICLR, 2025.

[13] Patrick E. O'Neil. [The Escrow Transactional Method](https://ics.uci.edu/~cs223/papers/p405-o_neil.pdf). ACM Transactions on Database Systems, 11(4):405–430, 1986.

## 写作定位备注（不属于论文正文）

- 不建议写“首次提出 Agent 事务”。Cordon、Agentic Transaction 和 ATCC 已直接使用 semantic/agentic transaction 概念。
- 更稳妥的核心 novelty claim 包含两点：**（1）统一管理数据状态、分支状态和任务语义，并由此实现快照安全的跨分支计算共享；（2）利用 LLM 将开放式任务语义编译为可验证契约，再由确定性验证器实施语义并发控制。**最终是否可以使用“首次”，仍应在投稿前做一次系统性文献检索并限定范围。
- 目前 78 条轨迹的共享机会和 71 条写轨迹的配对扰动证据较扎实；在线性能只有一个任务、一个 base seed，应保持为 pilot 表述，不能写成“平均提升”。
- 若篇幅有限，可把第 3—4 段中对相关工作的展开移到 Related Work，但应在 Introduction 中至少保留一句对 ATCC、Cordon 和 Agentic Transaction 的区别，否则审稿人很可能认为问题定义与已有工作重合。
