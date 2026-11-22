# Research Skills

A Research Skill is a reusable question you **run**. A Saved Answer is a result you **keep**. To enable Skills, choose a local **Research skills folder** under **Settings → Agent**, then **Save**. Clear the folder and save to turn the launcher off; this does not change the folder or its files.

## File format

Put visible UTF-8 Markdown files (up to 64 KiB each) in either layout:

```text
My research skills/
  inspection-timeline.md
  document-comparison/
    SKILL.md
```

Focus does not search deeper directories, follow links, or process scripts, includes, or attachments. An optional opening `---` block ending with `---` is ignored; it is not configuration. Focus uses the first Markdown heading as the menu title, or the filename (without `.md`) or containing folder as a fallback. You can search by title or relative path. If a file changes after the list opens, select it again from the refreshed list before starting.

Write the body as a question or request, with the sections and depth you want. For example:

```markdown
# Inspection Timeline

What does the record establish about the scheduling and outcome of the inspection?

## Scheduling
Explain when the inspection was proposed and who was notified.

## Outcome
Distinguish what witnesses reported from what was documented at the time.
Identify any gaps in the material examined without treating them as proof that
an event did not happen.
```

The contents are sent to the model as your question, not as a Pi extension or system prompt. Focus still limits evidence to the open record, uses the usual title and bottom-line subtitle, and links continuous verbatim phrases from original text pages. Don't use the skill itself, search snippets, or summaries as quotable evidence. Requested sections can be longer than an ordinary short answer.

## Models and answers

Skills inherit the ordinary Agent Q&A model and reasoning by default. Settings can select one exact authenticated model for all skills, with its own optional reasoning effort. Follow-ups stay in that conversation. Setting a model in the Markdown file has no effect.

Opening or searching **Skills** does not send a question. Activating a result starts a new conversation; Focus asks first if the current session may still be working or has an unsaved live answer. **Save Answer** explicitly keeps the displayed result in the case library. Saved answers and their source links do not depend on the skill file remaining available.
