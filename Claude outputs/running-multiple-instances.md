# Running Multiple Claude Desktop Instances (macOS & Windows)

Claude Desktop locks its login, sessions, and settings to a single data directory,
so it normally runs one account at a time. To run **two accounts side by side**,
you give a second instance its own data directory.

- **macOS:** two methods below (launcher, or cloned app bundle).
- **Windows:** one simple method — a shortcut with a `--user-data-dir` argument.
  Jump to [Windows](#windows).

> **Scope:** both methods *isolate* accounts (each runs independently, sandboxed).
> Neither carries a session *across* accounts — if one account hits its limit and
> you want to continue that exact conversation in the other, that's a different
> problem (see the CLI `claude --resume` flow, or `claude-session-bridge`).

---

## Method 1 — Extra data directory via a launcher (no cloning)

Keep the single installed `Claude.app`; launch a second instance pointed at its
own data directory.

### Setup

1. Create a data folder for the second account:
   ```bash
   mkdir -p "$HOME/Library/Application Support/Claude-Personal"
   ```
2. Make a launcher so you don't type the command each time. In **Script Editor**
   (Applications → Utilities), paste:
   ```applescript
   do shell script "open -n -a 'Claude' --args --user-data-dir=\"$HOME/Library/Application Support/Claude-Personal\""
   ```
   File → Save → **File Format: Application**, name it "Claude Personal", save to
   `/Applications`. Drag it to the Dock.
3. Launch it and log into the second account.

### Pros
- **No app duplication** — one installation.
- **Auto-updates**: when Claude updates, both instances get it automatically.
- **No code-signing issues** — the app bundle is never modified.
- Quick to set up and undo (just delete the launcher + data folder).

### Cons
- The **running** instances share the same Claude icon in the Dock, so they're
  hard to tell apart while open.
- Needs the launcher wrapper (a plain Dock pin can't carry the `--user-data-dir`
  argument).
- `claude://` deep links route to whichever instance launched last.

---

## Method 2 — Cloned app bundle with a unique identity

Duplicate the app so each account is a genuinely separate app with its own name
and icon.

### Setup

1. Duplicate the bundle:
   ```bash
   cp -R "/Applications/Claude.app" "/Applications/Claude Work.app"
   ```
2. Give it a unique identity so macOS treats it as a separate app:
   ```bash
   /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.anthropic.claude-work" \
     "/Applications/Claude Work.app/Contents/Info.plist"
   /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
     -f "/Applications/Claude Work.app"
   ```
   *(Editing `Info.plist` by hand in `nano` works too — change the
   `CFBundleIdentifier` string to something unique.)*
3. Create its data folder:
   ```bash
   mkdir -p "$HOME/Library/Application Support/Claude-Work"
   ```
4. Launch it with its own data directory (a Script Editor applet, saved as an
   Application, keeps it one-click):
   ```applescript
   do shell script "open -n -a 'Claude Work' --args --user-data-dir=\"$HOME/Library/Application Support/Claude-Work\""
   ```
### Setting a custom icon (so you can tell them apart)

1. Get an image — a `.png` (any square image works) or a proper `.icns`.
2. Open it in **Preview**, press **⌘A** (select all) then **⌘C** (copy).
3. In Finder, select **`/Applications/Claude Work.app`** and press **⌘I** (Get Info).
4. Click the small app icon in the **top-left** of the Info window (it gets a blue
   highlight), then press **⌘V** (paste). The Dock icon updates immediately.
5. To revert: select that top-left icon again and press **Delete**.

*(Tip: tint the standard Claude icon a different color for each profile — e.g. a
blue "Work" and a green "Personal" — so they're instantly distinguishable.)*

### Updating after a Claude update (important)

Because this is a **copy**, Claude's auto-update only updates the original
`/Applications/Claude.app`, not your clone. When you notice the versions differ
(or roughly monthly), refresh the clone:

```bash
# 1. Quit the cloned app if it's running
osascript -e 'quit app "Claude Work"' 2>/dev/null || true

# 2. Re-clone from the freshly-updated original (this replaces the old copy;
#    your data dir and login are untouched — they live in Claude-Work/, not here)
rm -rf "/Applications/Claude Work.app"
cp -R "/Applications/Claude.app" "/Applications/Claude Work.app"

# 3. Re-apply the unique identity + re-register
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.anthropic.claude-work" \
  "/Applications/Claude Work.app/Contents/Info.plist"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "/Applications/Claude Work.app"

# 4. Re-apply your custom icon (Get Info → paste), since the re-clone resets it.
```

Your account, sessions, and settings survive the update untouched — they're
stored in `~/Library/Application Support/Claude-Work/`, which the re-clone never
touches. Only the app bundle is replaced. *(The `setup-method2-clone.sh` script
does steps 2–3 for you; just re-run it, then re-paste the icon.)*

### Pros
- **Distinct Dock identity**: its own name and icon, so you always know which
  account you're clicking — even while running.
- Can be launched like any normal app.
- Cleanest experience for telling work vs personal apart.

### Cons
- **Breaks the code signature** — Gatekeeper may warn on first launch (right-click
  → Open to allow), and it isn't re-signed.
- **Does not auto-update** — when Claude updates the original, you must re-clone
  and re-patch this copy.
- More setup steps; two full app copies on disk.

---

## Shared caveats (both methods)

- Each instance bootstraps its **own Cowork VM** on first launch (~1–2 GB) and
  uses additional RAM — you're running two full apps.
- **MCP config does not sync** between profiles. If you use local MCP servers,
  populate `claude_desktop_config.json` in each data directory separately.
- **Usage limits are per account** — each instance draws from its own quota.
- These give you two accounts *running at once*; to move a session from one
  account to another (e.g., after a limit), use `claude --resume` (terminal) or
  `claude-session-bridge` (desktop).

## Which should you use? (macOS)

| Priority | Recommended |
|---|---|
| Simplicity + always up to date | **Method 1** (launcher) |
| Clearly distinct Dock icons/names | **Method 2** (cloned bundle) |
| Don't want to touch the app bundle / code-signing | **Method 1** |
| Willing to re-clone after Claude updates for a nicer UX | **Method 2** |

---

## Windows

Windows is simpler than macOS: shortcuts carry launch arguments natively, so you
**don't clone the app** — you just make one shortcut per profile, each pointed at
its own data directory. Do these steps once per account.

### Setup

1. **Find `Claude.exe`.** Right-click your existing Claude shortcut (Start menu or
   taskbar) → **Open file location** → right-click the app → **Properties** and
   copy the **Target**. It's usually:
   ```
   %LOCALAPPDATA%\Programs\Claude\Claude.exe
   ```
   *(If a shortcut points at a launcher stub, "Open file location" still lands you
   on the real folder — use whatever `Claude.exe` path you see.)*

2. **Create a data folder** for the profile. Press `Win + R`, type `%APPDATA%`,
   Enter, then make a new folder, e.g. `Claude-Work`.

3. **Create the shortcut.** Right-click the Desktop → **New → Shortcut**. For the
   location, paste (adjust the exe path if step 1 showed a different one):
   ```
   "%LOCALAPPDATA%\Programs\Claude\Claude.exe" --user-data-dir="%APPDATA%\Claude-Work"
   ```
   Click Next, name it **Claude Work**, Finish.

4. **Repeat** with a second folder + shortcut (e.g. `Claude-Personal` → "Claude
   Personal") for the other account.

5. **Launch each shortcut** and sign into the account you want it to hold. They run
   side by side, each on its own quota.

### Custom icon

Right-click the shortcut → **Properties → Change Icon → Browse** to a `.ico` file →
OK. (Convert a PNG to `.ico` with any online converter if needed.) Then right-click
→ **Pin to taskbar** / **Pin to Start** for one-click access.

### History persists

Just like macOS: close a shortcut and reopen it, and that profile's login and past
conversations come right back — everything lives in its `--user-data-dir` folder on
disk. Only pointing a shortcut at a *different* or empty folder gives a fresh
instance.

### Using the bridge with a Windows instance

`claude-session-bridge` supports these instances directly via `--app-support`:
```
python claude_session_bridge.py --app-support "%APPDATA%\Claude-Work" --diagnose
python claude_session_bridge.py --app-support "%APPDATA%\Claude-Work" --apply
```

### Windows caveats

- Each instance bootstraps its own VM (extra disk + RAM); MCP config
  (`claude_desktop_config.json`) is **per data folder**; quotas are **per account**.
- Fully quit an instance before running the bridge against it — quit from the
  system tray (right-click the tray icon → Quit) or via Task Manager, then reopen.
- These give you two accounts running **at once** (isolation), not session
  continuity across a limit — for that, use the bridge or `claude --resume`.

## Directory layout reference

**macOS**

| Scope | Primary profile | Secondary profile |
|---|---|---|
| App data / storage | `~/Library/Application Support/Claude/` | `~/Library/Application Support/Claude-Work/` (or `-Personal/`) |
| MCP config file | `…/Claude/claude_desktop_config.json` | `…/Claude-Work/claude_desktop_config.json` |
| App bundle | `/Applications/Claude.app` | `/Applications/Claude Work.app` (Method 2 only) |

**Windows**

| Scope | Primary profile | Secondary profile |
|---|---|---|
| App data / storage | `%APPDATA%\Claude\` | `%APPDATA%\Claude-Work\` (or `-Personal\`) |
| MCP config file | `%APPDATA%\Claude\claude_desktop_config.json` | `%APPDATA%\Claude-Work\claude_desktop_config.json` |
| Executable | `%LOCALAPPDATA%\Programs\Claude\Claude.exe` | *(same exe — the shortcut adds `--user-data-dir`)* |
