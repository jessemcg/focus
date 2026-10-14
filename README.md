# Focus

<img src="focus.svg" alt="Focus icon" width="96" align="left">

A Linux desktop app for reading and researching court records.
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
**Settings** in Focus. AI usage may incur provider charges.

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

## One neutral research method

Every new question and follow-up uses Focus's application-owned **focus-record-qa**
method, including cases formerly bound to a practice profile. There is no profile
choice or advanced profile option. **Settings** retains model/provider/reasoning,
appearance, speech input and launch controls.

Focus researches the question actually asked, using record-derived vocabulary and
verified original source pages. Prepared summaries, the overview and participant
metadata help navigation; they are not evidence for an answer. The method preserves
attribution, allegations versus findings, uncertainty, contemporaneous causal
verification, coverage limits and short clickable verbatim quotations. It does not
perform outside legal research or assume an appeal, specialty or legal doctrine.

Sessions pin the method and consumed bundle inputs. Changed inputs or method resources
require a new session; failed preflight preserves the displayed answer. Only **Save
Answer** writes to the per-case answer library. New saved answers use schema 3 and
record the Focus method separately from RecordPrep preparation provenance. Historical
schema-1/2 answers remain readable with their original metadata, without installed
profile snapshots. Older Focus releases may not read new schema-3 answers.

**No data migration:** private profiles, research selections, config, legacy prompts,
bundles and saved answers are not rewritten or deleted. Restart Focus, then explicitly
ask a new question to use the fixed method. No RecordPrep regeneration is required.
Retired `focus profiles …` commands report retirement rather than opening a case.

See the [fixed method and compatibility contract](docs/research-method.md),
[current validation](docs/research-method-validation.md), and
[historical profile-era evidence](docs/practice-profiles-validation.md).
Focus installation remains complete without Pi, login, models or paid verification.

## License

See [LICENSE](LICENSE).
