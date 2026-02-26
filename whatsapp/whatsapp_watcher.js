/**
 * WhatsApp Watcher — AI Employee
 *
 * Monitors incoming WhatsApp messages and creates action files in the vault
 * following the same pattern as gmail_watcher.py:
 *
 *   Message received → /Needs_Action/messages/<timestamp>_<sender>.md
 *
 * Features:
 *   - Auto-reconnect with exponential backoff (5s → 10s → 30s → 60s max)
 *   - Startup scan: unread messages from last 24 hours
 *   - Group messages: only processed when owner name is mentioned or keyword matched
 *   - Media: downloaded to /Needs_Action/media/ with .md reference file
 *   - Rate limit: max 100 messages processed per hour
 *   - Logging: /Logs/whatsapp/ per-day files
 *   - Session expired alert: /Needs_Action/WHATSAPP_SESSION_EXPIRED.md
 *
 * Usage:
 *   node whatsapp_watcher.js
 *   node whatsapp_watcher.js --dry-run   # Log only, do not write files
 */

'use strict';

const fs   = require('fs');
const path = require('path');
const { Client, LocalAuth, MessageMedia, MessageTypes } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

// ── Config ────────────────────────────────────────────────────────────────────

require('dotenv').config({ path: path.join(__dirname, '../AI_Employee_Vault/.env') });

const VAULT_PATH   = process.env.VAULT_PATH || path.join(__dirname, '../AI_Employee_Vault');
const DRY_RUN      = process.env.DRY_RUN !== 'false';
const SESSION_DIR  = path.join(__dirname, '.wwebjs_auth');
const LOG_DIR      = path.join(VAULT_PATH, 'Logs', 'whatsapp');
const MESSAGES_DIR = path.join(VAULT_PATH, 'Needs_Action', 'messages');
const MEDIA_DIR    = path.join(VAULT_PATH, 'Needs_Action', 'media');

const MAX_MESSAGES_PER_HOUR = 100;
const BACKOFF_SEQUENCE      = [5000, 10000, 30000, 60000]; // ms

// Keywords that trigger processing in any chat (including groups when not mentioned)
const TRIGGER_KEYWORDS = [
    'urgent', 'asap', 'invoice', 'payment', 'help', 'pricing',
    'deadline', 'emergency', 'critical', 'important',
];

const DRY_RUN_LABEL = DRY_RUN ? '[DRY-RUN] ' : '';

// ── Ensure Directories ────────────────────────────────────────────────────────

for (const dir of [LOG_DIR, MESSAGES_DIR, MEDIA_DIR]) {
    fs.mkdirSync(dir, { recursive: true });
}

// ── Logger ────────────────────────────────────────────────────────────────────

function log(level, message) {
    const now     = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    const timeStr = now.toISOString().slice(11, 19);
    const line    = `${dateStr} ${timeStr} | WhatsAppWatcher | ${level.toUpperCase()} | ${message}\n`;

    process.stdout.write(line);

    const logFile = path.join(LOG_DIR, `${dateStr}.log`);
    try {
        fs.appendFileSync(logFile, line, 'utf8');
    } catch (_) { /* non-fatal */ }
}

// ── Rate Limiter ──────────────────────────────────────────────────────────────

const _messageTimestamps = [];

function isRateLimited() {
    const now    = Date.now();
    const cutoff = now - 3600_000; // 1 hour window
    while (_messageTimestamps.length && _messageTimestamps[0] < cutoff) {
        _messageTimestamps.shift();
    }
    if (_messageTimestamps.length >= MAX_MESSAGES_PER_HOUR) {
        log('warn', `Rate limit reached: ${MAX_MESSAGES_PER_HOUR} messages/hour`);
        return true;
    }
    _messageTimestamps.push(now);
    return false;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function sanitizeFilename(str) {
    return str.replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, '_').slice(0, 50);
}

function timestampPrefix() {
    return new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
}

function isoNow() {
    return new Date().toISOString().replace('T', ' ').slice(0, 19) + 'Z';
}

function detectPriority(body) {
    const low   = body.toLowerCase();
    if (/urgent|asap|emergency|critical|immediately/.test(low)) return 'high';
    if (/invoice|payment|billing|deadline/.test(low))           return 'medium';
    return 'low';
}

