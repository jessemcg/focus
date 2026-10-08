# Source-install validation — 2026-10-08

## Current rolling installer

At Jesse's request, the default command is now `curl -fsSL .../main/scripts/install-bootstrap.sh | bash`.
The bootstrap, downloaded installer/maintenance engine and fresh source clone follow
`main`, with no release pin. The installed commit is still recorded for diagnostics.
Repair/resume preserve existing source. The download-first command remains optional.
The final source installer receives `/dev/tty` as stdin so interactive subprocesses
work when the bootstrap itself arrives through a pipe.

Validation: **504 passed, 11 optional metrics integration skips** in a disposable
standalone checkout/environment. New tests cover advancing main, a different remote
default branch, receipt validation/repair, pipeline arguments/status, and the real
bootstrap through a private controlling terminal with synthetic local downloads.
Existing complete-file download-failure/cleanup tests still pass. No production
installation, package transaction, auth, paid request or private settings change.
Evidence: `/tmp/focus-latest-install-QKfm7KFU`. Shell syntax and whitespace checks pass.

## Earlier publication history (superseded version selection)

**Published and pinned at Jesse's explicit request**, after implementation
validation. Source commit `b89c62ef47ca6ae2c424ce31559c702bbf2a9394` is on
`origin/main`; a subsequent release-metadata commit pins it and adds the README
command. The unchanged `uv.lock` is committed. Unrelated Open Case UI edits and
staged README UI wording remain uncommitted/preserved.

At Jesse's request the README command was subsequently shortened to a complete-file
curl loader. Bootstrap commit `efd8e75f58139a6d7d92cab01dcf38370d12bd3a` publishes
the exact reviewed bootstrap with the same source pin; no app/runtime change.
The short command requires pre-installed curl (wget alternative available), while
`--inline` retains the prior no-downloader/self-contained provisioning form.

No local production installation/deployment, provider login, paid verification
or private configuration migration was performed. Publication is not a claim of
complete Ubuntu/Fedora release certification.

Coordinated public desktop templates/exporter live in the independent
`Desktop_Files` repository; its maintained launchers and unrelated pending changes
were not modified or deployed by this work. Template/exporter source was committed
separately as `98b0be989981f7a620bf6ccb2cff291bc59c649f`; that repository has no
remote. End users download Focus's exported copies, not Desktop_Files.

## Evidence

| Check | Result / boundary |
| --- | --- |
| Full Focus pytest suite | **511 passed** after short-loader refinement with optional metrics test infrastructure (initial source snapshot: 502, initial publication: 503); standalone latest metadata checkout without sibling metrics: **500 passed, 11 optional integration skips**. One existing GTK CSS deprecation warning; disposable environments, not production runtime |
| Lifecycle tests | Local synthetic Git clone/pin/named branch; install, failed verification, resume, repair preserving edits and ownership, partial-download removal; package/uv/auth operations mocked |
| Real installed Pi | Actual Focus record/follow-up extensions against a loopback-only synthetic SSE provider; structured `focus_record` Python helper, guarded read, submit tool and real artifact parser succeeded; no persisted session |
| Rejected provider | Loopback HTTP 500; one request, no automatic retry or settings save |
| Coding discovery | Installed Pi SDK's normal resource loader found no embedded Focus tools/prompt/skill in the developer checkout |
| Standalone uv helper | Actual external managed Python 3.13.13 and locked editable sync; excludes dev by default; source association/fingerprint checked; earlier work-desktop build was native-wheel-cache-assisted |
| Desktop | Real GTK application observed with Linux Computer Use using synthetic HOME/XDG/case/app ID; source title edit appeared after restart without reinstalling; previews closed |
| Templates / syntax | Deterministic cross-repository export check, native desktop-file validation in lifecycle tests, shell/Python syntax and Git whitespace checks |
| Safety contracts | Foreign command/desktop/icon refusal, unsafe roots/receipts, locks, changed owned files, environment inheritance/fingerprints, document protection, package availability/removal bounds, consent/cancellation and purge dry-run change reporting |

