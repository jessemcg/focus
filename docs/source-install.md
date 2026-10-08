# Source installation and removal

## Release status

This installer is **unpublished**. `scripts/install-release.json` deliberately has
no source ref. A separate, explicit release operation must publish the tested
commit and pin that full 40-character commit before an executable download command
is advertised. `main` is not a release pin. Local tests do not establish a
clean-machine Ubuntu/Fedora release certification. See [validation](source-install-validation.md).

## What is installed

Focus remains an ordinary editable Git checkout, normally `~/Focus`, on a named
`focus-install` branch. It is not a `.deb`, `.rpm`, Flatpak, AppImage or binary-only
application. Native dependencies still come from official apt/dnf repositories.

Initial platform policy: Ubuntu 24.04/26.04 or compatible mutable derivatives,
Fedora 43/44 or compatible conventional dnf derivatives; x86_64 and aarch64.
Capabilities, not distro names alone, are required: GLib/girepository 2.80+, GTK
4.12+, Libadwaita 1.4+, GTK4 VTE 3.91 and the APIs used by Focus. Immutable
rpm-ostree desktops are rejected, without layering packages, rebooting, disabling
SELinux, adding PPAs or upgrading the OS. Unsupported hosts stop before app changes.

Unavoidable prerequisites: Bash, working system package manager, network and
privilege authorization when dependencies are missing. Missing bootstrap Python or
downloader is explained and separately authorized. Native transactions are previewed,
keep package-manager progress visible and require sudo authorization; unavailable
repository components must be enabled by the user, never silently.

| Component | Default |
| --- | --- |
| Source | `~/Focus` (custom `--source-dir`) |
| Environment | `~/.local/share/uv/project-envs/Focus` |
| Focus-managed Python | `~/.local/share/uv/project-python/Focus` |
| Private uv when necessary | `~/.local/share/focus/tools` |
| Settings | `$XDG_CONFIG_HOME/focus` or `~/.config/focus` |
| Private receipt/stage log | `$XDG_STATE_HOME/focus` or `~/.local/state/focus` |
| Durable maintenance | `$XDG_DATA_HOME/focus/installer` or `~/.local/share/focus/installer` |
| Owned cache | `$XDG_CACHE_HOME/focus` or `~/.cache/focus` |
| Commands | `~/.local/bin/focus`, `~/.local/bin/focus-uninstall` |
| Desktop ID | `com.mcglaw.Focus` |

Runtime roots must be machine-local below HOME, non-symlinked, nonoverlapping,
user-owned and not writable by other users/groups. Custom source directories can
be elsewhere but cannot contain runtime ownership roots. Existing foreign command,
environment, desktop-entry or icon collisions stop installation. In particular,
the public installer will **not take over Jesse's maintained environment/launchers**.
Do not work around a collision by deleting private configuration.

## Terminal workflow (after explicit publication)

Use a published checkout as the installer payload, with a **new, nonexistent**
source destination. An existing unowned checkout is not silently adopted; choose
another destination. `--resume`/`--repair` apply only to a receipt-owned install.

```sh
./install.sh --dry-run
./install.sh
# Or choose a new empty source destination:
./install.sh --source-dir "$HOME/Applications/Focus source"
```

The installer prints eleven numbered stages and `[CHECK]`, `[OK]`, `[ACTION]`,
`[WAIT]`, `[WARN]`, `[FAIL]` markers. Output is ASCII/no-color. It prints commands
and reasons before running them; prompts read the controlling terminal, never the
download stream. No shell tracing or authentication transcripts are recorded.

### Download-command publication template — NOT a current release command

The reviewed outer bootstrap is `scripts/download-bootstrap.sh.in`. After a
separately authorized release operation pins/publishes a tested full commit in
`scripts/install-release.json`, a maintainer can render both equivalent forms:

```sh
python3 scripts/print-install-command.py --expanded
python3 scripts/print-install-command.py
```

These commands only print instructions; they never publish/download/install. Both
currently refuse to print an executable command because the release is unpinned.
A pin alone is not proof that a commit has actually been published/tested.

The rendered outer command checks supported mutable hosts, uses an existing curl
or wget, and, if neither exists, visibly previews/authorizes official curl
provisioning and carries the successful package delta in
`FOCUS_BOOTSTRAP_PACKAGES`. It downloads the complete pinned script into a unique
private temporary directory, stops on download failure, offers inspection, asks
before execution, reads approvals from `/dev/tty`, and cleans its download files.
The one-line form uses Bash ANSI-C quoting of that same readable script; it is
not `curl | bash`. Any packages introduced before a later download failure are
reported and retained rather than silently removed. The checkout bootstrap can
likewise offer missing prerequisites. A checksum fetched from the same source is
transport corruption detection, not independent authentication.

## Pi is required

Installation is incomplete until a synthetic live Agent verification succeeds.
There is **no `--skip-pi` or reader-only completion path**.

`focus setup-pi` preserves compatible Pi installations, including the current
managed `PI_CODING_AGENT_DIR/bin/pi` layout. Initially tested interface baseline:
Pi 1.1.0, Node 22.19+. A missing Pi offers its official installer (downloaded fully
before execution); its decisions remain visible. An incompatible existing Pi is
not replaced silently. No `sudo npm install` is used.

Use `focus setup-pi --login` to open Pi in a neutral temporary directory. Run
`/login` and complete the subscription/API-key authentication in Pi, then exit.
Pi owns its normal auth store; Focus never copies credentials. Focus's offline
bounded RPC query lists available models, offers numbered/search choices, and
lists supported reasoning levels. This selection does not change the global
coding-model default.