function suggestedActions(body, isNewContact, isGroup) {
    const low   = body.toLowerCase();
    const lines = [];
    if (/invoice|payment|billing/.test(low))  lines.push('- [ ] Create invoice (financial workflow)');
    if (/meeting|call|schedule|zoom/.test(low)) lines.push('- [ ] Schedule meeting / send calendar invite');
    if (isNewContact)   lines.push('- [ ] Verify contact before replying (new contact — requires approval)');
    if (isGroup)        lines.push('- [ ] Reply in group (mentioned you)');
    lines.push('- [ ] Reply to sender');
    lines.push('- [ ] Forward to relevant party');
    lines.push('- [ ] Archive after processing');
    return lines.join('\n');
}

// ── Action File Writer ────────────────────────────────────────────────────────

function writeMessageFile(data) {
    const {
        sender, senderName, chatName, body, timestamp,
        isGroup, isNewContact, priority, mediaPath, messageId,
    } = data;

    const safeSender  = sanitizeFilename(senderName || sender);
    const prefix      = timestampPrefix();
    const filename    = `${prefix}_${safeSender}.md`;
    const filepath    = path.join(MESSAGES_DIR, filename);

    const mediaLine = mediaPath
        ? `**Media**: [[${path.basename(mediaPath)}]]\n`
        : '';

    const content = [
        '---',
        'type: whatsapp_message',
        `from: "${senderName || sender}"`,
        `phone: "${sender}"`,
        `chat: "${chatName}"`,
        `received_at: ${new Date(timestamp * 1000).toISOString()}`,
        `priority: ${priority}`,
        `is_group: ${isGroup}`,
        `is_new_contact: ${isNewContact}`,
        `status: pending`,
        `message_id: "${messageId}"`,
        '---',
        '',
        `# WhatsApp: ${senderName || sender}${isGroup ? ` (in ${chatName})` : ''}`,
        '',
        `**From**: ${senderName || sender} (${sender})`,
        `**Chat**: ${chatName}`,
        `**Received**: ${new Date(timestamp * 1000).toISOString()}`,
        `**Priority**: ${priority}`,
        `**New Contact**: ${isNewContact ? 'Yes' : 'No'}`,
        mediaLine,
        '## Message',
        '',
        body || '_(No text — see media file)_',
        '',
        '## Suggested Actions',
        '',
        suggestedActions(body || '', isNewContact, isGroup),
        '',
        '## Action Required',
        `Review this message and decide on next steps.`,
        isNewContact
            ? '**Note**: New contact — replying requires approval (Company Handbook).'
            : '',
    ].join('\n');

    if (DRY_RUN) {
        log('info', `${DRY_RUN_LABEL}Would write: ${filepath}`);
    } else {
        fs.writeFileSync(filepath, content, 'utf8');
        log('info', `Action file created: Needs_Action/messages/${filename}`);
    }

    return filepath;
}

// ── Session Expired Alert ─────────────────────────────────────────────────────

function createSessionExpiredAlert() {
    const alertPath = path.join(VAULT_PATH, 'Needs_Action', 'WHATSAPP_SESSION_EXPIRED.md');
    const content = [
        '---',
        'type: alert',
        'severity: high',
        `created: ${isoNow()}`,
        'status: pending',
        '---',
        '',
        '# Alert: WhatsApp Session Expired',
        '',
        '**Action required**: The WhatsApp session has expired or been invalidated.',
        '',
        '## Steps to fix',
        '1. Stop the WhatsApp watcher: `Ctrl+C`',
        '2. Delete session folder: `rm -rf D:/Hackathon-0\\ Q4/ai-employee-project/.wwebjs_auth/`',
        '3. Restart watcher: `node whatsapp_watcher.js`',
        '4. Scan the new QR code with your phone.',
        '',
        '*Generated by WhatsAppWatcher*',
    ].join('\n');

    if (!DRY_RUN) fs.writeFileSync(alertPath, content, 'utf8');
    log('error', 'Session expired — alert created in Needs_Action/');
}

// ── Message Processor ─────────────────────────────────────────────────────────

