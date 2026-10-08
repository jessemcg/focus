<img src="focus.svg" alt="Focus icon" width="96">

# Focus

A Linux desktop app for reading and researching appellate records.

- Browse transcripts and page images with bookmarks, search, and citation navigation.
- Read hearing, report, and minute-order summaries alongside the record.
- Ask AI questions, follow up, and jump from quoted text back to the source.
- Save answers with each case for later reference.

## Install

For Ubuntu **24.04/26.04** and Fedora **43/44** desktops (x86_64/aarch64).
Immutable distributions are not supported.

With `curl` installed, run as your normal user—not with sudo:

```bash
curl -fsSL https://raw.githubusercontent.com/jessemcg/focus/main/scripts/install-bootstrap.sh | bash
```

Installs the latest `main` code into `~/Focus`. The installer asks before installing
missing dependencies and guides you through Pi authentication, model selection,
and a required AI verification run. Provider charges may apply.

[Installation options, troubleshooting, and removal →](docs/source-install.md)

## Get started

Launch **Focus** from your applications menu or run `focus`. Choose **Open Case…**
from the menu and select a RecordPrep case bundle.

Basic browsing needs a `text_pages` folder; source-linked AI answers also need
`artifacts/source_map.json`. Summaries and page images appear when included.

Use **Agent Q&A** to ask questions and follow up. AI questions send selected record
text to your chosen model provider; check its confidentiality terms before using
sensitive records. Verify answers against the source.

## License

See [LICENSE](LICENSE).
