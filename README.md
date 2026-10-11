# Focus

<img src="focus.svg" alt="Focus icon" width="96" align="left">

A Linux desktop app for reading and researching appellate records.
Reads record bundles prepared by [RecordPrep](https://github.com/jessemcg/record-prep)
and uses the [Pi coding agent](https://github.com/earendil-works/pi/tree/main/packages/coding-agent)
for AI questions.

- Browse transcripts and page images with bookmarks, search, and citation navigation.
- Read hearing, report, and minute-order summaries alongside the record.
- Ask AI questions, follow up, and jump from quoted text back to the source.
- Save answers with each case for later reference.

## Install

Focus is intentionally distributed as source rather than a Flatpak or Debian package,
so you can easily adapt the code to your needs with the coding agent of your choice.

The installer has been tested with Ubuntu and Fedora.

With `curl` installed, run as your normal user—not with sudo:

```bash
curl -fsSL https://raw.githubusercontent.com/jessemcg/focus/main/scripts/install-bootstrap.sh | bash
```

Installs the latest `main` code into `~/Focus` and asks before installing missing
dependencies. Focus installs fully without Pi or an AI account.

After confirming Focus is installed, setup offers to install Pi if it is missing.
Press Enter to continue with Pi or type `skip` to finish. For AI features, open Pi
and use `/login` to enter an API key or sign in. Then select an available model in
**Focus Settings**. AI usage may incur provider charges.

[Installation options, troubleshooting, and removal →](docs/source-install.md)

## Resume or uninstall

**Resume an interrupted Focus installation:**

```bash
curl -fsSL https://raw.githubusercontent.com/jessemcg/focus/main/scripts/install-bootstrap.sh | bash -s -- --resume
```

**Uninstall Focus:** close Focus, then run:

```bash
"$HOME/.local/bin/focus-uninstall"
```

This keeps your source checkout, settings, case documents and Pi installation.
See [removal options](docs/source-install.md#removal) for optional cleanup.

**Uninstall Pi:** run its official installer and choose **Uninstall Pi**:

```bash
curl -fsSL https://pi.dev/install.sh | sh
```

Pi may also serve other apps; removing it disables their Pi features, including
Focus's AI questions. Pi credentials and saved sessions are retained.

## Get started

Launch **Focus** from your applications menu or run `focus`. Choose **Open Case…**
from the menu and select a RecordPrep case bundle.

Basic browsing needs a `text_pages` folder; source-linked AI answers also need
`artifacts/source_map.json`. Summaries and page images appear when included.

Use **Agent Q&A** to ask questions and follow up. AI questions send selected record
text to your chosen model provider; check its confidentiality terms before using
sensitive records. Verify answers against the source.

## Practice profiles

Focus includes **General Court Record** and **California Juvenile Dependency**
research profiles. Open **Research** in the header or **Practice Profiles** in
Settings to create, duplicate, edit, preview, export, register and select guidance
without editing JSON. Bundled profiles are read-only; your accepted revisions and
new-case default belong to Focus, independently of RecordPrep.

Before a case's first Q&A, explicitly confirm a profile or **Legacy**. Opening a
case does not change it. Live sessions pin their instructions and source inputs;
end the session before changing guidance. Saved answers show their own research
profile separately from the preparation actually consumed. Missing instructions
block new profile-dependent research, not browsing or reading old answers.

Use identity export/import to author a corresponding specialty in RecordPrep;
identity sharing never imports instructions or changes either app's default.
Private legacy-guidance copying is explicit and requires privacy review. See the
[GUI guide and contract](docs/practice-profiles.md) and
[validation evidence and limitations](docs/practice-profiles-validation.md).
Focus installation remains complete without Pi, login, models or paid verification.

## License

See [LICENSE](LICENSE).