The full suite uses the documented absolute UvEnvironments helper with explicit
`--project /tmp/.../source --environment /tmp/.../environment` overrides. That
helper is only test infrastructure, **not a public installer dependency**.

## Local disposable image checks

QEMU/KVM already existed on the current work desktop. Two downloaded cloud images
were booted locally, with no persistent libvirt definition, SSH, port forwarding,
remote-host execution or host package installation:

- Ubuntu 24.04 amd64 (`noble-server-cloudimg-amd64.img`, current image dated
  20260926): GLib **2.80.0**, GTK **4.14.5**, Libadwaita **1.5.0**, GTK4 VTE 3.91.
- Fedora 44 x86_64 (`Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2`): GLib
  **2.88.3**, GTK **4.22.5**, Libadwaita **1.9.4**, GTK4 VTE 3.91.

Official native dependencies were installed inside the guests. Each used a new
synthetic user/private HOME, private uv, separately downloaded managed Python
3.13, external locked editable environment and native Cairo/PyGObject builds;
**no host wheel cache/runtime was copied**. Native capability checks succeeded and
**83 focused tests passed per guest** on final sources. Guests powered themselves
off. Source arrived on a read-only synthetic ISO, not through a shared production
folder. These are native dependency/runtime checks, not full desktop releases.

Image validation caught Fedora's separately packaged `cairo-gobject.h`: the native
adapter now explicitly requests **cairo-gobject-devel** alongside cairo-devel.
Python versions/dependency pins did not change. Fixture retries corrected stdout
capture/private umask and reran final code; earlier failures remain in local logs.

## Mocked or unperformed

- Ubuntu 26.04 application/GUI checks used the current host's existing libraries;
  a separate clean Ubuntu 26.04 guest was **not** tested.
- Fedora 43 and aarch64 native runtime/build/GUI tests were **not** performed.
  Release/base/architecture/immutable rejection policies have fixture coverage.
- No fresh graphical Ubuntu/Fedora desktop installation, package-manager/sudo
  cancellation against a real production machine, official Pi install/uninstall,
  persistent provider authentication or paid provider acceptance was performed.
  Package transactions and those third-party/auth flows are mocked in lifecycle
  tests; local image native provisioning does not certify every installer prompt.
- The public command is published. The retained `--inline` form round-trips to
  the reviewed bootstrap. The new short curl/wget loaders are tested with local
  synthetic downloads for failure/partial refusal, successful execution, argument
  forwarding, child exit status, mode-600 temporary files, paths containing spaces,
  quotes/metacharacters, cleanup, and mktemp failure. At that stage, published bootstrap bytes
  matched the template/source pin (superseded by latest-main delivery above). No production installer execution occurred.
- Shared package/Pi/Node cleanup is separately requested and consented; real shared
  cleanup was not performed. Credential/session deletion intentionally has no switch.

Do not describe these results as complete Ubuntu/Fedora release certification.

## Local artifacts

Disposable evidence is under `/tmp/focus-source-validation-nf63uwek`:
`full-tests.log`, `standalone-provision.log`, `gui-before.log`, `gui-after.log`, and
`images/{ubuntu24,fedora44}-acceptance-serial.log`; temporary image fixtures and
prior failure logs are retained there. Publication-candidate checks and original
index/diff recovery records are at
`~/.cache/focus-publication-x_mbi_xj/{tests.log,publication-tests.log,standalone-publication-tests.log,original.index,worktree.patch,index.patch}`.
Short-loader follow-up logs/index recovery are at
`~/.cache/focus-command-simplify-6c7nuif8/{tests.log,standalone-tests.log,index.patch,worktree.patch}`.
These paths are machine-local temporary artifacts, not synchronized deployment
or an enduring release attestation.
