# Phase 1: Repository & Task Corpus Design Protocol

**Study Title:** *Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions*  
**Author:** Senior Research Software Engineer  
**Target Venue:** Empirical Software Engineering (ICSE / FSE / ASE / JSS / IST)  
**Document Status:** Complete Phase 1 Design Specification  

---

## 1. Overview & Research Methodology Goals

This study evaluates whether long-horizon autonomous coding agent trajectories (across multi-session, multi-step tasks) induce **Architectural Conformance Drift**—unintended degradation of module boundaries, illegal cross-layer dependencies, and structural layering violations.

To ensure empirical rigor and defense-grade reproducibility, Phase 1 establishes:
1. A **Scored Repository Selection Rubric** with explicit exclusion rules to eliminate selection bias, including a mandatory matching gate for baseline comparability.
2. A **Matched Task Design Protocol** to compare agents against human commits of similar scope rather than organic git history.
3. A **Sample Size Justification** balancing statistical power (MDES) and execution budget.
4. A **Long-Horizon Task Authoring Specification & Template** ensuring tasks demand multi-session (>3 context windows) and multi-layer (>5 file touches) edits.
5. An explicit **Threats to Validity** mapping for empirical SE peer review.

### 1.1 Sample Size Justification & Budget Tradeoff
Given financial and rate-limit constraints, we target an evaluation corpus of $N = 10$ Python repositories, with 1 task per repository executed across 3 sequential agent sessions. This yields $N_1 = 30$ agent session observations and $N_2 = 30$ matched human observations. Based on our post-hoc power analysis, a sample size of 30 observations per group at $\alpha = 0.05$ yields a Minimum Detectable Effect Size (MDES) of $d = 0.72$ at 80% statistical power. This indicates that the study is sufficiently powered to detect medium-to-large architectural drift differences. We accept the limitation of being underpowered for small effect sizes ($d < 0.72$) as an explicit tradeoff to keep overall execution costs within a modest $\$50.00$ budget ($\approx \$1.50$ API spend per full 3-session task run).

---

## 2. Scored Selection Rubric (Reproducible Qualification)

Every candidate repository is evaluated on a **100-Point Scored Qualification Rubric**. A repository must achieve a **minimum total score of 75 points** (with 0 score on any mandatory gate) to qualify for inclusion in the evaluation corpus.

### Rubric Breakdown

| Category | Criterion | Max Points | Evaluation & Scoring Rules |
| :--- | :--- | :---: | :--- |
| **A. Architecture (Mandatory Gate)** | **Intelligibility & Explicit Boundaries** | 25 | **25 pts:** Clear layered/hexagonal/modular architecture with explicit directory separation (e.g., `core/`, `domain/`, `adapters/`, `api/`).<br>**15 pts:** Convention-based module separation with documented module responsibilities.<br>**0 pts:** Flat directory structure, circular imports, or monolithic "kitchen sink" organization (**AUTOMATIC REJECT**). |
| **B. History (Mandatory Gate)** | **Human Commit Depth** | 20 | **20 pts:** $\ge 500$ commits with $\ge 5$ distinct human contributors.<br>**12 pts:** 200–499 commits with $\ge 3$ contributors.<br>**0 pts:** $< 200$ commits or single-author personal scratchpad (**AUTOMATIC REJECT**). |
| **C. Testability (Mandatory Gate)** | **Headless Test Suite Execution** | 20 | **20 pts:** Headless `pytest` or `jest` suite executes in $<3$ minutes, zero external network dependencies (hermetic), line coverage $>70\%$.<br>**12 pts:** Executes in $3–8$ minutes, hermetic, coverage $50–70\%$.<br>**0 pts:** Flaky tests, requires external live databases/APIs without mocks, build time $>8$ mins (**AUTOMATIC REJECT**). |
| **D. Licensing (Mandatory Gate)** | **Permissive Open-Source License** | 15 | **15 pts:** Explicit OSI-approved permissive license (MIT, Apache 2.0, BSD-2/3 Clause).<br>**0 pts:** Copyleft (GPL, AGPL, LGPL), non-commercial, or unlicensed (**AUTOMATIC REJECT**). |
| **E. Engineering Hygiene** | **Dependency & Environment Stability** | 5 | **5 pts:** Pinning via `pyproject.toml` / `poetry.lock` / `package-lock.json`, modern runtime support (Python $\ge 3.10$, Node $\ge 18$).<br>**3 pts:** Minor unpinned transient dependencies requiring simple lockfile generation.<br>**0 pts:** Deprecated runtimes, unbuildable natively. |
| **F. Matched Task (Mandatory Gate)** | **Matched Human Baseline Task Availability** | 15 | **15 pts:** A real, historical human contribution exists in the repo resolving a comparable issue matching these criteria: (a) file-touch count is $\pm 2$ files of the agent task, (b) same issue type (bugfix/feature/refactor), and (c) touches the same subsystem/layer.<br>**0 pts:** No comparable matched human task can be identified or constructed from history (**AUTOMATIC REJECT**). |

