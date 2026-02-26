/**
 * WhatsApp MCP Server — AI Employee
 *
 * Exposes WhatsApp capabilities to Claude Code via the Model Context Protocol.
 * Runs in stdio mode (piped by Claude Code CLI).
 *
 * Tools:
 *   whatsapp_send_message    — REQUIRES APPROVAL (creates /Pending_Approval/ file)
 *   whatsapp_get_chats       — read-only
 *   whatsapp_get_messages    — read-only
 *   whatsapp_search_messages — read-only
 *   whatsapp_get_chat_summary— read-only
 *   whatsapp_delete_message  — REQUIRES APPROVAL
 *   whatsapp_mark_read       — auto-approved
 *   whatsapp_get_contacts    — read-only
 *
 * Usage (registered via .claude/mcp.json):
 *   node whatsapp_mcp.js
 */

'use strict';

const fs   = require('fs');
const path = require('path');
const readline = require('readline');
const { Client, LocalAuth } = require('whatsapp-web.js');

// ── Config ────────────────────────────────────────────────────────────────────

require('dotenv').config({ path: path.join(__dirname, '../AI_Employee_Vault/.env') });

const VAULT_PATH          = process.env.VAULT_PATH || path.join(__dirname, '../AI_Employee_Vault');
const DRY_RUN             = process.env.DRY_RUN !== 'false';
const MAX_MSGS_PER_HOUR   = parseInt(process.env.MAX_MESSAGES_PER_HOUR || '20', 10);
const SESSION_DIR         = path.join(__dirname, '.wwebjs_auth');
const PENDING_DIR         = path.join(VAULT_PATH, 'Pending_Approval');
const LOG_DIR             = path.join(VAULT_PATH, 'Logs', 'whatsapp');

fs.mkdirSync(PENDING_DIR, { recursive: true });
fs.mkdirSync(LOG_DIR,     { recursive: true });

// ── Rate Limiter ──────────────────────────────────────────────────────────────

const _sendTimestamps = [];

function checkSendRateLimit() {
    const now    = Date.now();
    const cutoff = now - 3600_000;
    while (_sendTimestamps.length && _sendTimestamps[0] < cutoff) _sendTimestamps.shift();
    if (_sendTimestamps.length >= MAX_MSGS_PER_HOUR) return false;
    _sendTimestamps.push(now);
    return true;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function isoNow() {
    return new Date().toISOString().replace('T', ' ').slice(0, 19) + 'Z';
}

function isoExpiry(hours = 24) {
    return new Date(Date.now() + hours * 3_600_000)
        .toISOString().replace('T', ' ').slice(0, 19) + 'Z';
}

function sanitize(str) {
    return (str || '').replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, '_').slice(0, 40);
}

function timestampPrefix() {
    return new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
}

// ── WhatsApp Client ───────────────────────────────────────────────────────────

let waClient      = null;
let waReady       = false;
const waReadyWait = [];

function getClient() {
    return new Promise((resolve, reject) => {
        if (waReady) return resolve(waClient);
        waReadyWait.push({ resolve, reject });

        if (!waClient) {
            waClient = new Client({
                authStrategy: new LocalAuth({ dataPath: SESSION_DIR, clientId: 'ai-employee-mcp' }),
                puppeteer: {
                    headless: true,
                    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
                },
            });

            waClient.on('ready', () => {
                waReady = true;
                waReadyWait.forEach(p => p.resolve(waClient));
                waReadyWait.length = 0;
            });

            waClient.on('auth_failure', (msg) => {
                waReadyWait.forEach(p => p.reject(new Error('WhatsApp auth failure: ' + msg)));
                waReadyWait.length = 0;
            });

            waClient.on('disconnected', () => {
                waReady = false;
            });

            waClient.initialize().catch(err => {
                waReadyWait.forEach(p => p.reject(err));
                waReadyWait.length = 0;
            });
        }

        // Timeout after 60s
        setTimeout(() => {
            if (!waReady) {
                const idx = waReadyWait.findIndex(p => p.resolve === resolve);
                if (idx !== -1) {
                    waReadyWait.splice(idx, 1);
                    reject(new Error('WhatsApp client did not become ready within 60s. Is whatsapp_watcher.js running?'));
                }
            }
        }, 60_000);
    });
}

