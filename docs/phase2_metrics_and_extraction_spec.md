# Phase 2: Architecture Ground-Truth Extraction & Conformance Measurement Instrument

**Study Title:** *Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions*  
**Author:** Senior Research Software Engineer  
**Target Venue:** Empirical Software Engineering (ICSE / FSE / ASE / JSS / IST)  
**Document Status:** Complete Phase 2 Specification Document  

---

## 1. Ground-Truth Architecture Extraction Methodology

To evaluate architectural drift objectively, we extract an explicit, machine-checkable architectural model $A = (V, E_{allowed}, R)$ for each target repository prior to agent execution.

```
                      Pre-Task Repository State
                                  │
                                  ▼
                     Static Import Graph Extractor
                     (Python: grimp | TS: dep-cruiser)
                                  │
                                  ▼
                    Raw Module Dependency Graph G_0
                                  │
      ┌───────────────────────────┴───────────────────────────┐
      ▼                                                       ▼
Repository Docs / ADRs                                Directory Heuristic Protocol
(Explicit Layer Rules)                                (Inferred Layer Boundaries)
      │                                                       │
      └───────────────────────────┬───────────────────────────┘
                                  ▼
                   Machine-Checkable Rule Config
                  (yaml / json Fitness Function)
```

### 1.1 Tooling & Graph Extraction Protocol
We do not use hand-rolled AST parsers. Static dependency graphs are extracted using established, production-grade static analysis tools:

* **Python Repositories:** Extracted via `grimp` (High-performance C-extension underlying `import-linter`) supplemented by `pydeps` for visual graph exports.
* **TypeScript Repositories:** Extracted via `dependency-cruiser` (leveraging TypeScript AST resolution including `tsconfig.json` path aliases) supplemented by `madge`.

**Graph Abstraction:** A repository module graph $G = (V, E)$ represents:
* $V$: The set of top-level modules/packages or domain directories.
* $E \subseteq V \times V$: Directed edges where $(u, v) \in E$ indicates module $u$ explicitly imports from module $v$.

### 1.2 Layer Assignment Protocol
Every module $v \in V$ is assigned to a formal Architectural Layer $L(v) \in \{L_1, L_2, \dots, L_k\}$ ordered by abstraction height ($L_1 = \text{Domain Core}$, $L_k = \text{Infrastructure/Entrypoints}$). Layer assignment uses a strict 2-tier hierarchy:

1. **Tier A (Explicit Repository Documentation):** If the repository provides Architecture Decision Records (ADRs), `ARCHITECTURE.md`, or README layer diagrams, layer mapping directly mirrors documented conventions.
2. **Tier B (Directory-Heuristic Protocol):** When explicit docs are absent, layer assignments are inferred from directory tree depth and naming conventions:
   * **Domain Layer ($L_1$):** `domain/`, `core/`, `models/`, `entities/`
   * **Application Layer ($L_2$):** `use_cases/`, `services/`, `workflows/`, `handlers/`
   * **Adapter Layer ($L_3$):** `adapters/`, `repositories/`, `clients/`, `db/`
   * **Infrastructure / Interface Layer ($L_4$):** `api/`, `cli/`, `controllers/`, `main.py`, `index.ts`

> **Methodological Assumption & Threat to Validity:** Tier B assumes directory organization reflects intended architectural separation. When directory structure is ambiguous, the baseline state at $commit_0$ is assumed to be compliant, and drift is measured relative to new violations introduced by agent edits.

### 1.3 Machine-Checkable Architectural Rule Set Schema
Ground-truth rules are encoded as a machine-checkable YAML schema (`arch_rules.yaml`):

```yaml
version: "1.0"
repository: "PY-S1-fastapi-users"
layers:
  - id: L1_domain
    modules: ["fastapi_users.models", "fastapi_users.schemas"]
  - id: L2_service
    modules: ["fastapi_users.manager", "fastapi_users.authentication"]
  - id: L3_adapter
    modules: ["fastapi_users.db"]
  - id: L4_entrypoint
    modules: ["fastapi_users.router"]

rules:
  forbidden_dependencies:
    # High-level domain must not import low-level adapters or routers
    - source: L1_domain
      target: [L2_service, L3_adapter, L4_entrypoint]
      severity: CRITICAL
    - source: L2_service
      target: [L4_entrypoint]
      severity: HIGH
  encapsulation:
    # Private internal modules cannot be imported cross-package
    - module: "fastapi_users._internal"
      allow_imports_from: ["fastapi_users._internal"]
      severity: MEDIUM
```

---

## 2. Precise Mathematical Definition of Drift Metrics

Let $G_0 = (V_0, E_0)$ be the initial baseline dependency graph, and $G_t = (V_t, E_t)$ be the dependency graph at session checkpoint $t \in \{0, 1, 2, \dots, T\}$. Let $\Delta CC_t$ be the total change in Cyclomatic Complexity introduced up to session $t$.

### 2.1 Dependency Graph Edit Distance (DGED)

DGED measures structural graph alteration between baseline $G_0$ and checkpoint $G_t$:

$$\text{DGED}(G_0, G_t) = |V_0 \setminus V_t| + |V_t \setminus V_0| + |E_0 \setminus E_t| + |E_t \setminus E_0|$$

For pure additions (common in feature implementation tasks), where $V_0 \subseteq V_t$ and $E_0 \subseteq E_t$:

$$\text{DGED}(G_0, G_t) = |V_t \setminus V_0| + |E_t \setminus E_0| = \Delta |V| + \Delta |E|$$

### 2.2 Layering Violation Count (LVC) & Normalized LVC

Let $E_{new}(t) = E_t \setminus E_0$ be the set of newly introduced dependency edges at session $t$. An edge $(u, v) \in E_{new}(t)$ is defined as a **Layering Violation** if it violates any rule in the machine-checkable rule set $R$:

$$\text{Violations}(t) = \{ (u, v) \in E_{new}(t) \mid \text{RuleViolated}((u, v), R) = \text{True} \}$$

$$\text{LVC}(t) = |\text{Violations}(t)|$$

To normalize across repositories of varying sizes, we calculate **Normalized LVC ($\text{LVC}_{norm}$)** relative to initial total edges $|E_0|$:

$$\text{LVC}_{norm}(t) = \frac{\text{LVC}(t)}{|E_0| + 1} \times 10^3$$

*(Expressed as new violations per 1,000 baseline dependency edges).*

### 2.3 Conformance Decay Rate (CDR)

Rather than evaluating only the final state, CDR measures the *trajectory shape* of drift across sequential agent checkpoints $t = 1, 2, \dots, T$.

We model conformance decay by fitting a linear trajectory over checkpoint sessions:

$$\text{LVC}_{norm}(t) = \alpha + \beta_{CDR} \cdot t + \epsilon_t$$

Where:
* $\beta_{CDR}$ (**Conformance Decay Rate**): The slope coefficient representing the rate of architectural erosion per agent session.
* $\beta_{CDR} > 0$ indicates accelerating structural drift.
* Non-linear trajectories are classified using monotonic trend tests (Mann-Kendall test $\tau$).

### 2.4 Cyclomatic-Complexity-Normalized Drift Metrics

To prevent large feature additions from trivially inflating architectural drift scores, we normalize structural violations by the total Cyclomatic Complexity added ($\Delta CC_t$).

Using `lizard` or `radon` to compute total AST cyclomatic complexity $CC(G)$:

$$\Delta CC_t = \max(1, CC(G_t) - CC(G_0))$$

We define **Complexity-Normalized Drift ($\text{CND}$)** and **Complexity-Normalized Layering Violation ($\text{CNLV}$)**:

$$\text{CND}(t) = \frac{\text{DGED}(G_0, G_t)}{\Delta CC_t}$$

$$\text{CNLV}(t) = \frac{\text{LVC}(t)}{\Delta CC_t}$$

*Interpretation:* $\text{CNLV}(t)$ measures how many architectural boundary violations the agent creates **per unit of added control-flow complexity**. An agent that adds 500 lines of complex algorithm without crossing layer boundaries will have $\text{CNLV} \approx 0$, whereas an agent that shortcuts architecture by directly importing a DB adapter inside a core entity will spike $\text{CNLV} \gg 0$.

---

## 3. Worked Numerical Example on a Toy Repository

Consider a 5-module micro-app `ToyApp` evaluated across $T = 3$ agent sessions.

### Initial State ($t = 0$)
* **Modules ($V_0$):** `domain`, `service`, `db_adapter`, `api` (4 modules).
* **Edges ($E_0$):** 3 edges: `service` $\rightarrow$ `domain`, `db_adapter` $\rightarrow$ `service`, `api` $\rightarrow$ `service`.
* **Layer Rules ($R$):**
  * Rule 1: `domain` cannot import from `service`, `db_adapter`, or `api`.
  * Rule 2: `service` cannot import from `api` or `db_adapter`.
* **Baseline Stats:** $|V_0| = 4$, $|E_0| = 3$, $CC(G_0) = 20$. Initial violations = 0.

```
Baseline Graph (t=0):
  [api] ────> [service] ────> [domain]
                     ^
                     │
              [db_adapter]
```

### Agent Trajectory Breakdown

#### Session 1 ($t = 1$): Add Domain Entity & Helper
* Agent introduces new module `utils`.
* Edges added: `domain` $\rightarrow$ `utils` (valid), `service` $\rightarrow$ `utils` (valid).
* $|V_1| = 5$, $|E_1| = 5$. Added edges = 2.
* Violations at $t=1$: 0.
* $CC(G_1) = 25 \implies \Delta CC_1 = 5$.
* **Metrics at $t=1$:**
  * $\text{DGED}(G_0, G_1) = 1 \text{ (new node)} + 2 \text{ (new edges)} = 3$
  * $\text{LVC}(1) = 0$
  * $\text{CNLV}(1) = 0 / 5 = 0.00$