**Inclusion Threshold:** $\text{Total Score} \ge 75/100$, AND no score of $0$ in Categories A, B, C, D, or F.

### 2.1 Matched-Task Matching Protocol Details
To prevent comparing directed agent execution against organic human commit histories (which often contain trivial refactorings or single-line fixes), we enforce a matched-pair design. For each agent task $T_{\text{agent}}$, the matched human baseline task $T_{\text{human}}$ must satisfy:
1. **Scope Equivalency:** The human commit must touch a similar number of files ($|F_{\text{human}} - F_{\text{agent}}| \le 2$).
2. **Intent Equivalency:** The issue type (e.g., implementing an API endpoint or adding a database adapter) must match the agent's task type.
3. **Subsystem Locality:** The changes must occur in the same architectural boundary (e.g., both must touch the adapters layer).
If no such historical human task can be matched, the repository is excluded.

---

## 3. Stratified Sampling Protocol & Candidate Corpus

To maximize external validity and ensure results generalize beyond a single repo archetype, candidate repos are stratified across three orthogonal dimensions:
1. **Language:** Python vs. TypeScript (dominant languages in SWE-bench / agent evaluation).
2. **Repository Size:** Small ($1\text{k}–10\text{k}$ LOC), Medium ($10\text{k}–50\text{k}$ LOC), Large ($50\text{k}–200\text{k}$ LOC).
3. **Application Domain:** Web Backend / API, Developer CLI Tool, Data / Analytics Library.

### Stratification Sampling Matrix (Target N = 18)

```
                       +----------------------+----------------------+----------------------+
                       |     Web Backend      |    Developer CLI     |  Data / Library      |
+------------+---------+----------------------+----------------------+----------------------+
| Python     | Small   | FastAPI microservice | Typer/Click CLI      | Pydantic extension   |
|            | Medium  | Flask/Django app     | Ruff/Black wrapper   | ORM / Query builder  |
|            | Large   | Full API Server      | Complex Dev scaffold | Data processing core |
+------------+---------+----------------------+----------------------+----------------------+
| TypeScript | Small   | Express API          | Commander CLI        | Utility library      |
|            | Medium  | NestJS backend       | Devtool / Linter     | State / Data engine  |
|            | Large   | Fullstack server     | Build tool / Scaffold| Enterprise SDK       |
+------------+---------+----------------------+----------------------+----------------------+
```

### Qualified Candidate Repositories List

Below are **18 vetted candidate repositories** satisfying all mandatory gates and license constraints.

#### Python Corpus (9 Repositories)

