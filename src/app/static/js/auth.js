// IndexedDB + AES-256-GCM token storage
// Ported from qa-pipe (x5/git_reps/qa-pipe)

const DB_NAME    = 'QAPipeDB';
const DB_VERSION = 1;
const STORE_NAME = 'encryptedData';
const TOKEN_KEY  = 'gitlabToken';

let db = null;

// ── IndexedDB ──────────────────────────────────────────────

async function initDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => { db = req.result; resolve(db); };
    req.onupgradeneeded = (e) => {
      const database = e.target.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    };
  });
}

async function idbPut(data) {
  if (!db) await initDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_NAME], 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.put(data);
    req.onsuccess = () => resolve(req.result);
    req.onerror  = () => reject(req.error);
  });
}

async function idbGet(id) {
  if (!db) await initDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_NAME], 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const req = store.get(id);
    req.onsuccess = () => resolve(req.result);
    req.onerror  = () => reject(req.error);
  });
}

async function idbDelete(id) {
  if (!db) await initDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_NAME], 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror  = () => reject(req.error);
  });
}

// ── Crypto helpers ─────────────────────────────────────────

function toHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

function fromHex(hex) {
  return new Uint8Array(hex.match(/.{2}/g).map(b => parseInt(b, 16)));
}

async function deriveKey(password, salt) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

// ── Public API ─────────────────────────────────────────────

async function hasToken() {
  const data = await idbGet(TOKEN_KEY);
  return !!data;
}

async function saveToken(token, masterPassword) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv   = crypto.getRandomValues(new Uint8Array(12));
  const key  = await deriveKey(masterPassword, salt);
  const enc  = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(token)
  );
  await idbPut({
    id: TOKEN_KEY,
    encryptedToken: toHex(new Uint8Array(enc)),
    salt: toHex(salt),
    iv:   toHex(iv),
    createdAt: Date.now(),
  });
}

async function loadToken(masterPassword) {
  const data = await idbGet(TOKEN_KEY);
  if (!data) return null;
  try {
    const salt = fromHex(data.salt);
    const iv   = fromHex(data.iv);
    const key  = await deriveKey(masterPassword, salt);
    const dec  = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      fromHex(data.encryptedToken)
    );
    return new TextDecoder().decode(dec);
  } catch {
    return null; // wrong password
  }
}

async function clearToken() {
  await idbDelete(TOKEN_KEY);
}
