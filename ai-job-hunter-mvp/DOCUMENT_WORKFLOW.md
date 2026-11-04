# CV, cover-letter and application workflow

## Upload, tailor and export

**My profile** stores your account's verified master CV and explicit candidate facts in SQLite. PDF, DOCX, TXT and Markdown extraction is local, limited to 5 MB. Scanned PDFs need OCR elsewhere; extraction is not a visual-layout audit. No skills are globally blacklisted. Facts are preserved; missing qualifications must not be invented.

**CV studio** accepts both pasted job descriptions and vacancies handed off from Job Explorer. A pasted URL identifies the vacancy; it is not a general-purpose scraper. Analyze keyword overlap, create the local skill-focus draft, or use Claude. Edit the CV, cover letter and screening answers; check and confirm the exact documents before export/save.

DOCX and PDF exports use a selectable-text, single-column A4 template with standard section headings. They do not recreate the uploaded layout. Unsupported PDF glyphs produce a useful error; choose DOCX when needed. Structural and keyword warnings are guidance, not a guarantee of ATS acceptance or factual accuracy.

## Claude options

Your existing Claude subscription works with **Download prompt for Claude**, **Open Claude** and pasting the result back into the editors. Downloading a prompt does not send the CV anywhere. Uploading/pasting it into Claude is your action.

Optional API generation uses a private API key and model configured in **Settings**. Keys are encrypted outside the repository and never returned by the API. A Claude subscription is separate from API billing. API generation sends the source CV and job description to Anthropic only after consent. Shared backend `ANTHROPIC_API_KEY` / `CLAUDE_MODEL` variables are also supported; the UI identifies installation-wide fallback configuration. Generated documents remain unverified until reviewed.

## Exact application approval

Saving documents creates a pending application in the local account database. Duplicate vacancy URLs are blocked. In **Approval center** or **Applications**, inspect the original job, source CV, tailored CV, cover letter, screening answers and version history. Downloads are generated from the saved snapshot.

Editing documents, delivery metadata or the bound source creates a new immutable version and invalidates prior approval and queued work. Delivery binds the sender, recipient, attachment format, eligibility confirmation and document hash. Approval and queueing are separate actions. Sending is blocked during uncertain/in-flight attempts to prevent duplicate delivery.

The optional automatic policy can authorize exact locally produced, source-preserving snapshots under saved restrictions. Claude-generated documents and jobs needing additional documents or screening review require human review. Automatic policy authorization is explicitly audited; it is never represented as a human approval.

## Sending and outcomes

Connect Gmail in **Settings**. Review-first email sending requires an exact approved version and confirmed application address. The queue attaches both CV and letter in the selected format, includes saved screening answers, records actual attachment hashes and stores Gmail's Message-ID and acceptance timestamp only on SMTP acknowledgement.

If the network fails during transfer, the result is **uncertain**. Inspect Gmail Sent before resolving it; the agent does not blindly retry. Known pre-send failures can be retried. Canceling queued work prevents that queued send. A weekly reservation cap includes in-flight and uncertain attempts.

Reply tracking reads INBOX without marking mail read, inspects headers, and retrieves message text only for replies uniquely linked to recorded sent Message-IDs. Detected interview/rejection/offer labels are heuristics; inspect the message. Other replies remain for review. Unrelated mail bodies are not imported. Website-form submissions can be recorded as **User reported** with evidence and exact-document confirmation; these records prevent a duplicate email send but are not SMTP receipts.

See [READY_TO_USE.md](READY_TO_USE.md) for Gmail setup, operational limits and validation.