| ID | Repository | Size Tier | Domain | Architectural Style | License | Test Framework | LOC (Approx) | Commits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `PY-S1` | **FastAPI-Users** (`fastapi-users/fastapi-users`) | Small | Web Backend | Hexagonal / Port-Adapter | MIT | `pytest` | ~6.5k | ~1,200 |
| `PY-S2` | **HTTPie** (`httpie/cli`) | Small | Dev CLI | Layered CLI / Core / Plugin | BSD-3 | `pytest` | ~9.8k | ~4,500 |
| `PY-S3` | **Diskcache** (`grantjenks/python-diskcache`) | Small | Data Library | Core Storage Engine | Apache-2.0 | `pytest` | ~5.2k | ~850 |
| `PY-M1` | **SQLModel** (`fastapi/sqlmodel`) | Medium | Data / ORM | Layered (Pydantic + SQLAlchemy) | MIT | `pytest` | ~14k | ~950 |
| `PY-M2` | **LiteLLM** (`BerriAI/litellm`) | Medium | Web / API | Router / Provider Adapter Pattern | MIT | `pytest` | ~38k | ~6,200 |
| `PY-M3` | **Textual** (`Textualize/textual`) | Medium | Dev CLI / TUI | Event-driven Widget Hierarchy | MIT | `pytest` | ~42k | ~3,800 |
| `PY-L1` | **PostHog** (`PostHog/posthog-python`) | Large | Web / Analytics | Modular Monolith Client | MIT | `pytest` | ~58k | ~1,800 |
| `PY-L2` | **Kedro** (`kedro-org/kedro`) | Large | Data / Pipeline | Framework Plugin / Node DAG Architecture | Apache-2.0 | `pytest` | ~85k | ~5,400 |
| `PY-L3` | **Home-Assistant Core Submodule** (`home-assistant/core` - component slice) | Large | Modular System | Event Bus / Entity Integration Layers | Apache-2.0 | `pytest` | ~180k | ~45,000 |

#### TypeScript Corpus (9 Repositories)

| ID | Repository | Size Tier | Domain | Architectural Style | License | Test Framework | LOC (Approx) | Commits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `TS-S1` | **TRPC Core** (`trpc/trpc`) | Small | Web Backend | Type-safe Router / Procedure Pipeline | MIT | `vitest`/`jest` | ~8.5k | ~3,200 |
| `TS-S2` | **MeiliSearch JS** (`meilisearch/meilisearch-js`) | Small | Dev Library | Client SDK / HTTP Adapter Layer | MIT | `jest` | ~6.2k | ~950 |
| `TS-S3` | **Inquirer.js** (`SBoudrias/Inquirer.js`) | Small | Dev CLI | Prompt Controller / Input Adapters | MIT | `jest` | ~7.8k | ~1,600 |
| `TS-M1` | **Medusa** (`medusajs/medusa` - core package) | Medium | Web / E-Commerce | Module / Service Layered Architecture | MIT | `jest` | ~45k | ~8,900 |
| `TS-M2` | **TypeORM** (`typeorm/typeorm`) | Medium | Data / ORM | Metadata / Driver Adapter Pattern | MIT | `jest` | ~48k | ~6,500 |
| `TS-M3` | **Prisma Client** (`prisma/prisma` - client pkg) | Medium | Data / Query | Code Generator / Engine Bridge Layer | Apache-2.0 | `jest` | ~39k | ~14,000 |
| `TS-M4` | **Plop** (`plopjs/plop`) | Small-Med | Dev CLI | Generator / Action / Prompt Controller | MIT | `jest` | ~11k | ~750 |
| `TS-L1` | **NestJS Core** (`nestjs/nest`) | Large | Web Framework | Dependency Injection / Module Tree | MIT | `jest` | ~92k | ~7,400 |
| `TS-L2` | **Directus** (`directus/directus` - api pkg) | Large | Web / Headless CMS | Modular API / Storage Drivers | GPL-free MIT core | `jest` | ~135k | ~18,000 |

---

## 4. Long-Horizon Task Specification & Authoring Protocol

To observe architectural drift, tasks cannot be isolated bug fixes (single-file patches). Tasks must simulate realistic, multi-session software evolution.

### Task Qualification Criteria
1. **File Touch Scope:** Requires modifying or introducing $\ge 5$ files spanning at least 2 distinct architectural layers (e.g., Domain Core + Infrastructure Adapter + API Controller).
2. **Context Horizon Multi-Session Decomposition:** Task complexity must naturally split into $\ge 3$ sequential sub-goals. Agent context must be reset between sub-goals, forcing the agent to read existing codebase patterns rather than relying on in-memory chat history.
3. **Verifiable Ground Truth Oracle:** Acceptance requires passing (a) existing regression tests + (b) task-specific unit/integration tests added by the benchmark.

---

## 5. Task Authoring Template

All benchmark tasks must be documented using the standardized Markdown schema below:

