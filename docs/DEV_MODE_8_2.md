# Jervis 8.2 Dev Mode — initial safe Git inspection

**Experimental and read-only.** \`inspect_git()\` allows four fixed operations:
status, diff check, diff stats, and last five commits. No shell interpolation,
remote fetches, Git hooks, external diff/text converters, agent prompts,
branch changes, file writes, code execution, or patch application.

Callers must present a verified authenticated Jervis principal and a scoped
\`filesystem.read\` grant. The repository must be the exact approved root,
not merely a descendant of a broader checkout. The result is bounded to
64 KiB and remains private local data unless separate provider disclosure
is authorized. Permission boundaries must be rechecked at the action
boundary, not inferred from a model's confidence.

Still required: worktree isolation, explicit write approvals, durable mission
integration, test execution in an OS-isolated environment, secret scanning,
status UI, cross-platform hostile-repository testing and physical acceptance.
Do not expose unrestricted shell execution as Dev Mode.
