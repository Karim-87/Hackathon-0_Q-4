# Skill: File Processor

## Trigger
Run this skill when the user asks to "process files", "handle file drops", or "review dropped files". Also run when `process_inbox` identifies items of type `file_drop` in `/Needs_Action/files/`.

## Steps
1. List all files in `/Needs_Action/files/` — ignore `.gitkeep`
2. Identify file pairs: each drop creates two files:
   - `[timestamp]_[name].md` — metadata file with YAML frontmatter
   - `[timestamp]_[name].[ext]` — the actual dropped file
3. For each file pair, read the metadata `.md` file to get:
   - `original_name` — original filename
   - `size` / `size_bytes` — file size
   - `dropped_at` — when it was dropped
   - `status` — current status (should be `pending`)
4. Read the actual file contents to classify its type:
   - **Invoice** — contains payment amounts, billing info, due dates → route to `/Invoices/` and flag in `/Pending_Approval/`
   - **Contract/Agreement** — legal document → route to `/Pending_Approval/`
   - **Report/Data** — informational document → route to relevant `/Active_Projects/` folder
   - **Configuration/Code** — technical file → route to relevant project folder
   - **Test/Junk** — test data or irrelevant content → recommend moving to `/Done/` or `/Rejected/`
   - **Unknown** — cannot classify → flag for human review in `/Pending_Approval/`
5. For each classified file, determine the action:
   - If routing only (no delete, no payment) → auto-approve, move files to destination
   - If involves payment or financial data → create entry in `/Pending_Approval/` with `requires_approval: true`
   - If file should be deleted → require approval (never auto-delete)
6. Update the metadata `.md` frontmatter:
   - Set `status` to `processed`, `routed`, or `pending_approval`
   - Add `classified_as: [type]`
   - Add `routed_to: [destination folder]`
   - Add `processed_at: [current timestamp]`
7. Move the file pair to the destination folder
8. Report summary of all files processed with classifications and destinations
9. Trigger the `update_dashboard` skill

## Input
- `/Needs_Action/files/*` (metadata and actual files)
- `/Company_Handbook.md` (for autonomy rules on file operations)

## Output
- Files moved from `/Needs_Action/files/` to appropriate destination folders
- Updated metadata frontmatter on each processed file
- Summary report to user
- Updated `/Dashboard.md` (via update_dashboard skill)

## Rules
- File create and read operations are auto-approved
- File delete operations always require human approval — never auto-delete
- Any file containing financial data (invoices, payments, billing) must be flagged for approval
- Never move files without updating their metadata frontmatter
- Always preserve the original file — never modify the dropped file contents
- Log all file processing actions to `/Logs/`
- If a file contains sensitive data (passwords, API keys, credentials), flag it immediately and do not copy it to other locations
- Maximum safety: when uncertain about classification, default to `/Pending_Approval/` rather than auto-routing
