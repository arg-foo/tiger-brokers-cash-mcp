<always>
  <plan>
    **Claude Code Prompt for Plan Mode**
    **#prompts**

    Review this plan thoroughly before making any code changes. For every issue or recommendation, explain the concrete tradeoffs, give me an opinionated recommendation, and ask for my input before assuming a direction.
    My engineering preferences (use these to guide your recommendations):
    - DRY is important—flag repetition aggressively.
    - Well-tested code is non-negotiable; I'd rather have too many tests than too few.
    - I want code that's "engineered enough" — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity).
    - I err on the side of handling more edge cases, not fewer; thoughtfulness > speed.
    - Bias toward explicit over clever.

    **1. Architecture review**
    Evaluate:
    - Overall system design and component boundaries.
    - Dependency graph and coupling concerns.
    - Data flow patterns and potential bottlenecks.
    - Scaling characteristics and single points of failure.
    - Security architecture (auth, data access, API boundaries).

    **2. Code quality review**
    Evaluate:
    - Code organization and module structure.
    - DRY violations—be aggressive here.
    - Error handling patterns and missing edge cases (call these out explicitly).
    - Technical debt hotspots.
    - Areas that are over-engineered or under-engineered relative to my preferences.

    **3. Test review**
    Evaluate:
    - Test coverage gaps (unit, integration, e2e).
    - Test quality and assertion strength.
    - Missing edge case coverage—be thorough.
    - Untested failure modes and error paths.

    **4. Performance review**
    Evaluate:
    - N+1 queries and database access patterns.
    - Memory-usage concerns.
    - Caching opportunities.
    - Slow or high-complexity code paths.

    **For each issue you find**
    For every specific issue (bug, smell, design concern, or risk):
    - Describe the problem concretely, with file and line references.
    - Present 2–3 options, including "do nothing" where that's reasonable.
    - For each option, specify: implementation effort, risk, impact on other code, and maintenance burden.
    - Give me your recommended option and why, mapped to my preferences above.
    - Then explicitly ask whether I agree or want to choose a different direction before proceeding.

    **Workflow and interaction**
    - Do not assume my priorities on timeline or scale.
    - After each section, pause and ask for my feedback before moving on.

    BEFORE YOU START:
    Ask if I want one of two options:
    1/ BIG CHANGE: Work through this interactively, one section at a time (Architecture → Code Quality → Tests → Performance) with at most 4 top issues in each section.
    2/ SMALL CHANGE: Work through interactively ONE question per review section

    FOR EACH STAGE OF REVIEW: output the explanation and pros and cons of each stage's questions AND your opinionated recommendation and why, and then use AskUserQuestion. Also NUMBER issues and then give LETTERS for options and when using AskUserQuestion make sure each option clearly labels the issue NUMBER and option LETTER so the user doesn't get confused. Make the recommended option always the 1st option.
  </plan>
  <implementing>
    <steps>
      <1>Use tdd-engineer sub agent for implementing features, writing tests, debugging, or reviewing code</1>
      <2>Use code-reviewer sub agent to review the implementation and output review feedbacks</2>
      <3>Use tdd-engineer sub agent to implement the review feedback</3>
      <4>Repeat step 2 and 3 until there are no more review feedbacks</4>
      <5>Git commit existing changes</5>
      <6>Git push and submit push request</6>
    </steps>
  </implementing>
  <technical-design>
    Use solutions-architect sub agent for analyzing requirements, creating technical proposals, evaluating solution feasibility, finding open-source projects, or designing system architectures.
  </technical-design>
</always>

<tech-stack>
  <runtime lang="Python" version=">=3.12" async="asyncio" pkg="uv" build="hatchling" />
  <mcp framework="mcp SDK" api="FastMCP" transport="stdin/stdout" pin="mcp>=1.20,&lt;2.0" />
  <tooling>
    <tool name="uv" role="package-manager" note="Use 'uv run' to execute scripts/tests, 'uv sync' to install deps" />
  </tooling>
</tech-stack>

<rtk-instructions>
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Git
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### Files & Search
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
```

### Python Tooling
```bash
rtk uv sync             # Compact dependency sync output
rtk uv sync --dev       # Works with all uv sync flags
rtk uv run pytest       # Pytest failures only (90%)
rtk uv run pytest -x    # Works with all pytest flags
rtk uv run ruff check   # Ruff lint violations grouped (80%)
rtk uv run ruff format  # Ruff format output compact (70%)
rtk uv run uvicorn      # Compact server startup output
rtk uv pip list         # Compact package list
rtk uv pip install      # Compact install output
```

### Network
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```
</rtk-instructions>