// ── Approval File Creator ─────────────────────────────────────────────────────

function createSendApproval({ toName, toNumber, message }) {
    const prefix   = timestampPrefix();
    const filename = `WHATSAPP_REPLY_${sanitize(toName || toNumber)}_${prefix}.md`;
    const filepath = path.join(PENDING_DIR, filename);

    const content = [
        '---',
        'type: approval_request',
        'action: whatsapp_reply',
        `to_name: "${toName || ''}"`,
        `to_number: "${toNumber}"`,
        `message_preview: "${message.slice(0, 100).replace(/"/g, "'")}"`,
        `created: ${isoNow()}`,
        `expires: ${isoExpiry(24)}`,
        'status: pending',
        `dry_run: ${DRY_RUN}`,
        '---',
        '',
        '# WhatsApp Reply Approval',
        '',
        `## Reply Details`,
        `- **To**: ${toName || toNumber} (${toNumber})`,
        `- **Proposed Reply**:`,
        '',
        `> ${message.replace(/\n/g, '\n> ')}`,
        '',
        '## To Approve',
        'Move this file to `/Approved/` folder.',
        '',
        '## To Edit',
        'Edit the reply text above, then move to `/Approved/`.',
        '',
        '## To Reject',
        'Move this file to `/Rejected/` folder.',
        '',
        '*Generated by whatsapp_mcp — ' + isoNow() + '*',
    ].join('\n');

    fs.writeFileSync(filepath, content, 'utf8');
    return filename;
}

function createDeleteApproval({ chatName, messageId, messagePreview }) {
    const prefix   = timestampPrefix();
    const filename = `WHATSAPP_DELETE_${sanitize(chatName)}_${prefix}.md`;
    const filepath = path.join(PENDING_DIR, filename);

    const content = [
        '---',
        'type: approval_request',
        'action: whatsapp_delete',
        `chat: "${chatName}"`,
        `message_id: "${messageId}"`,
        `message_preview: "${(messagePreview || '').slice(0, 100).replace(/"/g, "'")}"`,
        `created: ${isoNow()}`,
        'status: pending',
        'priority: medium',
        '---',
        '',
        '# WhatsApp Delete Approval',
        '',
        `## Delete Request`,
        `- **Chat**: ${chatName}`,
        `- **Message ID**: ${messageId}`,
        `- **Preview**: ${messagePreview || '(no text)'}`,
        '',
        '## To Approve',
        'Move to `/Approved/`',
        '',
        '## To Reject',
        'Move to `/Rejected/`',
    ].join('\n');

    fs.writeFileSync(filepath, content, 'utf8');
    return filename;
}

// ── MCP Tool Implementations ──────────────────────────────────────────────────

