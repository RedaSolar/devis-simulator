// =========================================================
// TAQINOR — JWT Authentication Utilities
// =========================================================

const API_BASE = '';

function getToken() {
    return localStorage.getItem('taqinor_token');
}

function setToken(t) {
    localStorage.setItem('taqinor_token', t);
}

function clearToken() {
    localStorage.removeItem('taqinor_token');
}

function getUser() {
    try {
        return JSON.parse(localStorage.getItem('taqinor_user') || 'null');
    } catch (e) {
        return null;
    }
}

function setUser(u) {
    localStorage.setItem('taqinor_user', JSON.stringify(u));
}

function clearUser() {
    localStorage.removeItem('taqinor_user');
}

async function authFetch(url, options = {}) {
    const token = getToken();
    if (!token) {
        window.location.href = '/login';
        return null;
    }
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...(options.headers || {}),
    };
    try {
        const res = await fetch(API_BASE + url, { ...options, headers });
        if (res.status === 401) {
            clearToken();
            clearUser();
            window.location.href = '/login';
            return null;
        }
        return res;
    } catch (err) {
        console.error('Network error:', err);
        throw err;
    }
}

async function logout() {
    clearToken();
    clearUser();
    window.location.href = '/login';
}

function isAuthenticated() {
    return !!getToken();
}

function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = '/login';
        return false;
    }
    return true;
}