#### Session 2 ($t = 2$): Implement Caching in Domain (Shortcut Taken)
* Agent modifies `domain` to directly import `db_adapter` for cache fetching (Shortcut violation of Rule 1!).
* Edges added: `domain` $\rightarrow$ `db_adapter` (**ILLEGAL EDGE**).
* $|V_2| = 5$, $|E_2| = 6$.
* Violations at $t=2$: 1 (`domain` $\rightarrow$ `db_adapter`).
* $CC(G_2) = 30 \implies \Delta CC_2 = 10$.
* **Metrics at $t=2$:**
  * $\text{DGED}(G_0, G_2) = 1 + 3 = 4$
  * $\text{LVC}(2) = 1$
  * $\text{CNLV}(2) = 1 / 10 = 0.10$

#### Session 3 ($t = 3$): Expose Direct DB Query in API Layer
* Agent modifies `api` to directly bypass `service` and import `db_adapter` (Violation of Rule 2!).
* Edges added: `api` $\rightarrow$ `db_adapter` (**ILLEGAL EDGE**).
* $|V_3| = 5$, $|E_3| = 7$.
* Violations at $t=3$: 2 (`domain` $\rightarrow$ `db_adapter`, `api` $\rightarrow$ `db_adapter`).
* $CC(G_3) = 36 \implies \Delta CC_3 = 16$.
* **Metrics at $t=3$:**
  * $\text{DGED}(G_0, G_3) = 1 + 4 = 5$
  * $\text{LVC}(3) = 2$
  * $\text{LVC}_{norm}(3) = (2 / 4) \times 1000 = 500.0$
  * $\text{CNLV}(3) = 2 / 16 = 0.125$

```
Post-Session 3 Graph (t=3):
  [api] ────────> [service] ────────> [domain] ───> [utils]
    │                                    │            ^
    │ (Illegal Edge)      (Illegal Edge) │            │
    └───────────> [db_adapter] <─────────┘            │
                        ^                             │
                        └─────────────────────────────┘
```

#### Trajectory Fit ($\beta_{CDR}$)
Fitting linear regression across $t \in \{1, 2, 3\}$ for $\text{LVC}(t) = [0, 1, 2]$:
$$\beta_{CDR} = +1.00 \text{ violations / session}$$
This indicates a steady, linear architectural degradation across multi-session execution.

---

## 4. Related Work Differentiation Paragraph

> **Camera-Ready Related Work Paragraph:**  
> Prior benchmarks evaluating AI coding agents focus primarily on functional correctness (SWE-bench [1]) or surface-level code quality erosion. Most notably, SlopCodeBench [2] quantifies "code slop" through AST verbosity, duplicate logic, and unmaintained comments, while RoadmapBench [3] frames code evolution strictly through API version migration accuracy. However, neither framework measures macro-level structural integrity. A codebase can maintain flawless linter pass rates and high test coverage while silently degrading architectural layering—such as high-level domain abstractions directly importing low-level database drivers. Our study bridges this critical gap by introducing **Architectural Conformance Drift**, isolating structural dependency graph mutations ($\text{DGED}$) and cross-layer boundary violations ($\text{LVC}$) normalized by control-flow complexity ($\text{CNLV}$) across long-horizon, multi-session agent trajectories.

---

## 5. Tooling Selection Justification ("Why Not Just Use X?")

| Alternative Tool | Why It Is Insufficient For This Study | Our Chosen Approach & Justification |
| :--- | :--- | :--- |
| **Standard Linters** (`flake8`, `eslint`, `ruff`) | Standard linters evaluate local AST nodes (formatting, unused variables, simple complexity). They possess zero awareness of global module dependency graphs or cross-directory architectural layering rules. | **`grimp` / `dependency-cruiser` + Custom Ruleset**: Static graph engines extract the global import DAG, allowing us to evaluate architectural boundaries across multi-package directories. |
| **SlopCodeBench Metrics** | SlopCodeBench measures micro-smells (code duplication, bloat, commentary verbosity). An agent can write perfectly concise, non-redundant code that completely destroys hexagonal architecture boundaries. | **Layering Violation Count ($\text{LVC}$)**: Specifically isolates cross-boundary dependency violations, decoupling structural drift from micro-level syntax bloat. |
| **SonarQube / Commercial Static Scanners** | SonarQube rules focus heavily on security vulnerabilities and cognitive complexity thresholds. Configuring custom cross-module layering rules across heterogeneous repos is non-reproducible and proprietary. | **Open-Source Declarative Fitness Functions**: Using explicit YAML rule files paired with `grimp`/`dependency-cruiser` ensures 100% reproducible execution in headless CLI pipelines (Colab/Kaggle). |
| **Raw `git diff` / LOC Delta** | Diff size merely measures code volume. A 500-line refactoring within a domain entity causes zero architectural drift, whereas a 2-line illegal import statement breaches architectural isolation. | **Complexity-Normalized Metrics ($\text{CNLV}$)**: Normalizes violations against Cyclomatic Complexity change ($\Delta CC$), ensuring large feature additions are not penalized unless structural boundaries are breached. |

---

## 6. Next Steps for Phase 3

1. Design the **API Caching & Execution Engine Architecture** (zero-repay LLM logging, fault-tolerant checkpointing for free Colab/Kaggle runtimes).
2. Specify JSON schema for session state persistence and execution replay.
