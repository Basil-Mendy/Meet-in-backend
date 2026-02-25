const axios = require('axios');

/**
 * Socket handlers module
 * - keeps connectedUsers map
 * - helper to join rooms, emit events, validate access (placeholders)
 * - designed so Redis adapter can be plugged in later for horizontal scaling
 */

const connectedUsers = new Map(); // userId -> socketId(s) (Set)

function addConnectedUser(userId, socketId) {
    const entry = connectedUsers.get(userId) || new Set();
    entry.add(socketId);
    connectedUsers.set(userId, entry);
}

function removeConnectedUser(userId, socketId) {
    const entry = connectedUsers.get(userId);
    if (!entry) return;
    entry.delete(socketId);
    if (entry.size === 0) connectedUsers.delete(userId);
}

function getSocketIdsForUser(userId) {
    const entry = connectedUsers.get(userId);
    return entry ? Array.from(entry) : [];
}

/**
 * Fetch list of forum rooms the user belongs to.
 * This is a placeholder that calls an API endpoint on your main backend.
 * The endpoint should return an array of forum objects with `id` field.
 */
async function fetchUserForumRooms({ backendApiUrl, token }) {
    if (!backendApiUrl || !token) return [];
    try {
        const res = await axios.get(`${backendApiUrl.replace(/\/$/, '')}/forums/my-forums/`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        // Expecting res.data to be array of forums with `id` field
        if (Array.isArray(res.data)) return res.data.map(f => `forum_${f.id}`);
        return [];
    } catch (err) {
        console.warn('Failed to fetch user forums for room join:', err?.message || err);
        return [];
    }
}

module.exports = {
    connectedUsers,
    addConnectedUser,
    removeConnectedUser,
    getSocketIdsForUser,
    fetchUserForumRooms,
};
