/**
 * WhatsApp Session Manager
 *
 * Connects to WhatsApp Web via QR code scan and persists the session
 * locally so re-scanning is not needed on restart.
 *
 * Session path : D:/Hackathon-0 Q4/ai-employee-project/.wwebjs_auth/
 * (Never stored inside the vault — kept outside for security.)
 *
 * Usage:
 *   node whatsapp_session.js           # Start and keep alive
 *   node whatsapp_session.js --test    # Connect, print status, disconnect
 */

'use strict';

const path = require('path');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

// ── Config ────────────────────────────────────────────────────────────────────

const SESSION_DIR = path.join(__dirname, '.wwebjs_auth');
const TEST_MODE   = process.argv.includes('--test');

// ── Client Setup ──────────────────────────────────────────────────────────────

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: SESSION_DIR,
        clientId: 'ai-employee',
    }),
    webVersionCache: {
        type: 'remote',
        remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1017170987-alpha.html',
    },
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-features=VizDisplayCompositor',
        ],
    },
});

// ── Event Handlers ────────────────────────────────────────────────────────────

client.on('qr', (qr) => {
    console.log('\n[WhatsApp Session] Scan this QR code with your phone:');
    console.log('[WhatsApp Session] WhatsApp → Settings → Linked Devices → Link a Device\n');
    qrcode.generate(qr, { small: true });
});

client.on('loading_screen', (percent, message) => {
    console.log(`[WhatsApp Session] Loading: ${percent}% — ${message}`);
});

client.on('authenticated', () => {
    console.log('[WhatsApp Session] Authenticated. Session saved to:', SESSION_DIR);
});

client.on('auth_failure', (msg) => {
    console.error('[WhatsApp Session] Authentication failed:', msg);
    console.error('[WhatsApp Session] Delete .wwebjs_auth/ folder and restart to re-scan QR.');
    process.exit(1);
});

client.on('ready', () => {
    const info = client.info;
    console.log('\n[WhatsApp Session] Connected successfully!');
    console.log(`[WhatsApp Session] Account  : ${info.pushname} (${info.wid.user})`);
    console.log(`[WhatsApp Session] Platform : ${info.platform}`);
    console.log(`[WhatsApp Session] Session  : ${SESSION_DIR}`);

    if (TEST_MODE) {
        console.log('\n[WhatsApp Session] --test mode: disconnecting now.');
        client.destroy().then(() => process.exit(0));
    } else {
        console.log('[WhatsApp Session] Session manager running. Press Ctrl+C to stop.\n');
    }
});

client.on('disconnected', (reason) => {
    console.warn('[WhatsApp Session] Disconnected:', reason);
    if (!TEST_MODE) {
        console.log('[WhatsApp Session] Attempting to reconnect...');
        client.initialize();
    }
});

// ── Graceful Shutdown ─────────────────────────────────────────────────────────

async function shutdown(signal) {
    console.log(`\n[WhatsApp Session] ${signal} received. Closing connection...`);
    try {
        await client.destroy();
        console.log('[WhatsApp Session] Disconnected cleanly.');
    } catch (e) {
        console.error('[WhatsApp Session] Error during shutdown:', e.message);
    }
    process.exit(0);
}

process.on('SIGINT',  () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// ── Start ─────────────────────────────────────────────────────────────────────

console.log('[WhatsApp Session] Initializing...');
console.log('[WhatsApp Session] Session dir:', SESSION_DIR);
client.initialize();
