# Source-install validation — 2026-10-08

## Delivery status

Implemented, **not published or deployed**. `scripts/install-release.json` retains
`source_ref: null`; the command renderer refuses an executable download command.
A separately authorized release must publish/pin the tested source. No production
Git commit/push, real installer run, provider login, paid verification or private
configuration migration was performed. Existing user edits and staged README
changes were preserved. The unchanged `uv.lock` is now tracked without committing.

Coordinated public desktop templates/exporter live in the independent
`Desktop_Files` repository; its maintained launchers and unrelated pending changes
were not modified or deployed by this work. Future commits stay separate.

## Evidence

| Check | Result / boundary |
| --- | --- |
| Full Focus pytest suite | **501 passed**, one existing GTK CSS deprecation warning; disposable source/environment, not production runtime |
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
- No public download one-liner was executed/published. A failed-download fixture
  proves a partial script is not executed; an unpinned manifest blocks generation.
- Shared package/Pi/Node cleanup is separately requested and consented; real shared
  cleanup was not performed. Credential/session deletion intentionally has no switch.

Do not describe these results as complete Ubuntu/Fedora release certification.

## Local artifacts

Disposable evidence is under `/tmp/focus-source-validation-nf63uwek`:
`full-tests.log`, `standalone-provision.log`, `gui-before.log`, `gui-after.log`, and
`images/{ubuntu24,fedora44}-acceptance-serial.log`; temporary image fixtures and
prior failure logs are retained there. These paths are machine-local temporary
artifacts, not synchronized deployment or an enduring release attestation.
