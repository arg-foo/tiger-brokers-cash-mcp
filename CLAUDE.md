<always>
  <plan>
    
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
  <deps type="dev">
    <dep name="pytest"         pin=">=8.0,&lt;9.0" />
    <dep name="pytest-asyncio" pin=">=0.23,&lt;1.0" />
    <dep name="pytest-cov"     pin=">=5.0,&lt;6.0" />
    <dep name="pytest-timeout" pin=">=2.2,&lt;3.0" />
    <dep name="respx"          pin=">=0.21,&lt;1.0" />
    <dep name="ruff"           pin=">=0.8,&lt;1.0" />
    <dep name="mypy"           pin=">=1.7,&lt;2.0" />
  </deps>
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

### Python Tooling (70-90% savings)                                                                                                                                 
```bash                                                                                                                                                             
rtk pytest              # Pytest failures only (90%)                                                                                                                
rtk pytest -x           # Works with all pytest flags                                                                                                               
rtk ruff check          # Ruff lint violations grouped (80%)                                                                                                        
rtk ruff format         # Ruff format output compact (70%)                                                                                                          
rtk pip list            # Compact package list (70%)                                                                                                                
rtk pip install         # Compact install output (90%)                                                                                                              
rtk pip show <pkg>      # Compact package info (70%)                                                                                                         
rtk pip outdated        # Compact outdated packages (80%)                                                                                                    
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