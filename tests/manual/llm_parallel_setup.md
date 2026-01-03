# LLM Parallel Collaboration (Codex + Gemini)

This is a **manual, two-terminal recipe** for running two LLM CLI agents
(Codex + Gemini) in parallel on the **same mounted Gate view**, so locks
are enforced and edits cannot overwrite each other.

---

## 0) Bring Gate up (host-direct default)

```
/home/kajsfasdfnaf/Desktop/shared_concurrency_substrate/dist/gate up \
  --base ubuntu-24.04 \
  --vm-dir /home/kajsfasdfnaf/Desktop/shared_concurrency_substrate/vm_build \
  --vm-name gate-vm \
  --ssh-key ~/.ssh/shared_concurrency_substrate_test.pub \
  --repo-path /tmp/gate_demo_repo
```

If you want a new empty repo:
```
mkdir -p /tmp/gate_demo_repo
git -C /tmp/gate_demo_repo init
```

Confirm mount is active:
```
/home/kajsfasdfnaf/Desktop/shared_concurrency_substrate/dist/gate status --vm-name gate-vm
```

Mounted path (both agents must use this):
```
$HOME/.local/state/gate/mounts/gate-host-direct
```

---

## 1) Create a coordination file

```
MOUNT="$HOME/.local/state/gate/mounts/gate-host-direct"
cat > "$MOUNT/COORDINATION.md" <<'TXT'
# Coordination
- Both agents must work ONLY inside this mounted path.
- Before editing a file, append a short “I’m editing <file>” note here.
- Use separate files when possible.
- If blocked on a lock, wait and do not force.
TXT
```

---

## 2) Terminal A — Codex

```
cd "$HOME/.local/state/gate/mounts/gate-host-direct"
codex
```

Paste as the first prompt:
```
You are Codex. Another agent (Gemini) is working in a second terminal.
Work ONLY inside this mounted path: $HOME/.local/state/gate/mounts/gate-host-direct
Read COORDINATION.md first. Announce any file you plan to edit by appending to COORDINATION.md.
Do not edit the real repo path. If a file is locked, wait and retry.
Goal: implement the feature we agree on together with Gemini.
```

---

## 3) Terminal B — Gemini

```
cd "$HOME/.local/state/gate/mounts/gate-host-direct"
gemini
```

Paste as the first prompt:
```
You are Gemini. Another agent (Codex) is working in a second terminal.
Work ONLY inside this mounted path: $HOME/.local/state/gate/mounts/gate-host-direct
Read COORDINATION.md first. Announce any file you plan to edit by appending to COORDINATION.md.
Do not edit the real repo path. If a file is locked, wait and retry.
Goal: implement the feature we agree on together with Codex.
```

---

## 4) Coordination rules (summary)

- Both CLIs must edit **only** inside the mount path.
- Always announce edits in `COORDINATION.md`.
- If a file is locked, **wait** — do not force.

---

## 5) Shutdown

```
/home/kajsfasdfnaf/Desktop/shared_concurrency_substrate/dist/gate down --vm-name gate-vm
```
