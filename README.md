# Focus

<img src="focus.svg" alt="Focus icon" width="128" align="right">

A Linux desktop app for reading and researching court records.
Reads record bundles prepared by [RecordPrep](https://github.com/jessemcg/record-prep)
and uses the [Pi coding agent](https://github.com/earendil-works/pi/tree/main/packages/coding-agent)
for AI questions.

- Browse transcripts and page images with bookmarks, search, and citation navigation.
- Read hearing, report, motion-paper, and minute-order summaries alongside the record.
- Ask AI questions, follow up, and jump from quoted text back to the source.
- Save answers with each case for later reference.

## Install

Focus is intentionally distributed as source rather than a Flatpak or Debian package
so that it can be easily modified by a coding agent.
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

[Installation options, troubleshooting, and removal](docs/source-install.md)

## Resume or uninstall

### Resume installation

```bash
curl -fsSL https://raw.githubusercontent.com/jessemcg/focus/main/scripts/install-bootstrap.sh | bash -s -- --resume
```

### Uninstall Focus

Close Focus, then run:

```bash
"$HOME/.local/bin/focus-uninstall"
```

This keeps your source checkout, settings, case documents and Pi installation.
See [removal options](docs/source-install.md#removal) for optional cleanup.

### Uninstall Pi

Run its official installer and choose **Uninstall Pi**:

```bash
curl -fsSL https://pi.dev/install.sh | sh
```

Pi may also serve other apps; removing it disables their Pi features, including
Focus's AI questions. Pi credentials and saved sessions are retained.

## Get started

Launch **Focus** from your applications menu or run `focus`. Click the **Open Case…**
folder icon at the top left and select a RecordPrep case bundle.

Basic browsing needs a `text_pages/` folder; source-linked AI answers also need
`artifacts/source_map.json`. Summaries and page images appear when included.
When available, select **Case Overview** in **Case Tools** to read it alongside the record.

In the right-side hover area, scroll to navigate, left-click for next, or
right-click for back.
On an enlarged page image, left-click the image to go forward or right-click it to go back.

The **Answer / Session** controls lead directly into the answer or session view,
without a metadata line. Research and save metadata remain stored with answers.
Click the PDF icon beside **Saved** or in a summary’s toolbar to open its PDF, then use your PDF viewer’s **Print** or **Save a Copy** action.

Use **Agent Q&A** to ask questions and follow up. AI questions send selected record
text to your chosen model provider; check its confidentiality terms before using
sensitive records. Verify answers against the source.

For reusable questions, set a **Research skills folder** in **Settings → Agent**,
then pick a skill beside **New question**. Skills start research; **Save Answer**
keeps the result. See the [Research Skills file guide](docs/research-skills.md).

## License

See [LICENSE](LICENSE).

**Recommended Agent model:** the latest DeepSeek Flash model via the Fireworks API.