Verification uses the desktop launch environment, with no login-shell initialization
or terminal-only API-key variables. Use persistent Pi `/login` where necessary.
Then authorize **one small synthetic Agent verification run** (provider billing
may apply). It reads temporary text, uses the real guarded tools, explicitly
loaded extensions and answer-artifact parser, disables retry/compaction, has a
90-second deadline and uses no real documents. Provider/model/auth checks alone
are not proof of accepted requests. Failure/cancel/declined consent retains an
incomplete receipt; retries are explicit, not automatic. Focus saves executable,
provider, model and reasoning only after this succeeds, using application-owned
settings-save functions. The maintenance shell does not rewrite private settings.

For already-authenticated scripted use, `setup-pi` accepts `--executable`,
`--provider`, `--model`, `--thinking`, and explicit `--approve-verification`.
Installation accepts provider/model/thinking/verification and `--login` too.
Without a controlling terminal it stops whenever another approval is needed;
there is no generic `--yes` that silently authorizes package changes or billing.

## Resume, repair and diagnostics

```sh
./install.sh --source-dir "$HOME/Focus" --resume
./install.sh --source-dir "$HOME/Focus" --repair
focus doctor
focus doctor --json
focus setup-pi --login
```

Every saved stage is rechecked. Repair does not fetch/reset/clean/stash user source,
update the lockfile or repair malformed settings by guessing. Native packages and
Pi auth changes are not automatically rolled back on failure. The receipt records
installation ID, phase, canonical paths, actual commit, dependency fingerprint,
tool versions, ownership hashes, created resources and package deltas, not case
content or credentials. An installed maintenance copy and uninstall command are
available even before native/source/auth stages finish. A concurrent operation is
locked out. Use the receipt/installed maintenance path printed on failure if source
has not downloaded yet; rerun the original installer with `--resume`.

`doctor` is read-only, offline except that user-supplied credential commands inside
Pi's own configuration can run. It never sends a model prompt or refreshes OAuth
credentials. It distinguishes current credential availability from a previous
successful synthetic verification and reports native/resources/editable binding.

## Launch, settings and development

Ordinary launch executes the verified external environment directly; it never
calls uv sync/run, installs dependencies, downloads Python or updates Git. The
public desktop entry uses the existing SVG, symbolic SVG and 512px PNG unchanged,
with the exact SVG path. It does not refresh MCGLAW current-case selection, add
keyboard mappings/favorites, create a desktop shortcut or install other projects.
Optional metrics are disabled by default. Jesse's maintained launcher/metrics
behavior remains separate and unchanged.

Public launchers explicitly set `FOCUS_CONFIG_DIR` to XDG Focus storage. Without
that override, existing checkout `config.json`/`.pi/settings.json` remain supported
when present; otherwise XDG storage is used. No migration or deletion occurs. New
profiles contain policy defaults without a hardcoded provider/model. Settings
shows the effective Pi storage path. Credentials always remain with Pi.

Embedded resources live in `focus/agent_resources`, not developer `.pi`. Only the
known prompt, skill, record extension, explicit follow-up bridge and selected
settings are staged into private disposable `.pi` workspaces. Coding agents opened
in the source checkout retain their normal coding prompt and tools. Embedded
sessions retain exactly `read,focus_record,submit_focus_answer`, guarded text-only
reads, answer artifacts, explicit follow-ups, cleanup and `--no-session`.

Edit source with any coding agent/editor; restart Focus to load changes. Keep Git:

```sh
cd "$HOME/Focus"
git status --short
git diff
scripts/focus-env check
scripts/focus-env run focus
scripts/focus-env sync --dev       # explicitly provision tests
scripts/focus-env run pytest -q
scripts/focus-env run python -m compileall -q focus scripts tests
# After intentionally editing dependency declarations/lockfile:
scripts/focus-env sync             # locked editable sync; excludes dev by default
```

`run` never provisions; `sync --dev` explicitly adds the dev dependency group.
Do not create `.venv` in the source. Private preferences/case materials are not
Git source. See the README's separate maintained-runtime instructions for Jesse's
sibling UvEnvironments workflow; that repository is not a public dependency.

## Removal

Close Focus and its embedded sessions yourself; the uninstaller never kills them.
Always preview:

```sh
focus-uninstall --dry-run
focus-uninstall
focus-uninstall --purge --dry-run
focus-uninstall --purge
# Separately requested shared-tool cleanup:
focus-uninstall --purge --cleanup-packages --cleanup-pi
```

Normal removal deletes owned commands, entry/icons, environment, private managed
Python/tools and disposable cache, preserving source, settings and maintenance
receipt/logs. Purge independently confirms installer-created source, owned Focus
settings, maintenance and receipt/log deletion by their exact paths. It reports
modified/untracked/ignored files, additional branches and commits not represented
by remote refs before source deletion. Pre-existing settings are not owned and are
retained. Changed installed files, malformed receipts, symlinked roots or foreign
ownership fail closed. Recursive deletion does not follow symlinks; recognized
record/document layouts block purge even if someone put a case inside the checkout.

Shared native packages remain by default. Optional cleanup considers only newly
introduced packages, previews removals, rejects transactions removing unrelated
packages, and never invokes autoremove. Unrecognized dnf removal tables fail closed.
Optional introduced Pi removal uses its official uninstaller; pre-existing Pi is
never removed. Introduced Node requires independent exact-path consent and a
no-active-Node-process check. Pi credentials/session stores are always retained by
these interfaces, even during tool cleanup. They may now serve unrelated coding
work. This version offers no credential-store deletion switch.

**Case bundles, source records, bookmarks and case-local saved answers are user
documents and are never removed by either removal mode.**
