# Interactive Agent Setup

Use this document during install or reconfiguration.

Goal:

- let the agent ask a small number of focused setup questions
- let the agent edit `config.json` directly
- avoid dumping the entire config surface into one message
- make setup disappear after day 1 unless the user explicitly asks to revisit it

---

## Core rule

The agent should route by conversation, not by installer code.

1. inspect the user's goal
2. decide which option cluster matters
3. ask only the questions needed for that cluster
4. write or update `config.json`
5. summarize what was enabled

Once setup is complete, do not reopen setup during normal runs.

---

## Phase 0: Install location

Before asking setup questions, resolve the install location and ensure `paper-finder` is present.

Resolution rule:

1. Detect the host agent's normal skill/plugin directory if it has one.
2. Prefer an existing host-managed skill root.
3. Default: `~/.claude/tools/paper-finder`

Example:

```bash
if [ -d ~/.claude/tools/paper-finder/.git ]; then
  cd ~/.claude/tools/paper-finder && git pull --ff-only
else
  mkdir -p ~/.claude/tools
  git clone https://github.com/[user]/paper-finder ~/.claude/tools/paper-finder
fi
cd ~/.claude/tools/paper-finder
uv sync
```

---

## Pre-check: is config.json already valid?

Before asking setup questions, check if a valid `config.json` already exists.

**If config.json exists and is valid:**

> **paper-finder is already configured. What would you like to do?**
>
> 1. **Run with current config** -- skip setup
> 2. **Reconfigure** -- walk through setup again
> 3. **Update specific settings** -- change only named settings

If the user chooses 1, exit setup immediately.

---

## Phase 1: Foundation

### Step 1.1: Goal selection

> **What would you like paper-finder to do?**
>
> | | Option | What you get | What you miss |
> |---|---|---|---|
> | **A** | **Quick search** | OpenAlex keyword search + local HTML output | No profile-based ranking, no Zotero integration |
> | **B** | **Profile-based digest** (recommended) | Research profile filters papers, ranked by relevance | Requires Zotero for profile generation |

**If A:** set `semantic_search.enabled = false`, skip Zotero questions. Go to Step 1.2.
**If B:** continue to Step 1.2.

### Step 1.2: Add-ons

> **Would you like any of these enhancements?**
>
> | | Add-on | What it adds | Requires |
> |---|---|---|---|
> | **C** | **Semantic search** | Find nearest Zotero neighbors for each candidate | Embedding model |
> | **D** | **Push delivery** | Digest sent to email or Telegram automatically | SMTP or Telegram credentials |

Pick any combination.

---

## Phase 2: Zotero + Semantic Search (if C selected)

### Step 2.1: Zotero connection

> **Your Zotero library type?**
>
> 1. **Group** (`group`) -- shared team library
> 2. **Personal** (`user`) -- your own library

> **Your Zotero library ID?**
> For **group** libraries: go to [zotero.org/groups](https://www.zotero.org/groups/)
> For **personal** libraries: find it at [zotero.org/settings/keys](https://www.zotero.org/settings/keys)

> **Your Zotero API key?**
> Create one at the same page. Or set `ZOTERO_API_KEY` environment variable.

### Step 2.2: Semantic search backend

> **Which embedding backend?**
>
> | | Backend | Speed | Note |
> |---|---|---|---|
> | **1** | **Qwen** (recommended) | Fast, high quality | zh+en, needs API key |
> | **2** | **OpenAI API** | Highest quality | Paid |
> | **3** | **Gemini API** | Good quality | Free tier available |

> **How should items be synced into the semantic index?**
>
> | | Method | What it needs |
> |---|---|---|
> | **1** | **API sync** (recommended) | Zotero API credentials |
> | **2** | **Local sqlite** | Path to `zotero.sqlite` |

**If API sync:** run `paper-finder --action sync-index` after setup.
**If local sqlite:** ask for the path (usually `~/Zotero/zotero.sqlite`).

---

## Phase 3: Delivery Channel (if D selected)

### Step 3.1: Channel choice

> **How do you want to receive digests?**
>
> | | Channel | Best for |
> |---|---|---|
> | **1** | **Email** | Regular reading, team sharing |
> | **2** | **Telegram** | Mobile-first, quick triage |
> | **3** | **Both** | Email primary, Telegram backup |

### Step 3.2: Email details (if email selected)

Ask for: sender, recipients, SMTP server, port, user, password.

### Step 3.3: Telegram details (if Telegram selected)

Telegram requires environment variables:
- `TELEGRAM_BOT_TOKEN` -- create via [@BotFather](https://t.me/BotFather)
- `TELEGRAM_CHAT_ID` -- the target chat/channel ID

---

## Phase 4: Review Settings

> **Review enrichment settings** (defaults in parentheses):
>
> - How many top papers should the host agent enrich? (5)
> - How many papers in the final visible digest? (5)
>
> Press Enter to accept defaults.

---

## Phase 5: Confirm and Write

### Step 5.1: Show summary

```
paper-finder Configuration Summary
===================================

Foundation:     [Quick search / Profile-based digest]
Zotero:         [configured / not configured]
Semantic:       [qwen / openai / gemini / disabled]
Delivery:       [email / telegram / both / local only]

Config path:    ~/.claude/tools/paper-finder/config.json
```

### Step 5.2: Write config.json

Copy `config.example.json` as template, modify only affected fields.

### Step 5.3: Create directories

```bash
mkdir -p ~/.claude/tools/paper-finder/profiles
mkdir -p ~/.claude/tools/paper-finder/reports
cp profiles/research-interest.example.json \
  ~/.claude/tools/paper-finder/profiles/research-interest.json
```

---

## Phase 6: Post-setup Verification

Execute relevant commands:

| Choice | Command(s) |
|---|---|
| Sync index | `uv run --project ~/.claude/tools/paper-finder paper-finder --action sync-index` |

### Smoke check

```bash
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --action search --query "test" --source nber --top 3
```

---

## Reference: Config Structure

```json
{
  "profile_path": "~/.claude/tools/paper-finder/profiles/research-interest.json",
  "output_root": "/path/to/output",
  "review_generation": {
    "agent_top_n": 5,
    "final_top_n": 5
  },
  "delivery": {
    "primary_channel": "email",
    "email": {
      "send_enabled": false,
      "sender": "",
      "recipients": [],
      "smtp_server": "",
      "smtp_port": 465,
      "smtp_user": "",
      "smtp_pass": ""
    }
  },
  "zotero": {
    "library_id": "",
    "api_key": "",
    "library_type": "user"
  },
  "semantic_search": {
    "enabled": true,
    "zotero_db_path": "",
    "embedding_model": "openai",
    "embedding_config": {
      "model_name": "text-embedding-v4",
      "base_url": "https://api.openai.com/v1",
      "api_key": ""
    }
  }
}
```

---

## Reference: CLI Commands

```bash
# Search papers
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --action search --query "your query" --source nber --top 10

# Run digest
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --action digest-all --config ~/.claude/tools/paper-finder/config.json

# Sync Zotero index
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --action sync-index --config ~/.claude/tools/paper-finder/config.json
```