async function processMessage(msg, client) {
    if (isRateLimited()) return;

    const chat       = await msg.getChat();
    const contact    = await msg.getContact();
    const isGroup    = chat.isGroup;
    const body       = msg.body || '';
    const senderName = contact.pushname || contact.name || '';
    const sender     = contact.number || msg.from.replace(/@.*/, '');
    const chatName   = chat.name || senderName;

    // Group filter: only process when mentioned or keyword matched
    if (isGroup) {
        const myNumber  = client.info?.wid?.user;
        const mentioned = msg.mentionedIds?.some(id => id.includes(myNumber));
        const hasKw     = TRIGGER_KEYWORDS.some(kw => body.toLowerCase().includes(kw));
        if (!mentioned && !hasKw) {
            log('debug', `Group message from ${chatName} skipped (no mention/keyword)`);
            return;
        }
    }

    const priority     = detectPriority(body);
    const isNewContact = !contact.isMyContact;

    // Handle media
    let mediaPath = null;
    if (msg.hasMedia) {
        try {
            const media = await msg.downloadMedia();
            if (media) {
                const ext       = media.mimetype.split('/')[1]?.split(';')[0] || 'bin';
                const mediaName = `${timestampPrefix()}_${sanitizeFilename(senderName || sender)}.${ext}`;
                mediaPath       = path.join(MEDIA_DIR, mediaName);
                if (!DRY_RUN) {
                    fs.writeFileSync(mediaPath, Buffer.from(media.data, 'base64'));
                    log('info', `Media saved: Needs_Action/media/${mediaName}`);
                } else {
                    log('info', `${DRY_RUN_LABEL}Would save media: ${mediaPath}`);
                }
            }
        } catch (e) {
            log('warn', `Failed to download media from ${sender}: ${e.message}`);
        }
    }

    writeMessageFile({
        sender, senderName, chatName, body,
        timestamp: msg.timestamp,
        isGroup, isNewContact, priority,
        mediaPath, messageId: msg.id.id,
    });

    log('info', `Processed message from ${senderName || sender} | priority=${priority} | group=${isGroup}`);
}

// ── Startup: Check Unread (Last 24h) ─────────────────────────────────────────

async function checkUnreadMessages(client) {
    log('info', 'Checking unread messages from last 24 hours...');
    const cutoff = Math.floor(Date.now() / 1000) - 86400;

    try {
        const chats = await client.getChats();
        let count   = 0;

        for (const chat of chats) {
            if (chat.unreadCount <= 0) continue;
            const messages = await chat.fetchMessages({ limit: 50 });

            for (const msg of messages) {
                if (msg.timestamp < cutoff) continue;
                if (msg.fromMe) continue;
                await processMessage(msg, client);
                count++;
            }
        }

        log('info', `Startup unread scan complete: ${count} message(s) processed`);
    } catch (e) {
        log('warn', `Startup unread scan failed: ${e.message}`);
    }
}

// ── WhatsApp Client ───────────────────────────────────────────────────────────

let reconnectAttempt = 0;

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: SESSION_DIR,
        clientId: 'ai-employee',
    }),
    puppeteer: {
        headless: 'shell',
        executablePath: 'C:\\Users\\User\\.cache\\puppeteer\\chrome\\win64-145.0.7632.77\\chrome-win64\\chrome.exe',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-automation',
        ],
    },
});

client.on('qr', (qr) => {
    log('info', 'QR code ready — scan with WhatsApp on your phone');
    qrcode.generate(qr, { small: true });
});

client.on('loading_screen', (percent, message) => {
    log('info', `Loading: ${percent}% — ${message}`);
});

client.on('authenticated', () => {
    log('info', 'Authenticated. Session saved.');
    reconnectAttempt = 0;
});

client.on('auth_failure', (msg) => {
    log('error', `Auth failure: ${msg}`);
    createSessionExpiredAlert();
    process.exit(1);
});

client.on('ready', async () => {
    const info = client.info;
    log('info', `Connected: ${info.pushname} (${info.wid.user}) on ${info.platform}`);
    log('info', `DRY_RUN=${DRY_RUN} | VAULT=${VAULT_PATH}`);
    reconnectAttempt = 0;
    await checkUnreadMessages(client);
});

client.on('message', async (msg) => {
    if (msg.fromMe) return;
    await processMessage(msg, client);
});

client.on('disconnected', (reason) => {
    log('warn', `Disconnected: ${reason}`);

    if (reason === 'LOGOUT') {
        createSessionExpiredAlert();
        process.exit(1);
    }

    // Exponential backoff reconnect
    const delay = BACKOFF_SEQUENCE[Math.min(reconnectAttempt, BACKOFF_SEQUENCE.length - 1)];
    reconnectAttempt++;
    log('info', `Reconnecting in ${delay / 1000}s (attempt ${reconnectAttempt})...`);
    setTimeout(() => client.initialize(), delay);
});

// ── Graceful Shutdown ─────────────────────────────────────────────────────────

async function shutdown(signal) {
    log('info', `${signal} received. Shutting down...`);
    try { await client.destroy(); } catch (_) {}
    process.exit(0);
}

process.on('SIGINT',  () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// ── Start ─────────────────────────────────────────────────────────────────────

log('info', `WhatsApp Watcher starting... (DRY_RUN=${DRY_RUN})`);
log('info', `Session: ${SESSION_DIR}`);
log('info', `Vault  : ${VAULT_PATH}`);
client.initialize();