const tools = {

    async whatsapp_send_message({ to, message }) {
        if (!to || !message) throw new Error('Parameters required: to, message');

        if (!checkSendRateLimit()) {
            return { status: 'rate_limited', reason: `Max ${MAX_MSGS_PER_HOUR} messages/hour reached` };
        }

        // Always create approval file — never send directly
        const approvalFile = createSendApproval({ toName: to, toNumber: to, message });
        const result = {
            status: 'pending_approval',
            approval_file: approvalFile,
            message: `Approval required. Review and move ${approvalFile} to /Approved/ to send.`,
            dry_run: DRY_RUN,
        };

        if (DRY_RUN) {
            result.dry_run_note = 'DRY_RUN=true — even after approval, message will only be logged.';
        }

        return result;
    },

    async whatsapp_get_chats() {
        const client = await getClient();
        const chats  = await client.getChats();

        return chats.slice(0, 50).map(c => ({
            id          : c.id._serialized,
            name        : c.name,
            isGroup     : c.isGroup,
            unreadCount : c.unreadCount,
            lastMessage : c.lastMessage?.body?.slice(0, 100) || '',
            timestamp   : c.timestamp,
        }));
    },

    async whatsapp_get_messages({ chat_id, limit = 50 }) {
        if (!chat_id) throw new Error('Parameter required: chat_id');
        const client = await getClient();
        const chat   = await client.getChatById(chat_id);
        const msgs   = await chat.fetchMessages({ limit: Math.min(limit, 200) });

        return msgs.map(m => ({
            id        : m.id.id,
            from      : m.from,
            fromMe    : m.fromMe,
            body      : m.body?.slice(0, 500),
            timestamp : m.timestamp,
            hasMedia  : m.hasMedia,
            type      : m.type,
        }));
    },

    async whatsapp_search_messages({ query, chat_id }) {
        if (!query) throw new Error('Parameter required: query');
        const client = await getClient();
        const chats  = chat_id
            ? [await client.getChatById(chat_id)]
            : await client.getChats();

        const results = [];
        for (const chat of chats.slice(0, 20)) {
            const msgs = await chat.fetchMessages({ limit: 100 });
            for (const m of msgs) {
                if (m.body?.toLowerCase().includes(query.toLowerCase())) {
                    results.push({
                        chat     : chat.name,
                        chat_id  : chat.id._serialized,
                        id       : m.id.id,
                        from     : m.from,
                        body     : m.body?.slice(0, 300),
                        timestamp: m.timestamp,
                    });
                }
            }
            if (results.length >= 50) break;
        }

        return results;
    },

    async whatsapp_get_chat_summary({ chat_id, period = 'today' }) {
        if (!chat_id) throw new Error('Parameter required: chat_id');

        const now      = Math.floor(Date.now() / 1000);
        const cutoffs  = { today: now - 86400, week: now - 604800, month: now - 2592000 };
        const cutoff   = cutoffs[period] || cutoffs.today;

        const client  = await getClient();
        const chat    = await client.getChatById(chat_id);
        const msgs    = await chat.fetchMessages({ limit: 500 });
        const recent  = msgs.filter(m => m.timestamp >= cutoff);

        const received   = recent.filter(m => !m.fromMe);
        const sent       = recent.filter(m =>  m.fromMe);
        const keywords   = {};

        for (const m of received) {
            for (const word of (m.body || '').toLowerCase().split(/\W+/)) {
                if (word.length > 4) keywords[word] = (keywords[word] || 0) + 1;
            }
        }

        const topTopics = Object.entries(keywords)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([w]) => w);

        const actionItems = received
            .filter(m => TRIGGER_KEYWORDS_GLOBAL.some(kw => (m.body || '').toLowerCase().includes(kw)))
            .map(m => m.body?.slice(0, 100));

        return {
            chat_name    : chat.name,
            period,
            total_messages: recent.length,
            received     : received.length,
            sent         : sent.length,
            top_topics   : topTopics,
            action_items : actionItems.slice(0, 10),
        };
    },

    async whatsapp_delete_message({ chat_id, message_id }) {
        if (!chat_id || !message_id) throw new Error('Parameters required: chat_id, message_id');

        const client  = await getClient();
        const chat    = await client.getChatById(chat_id);
        const msgs    = await chat.fetchMessages({ limit: 100 });
        const msg     = msgs.find(m => m.id.id === message_id);

        const approvalFile = createDeleteApproval({
            chatName       : chat.name,
            messageId      : message_id,
            messagePreview : msg?.body?.slice(0, 100) || '',
        });

        return {
            status        : 'pending_approval',
            approval_file : approvalFile,
            message       : `Approval required. Move ${approvalFile} to /Approved/ to delete.`,
        };
    },

    async whatsapp_mark_read({ chat_id }) {
        if (!chat_id) throw new Error('Parameter required: chat_id');

        if (DRY_RUN) {
            return { status: 'dry_run', message: `DRY_RUN: would mark ${chat_id} as read` };
        }

        const client = await getClient();
        const chat   = await client.getChatById(chat_id);
        await chat.sendSeen();
        return { status: 'success', chat_id };
    },

    async whatsapp_get_contacts() {
        const client   = await getClient();
        const contacts = await client.getContacts();

        return contacts
            .filter(c => c.isMyContact && c.number)
            .slice(0, 200)
            .map(c => ({
                name  : c.pushname || c.name || '',
                number: c.number,
                id    : c.id._serialized,
            }));
    },
};

// Helper referenced inside whatsapp_get_chat_summary scope
const TRIGGER_KEYWORDS_GLOBAL = [
    'urgent', 'asap', 'invoice', 'payment', 'help', 'pricing',
    'deadline', 'emergency', 'critical', 'important',
];

// ── MCP Protocol (stdio JSON-RPC) ─────────────────────────────────────────────