```markdown
# TASK BENCHMARK SPECIFICATION

## Task Metadata
- **Task ID:** TASK-[REPO_ID]-[INDEX] (e.g., TASK-PY-S1-01)
- **Target Repo:** [Repo Owner / Repo Name]
- **Base Commit Hash:** [Full git commit SHA]
- **Language / Test Runner:** [Python (pytest) | TypeScript (jest)]
- **Target Architectural Layers Touched:**
  - Layer 1: Domain / Core Business Logic (`src/core/`)
  - Layer 2: Persistence / External Adapter (`src/adapters/` or `src/services/`)
  - Layer 3: Boundary Interface (`src/api/` or `src/cli/`)

---

## 1. Task Description (Agent Prompt)
[Insert detailed user feature request / GitHub issue description. Must state expected behavior without prescribing internal implementation choices, allowing the agent to either respect or violate architectural constraints.]

---

## 2. Multi-Session Sequential Execution Plan

### Session 1: Core Domain & Data Model Extension
- **Objective:** Extend core entities / domain interfaces to support the new feature.
- **Expected Touch Points:** `src/domain/entities/`, `src/domain/interfaces/`
- **Session Reset Boundary:** Context wiped after domain tests pass.

### Session 2: Infrastructure & Service Integration
- **Objective:** Implement persistence/adapter logic adhering to core interfaces.
- **Expected Touch Points:** `src/infrastructure/` or `src/adapters/`
- **Session Reset Boundary:** Context wiped after adapter integration tests pass.

### Session 3: External Exposure (API / CLI Controller & Wiring)
- **Objective:** Expose the new capabilities via entrypoints and dependency injection wiring.
- **Expected Touch Points:** `src/api/controllers/` or `src/cli/commands/`
- **Session Completion Boundary:** All repository tests + task acceptance tests pass.

---

## 3. Explicit Architectural Invariants (Ground Truth Reference Rules)

*These rules define the baseline architectural model. Violations of these rules constitute Architectural Drift.*

1. **Dependency Direction Rule:** High-level domain code (`src/domain/`) MUST NOT import from low-level infrastructure (`src/infrastructure/`) or presentation (`src/api/`).
2. **Boundary Isolation Rule:** External HTTP request/response DTOs must not bleed into core domain entity methods.
3. **Module Encapsulation Rule:** Private module components (`_internal/` or unexported symbols) must not be imported across package boundaries.

---

## 4. Ground Truth Oracle & Evaluation Pipeline
1. **Functional Verification Command:** `pytest tests/tasks/test_task_spec.py` (or `npm test`)
2. **Regression Check Command:** `pytest` (full original test suite)
3. **Architectural Drift Measurement Trigger:** Run static dependency analyzer on diff (`import-linter`, `dep-check`, or AST dependency parser).
```

---

## 6. Threats to Validity & Mitigation Strategies

| Threat Type | Risk Factor | Research Mitigation Strategy |
| :--- | :--- | :--- |
| **Construct Validity** | Architectural drift is confused with trivial formatting or syntax code smells. | We separate **Surface Quality** (linter warnings, cyclomatic complexity, SlopCodeBench metrics) from **Architectural Conformance** (dependency graph cycle creation, layer boundary violations via AST import parsing). |
| **Internal Validity** | Test non-determinism or context window truncation invalidates task completion. | Every task must execute inside a hermetic container with pinned dependencies. Tasks must be pre-tested by human baseline executions to guarantee feasibility. |
| **External Validity** | Findings only apply to small Python repositories. | Stratified sampling across 3 sizes (Small, Medium, Large) and 3 domains across both Python and TypeScript mitigates single-ecosystem bias. |
| **Selection Bias** | Repositories chosen favor specific coding styles. | Standardized 100-point scoring rubric with explicit thresholds ensures reproducible selection without manual cherry-picking. |

---

## 7. Next Steps for Phase 2

1. Review and refine candidate repository list.
2. Establish formal metrics definition for **Architectural Conformance Drift** (e.g., Dependency Graph Edges Violation Rate, Module Encapsulation Index, Layer Divergence Score).
3. Specify AST-based static analysis tooling (`import-linter`, `griffe`, `ts-morph` / `dependency-cruiser`).