const MCP_TOOLS = [
    {
        name: 'whatsapp_send_message',
        description: 'Send a WhatsApp message. ALWAYS creates an approval file — message is not sent until human approves.',
        inputSchema: {
            type: 'object',
            properties: {
                to     : { type: 'string', description: 'Phone number or contact name' },
                message: { type: 'string', description: 'Message text to send' },
            },
            required: ['to', 'message'],
        },
    },
    {
        name: 'whatsapp_get_chats',
        description: 'Get list of recent WhatsApp chats with unread counts.',
        inputSchema: { type: 'object', properties: {} },
    },
    {
        name: 'whatsapp_get_messages',
        description: 'Get messages from a specific chat.',
        inputSchema: {
            type: 'object',
            properties: {
                chat_id: { type: 'string', description: 'Chat ID from whatsapp_get_chats' },
                limit  : { type: 'number', description: 'Max messages to return (default 50)' },
            },
            required: ['chat_id'],
        },
    },
    {
        name: 'whatsapp_search_messages',
        description: 'Search messages across all chats or within a specific chat.',
        inputSchema: {
            type: 'object',
            properties: {
                query  : { type: 'string', description: 'Search text' },
                chat_id: { type: 'string', description: 'Optional: restrict to this chat' },
            },
            required: ['query'],
        },
    },
    {
        name: 'whatsapp_get_chat_summary',
        description: 'Get an AI-ready summary of a chat for a time period.',
        inputSchema: {
            type: 'object',
            properties: {
                chat_id: { type: 'string', description: 'Chat ID from whatsapp_get_chats' },
                period : { type: 'string', enum: ['today', 'week', 'month'], description: 'Time period' },
            },
            required: ['chat_id'],
        },
    },
    {
        name: 'whatsapp_delete_message',
        description: 'Request deletion of a WhatsApp message. ALWAYS requires human approval.',
        inputSchema: {
            type: 'object',
            properties: {
                chat_id   : { type: 'string', description: 'Chat ID' },
                message_id: { type: 'string', description: 'Message ID from whatsapp_get_messages' },
            },
            required: ['chat_id', 'message_id'],
        },
    },
    {
        name: 'whatsapp_mark_read',
        description: 'Mark a chat as read. Auto-approved (safe action).',
        inputSchema: {
            type: 'object',
            properties: {
                chat_id: { type: 'string', description: 'Chat ID to mark as read' },
            },
            required: ['chat_id'],
        },
    },
    {
        name: 'whatsapp_get_contacts',
        description: 'Get list of WhatsApp contacts.',
        inputSchema: { type: 'object', properties: {} },
    },
];

// ── stdio JSON-RPC Handler ────────────────────────────────────────────────────

const rl = readline.createInterface({ input: process.stdin, terminal: false });

function sendResponse(id, result) {
    const msg = JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n';
    process.stdout.write(msg);
}

function sendError(id, code, message) {
    const msg = JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n';
    process.stdout.write(msg);
}

rl.on('line', async (line) => {
    let req;
    try { req = JSON.parse(line.trim()); } catch { return; }

    const { id, method, params } = req;

    try {
        if (method === 'initialize') {
            sendResponse(id, {
                protocolVersion: '2024-11-05',
                capabilities   : { tools: {} },
                serverInfo     : { name: 'whatsapp', version: '1.0.0' },
            });
        } else if (method === 'tools/list') {
            sendResponse(id, { tools: MCP_TOOLS });
        } else if (method === 'tools/call') {
            const toolName = params?.name;
            const toolArgs = params?.arguments || {};
            const fn       = tools[toolName];

            if (!fn) {
                sendError(id, -32601, `Unknown tool: ${toolName}`);
                return;
            }

            const result = await fn(toolArgs);
            sendResponse(id, {
                content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            });
        } else if (method === 'notifications/initialized') {
            // No response needed for notifications
        } else {
            sendError(id, -32601, `Unknown method: ${method}`);
        }
    } catch (err) {
        sendError(id, -32603, err.message);
    }
});

process.on('SIGINT',  () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));

// Suppress unhandled rejections from WhatsApp client reconnect
process.on('unhandledRejection', (reason) => {
    const msg = String(reason?.message || reason);
    if (!msg.includes('WhatsApp')) {
        process.stderr.write(`[whatsapp_mcp] Unhandled rejection: ${msg}\n`);
    }
});
