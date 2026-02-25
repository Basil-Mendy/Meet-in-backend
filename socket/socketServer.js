/*
 * Socket.IO server for Meet-In
 * - Uses JWT authentication on socket connection
 * - Keeps in-memory map of connected users
 * - Joins personal room and forum rooms
 * - Emits events to user, forum rooms, or broadcast
 * - Designed to allow Redis adapter integration later
 */

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const jwt = require('jsonwebtoken');
const {
    addConnectedUser,
    removeConnectedUser,
    getSocketIdsForUser,
    fetchUserForumRooms,
} = require('./socketHandlers');

const PORT = process.env.SOCKET_PORT || 5000;
const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000/api';
const JWT_SECRET = process.env.SOCKET_JWT_SECRET || process.env.JWT_SECRET || 'CHANGE_ME';

function startSocketServer({ port = PORT } = {}) {
    const app = express();
    const server = http.createServer(app);

    const io = new Server(server, {
        cors: {
            origin: '*', // tighten in production to your frontend origin
            methods: ['GET', 'POST'],
        },
        pingTimeout: 60000,
        allowEIO3: true,
    });

    // Optional: configure Redis adapter here for scaling
    // const { createAdapter } = require('@socket.io/redis-adapter');
    // const pubClient = createClient({ url: process.env.REDIS_URL });
    // const subClient = pubClient.duplicate();
    // await Promise.all([pubClient.connect(), subClient.connect()]);
    // io.adapter(createAdapter(pubClient, subClient));

    io.use(async (socket, next) => {
        try {
            // Token can be sent via handshake.auth or query for backwards compat
            const token = socket.handshake.auth?.token || socket.handshake.query?.token;
            if (!token) return next(new Error('Authentication error: no token'));

            // Verify JWT
            const payload = jwt.verify(token, JWT_SECRET);
            socket.user = { id: String(payload.user_id || payload.id), payload };
            return next();
        } catch (err) {
            console.warn('Socket auth failed:', err.message || err);
            return next(new Error('Authentication error: invalid token'));
        }
    });

    io.on('connection', async (socket) => {
        const userId = socket.user.id;
        console.log(`[WS] User connected: ${userId} (socket ${socket.id})`);

        // Track connected user
        addConnectedUser(userId, socket.id);

        // Join personal room
        const personalRoom = `user_${userId}`;
        socket.join(personalRoom);

        // Join user's forum rooms (fetch from backend)
        try {
            const token = socket.handshake.auth?.token || socket.handshake.query?.token;
            const forumRooms = await fetchUserForumRooms({ backendApiUrl: BACKEND_API_URL, token });
            forumRooms.forEach(r => socket.join(r));
        } catch (err) {
            console.warn('Failed to auto-join forum rooms:', err);
        }

        // Notify others that user is online
        socket.broadcast.emit('user_online', { userId });

        // Standard events
        socket.on('join_room', ({ room }) => {
            if (!room) return;
            // TODO: validate room access if needed
            socket.join(room);
        });

        socket.on('leave_room', ({ room }) => {
            if (!room) return;
            socket.leave(room);
        });

        socket.on('send_message', (payload) => {
            // payload: { toUserId?, room?, message, meta }
            const { toUserId, room, message, meta } = payload || {};
            const envelope = {
                from: userId,
                message,
                meta: meta || {},
                createdAt: new Date().toISOString(),
            };

            if (toUserId) {
                // emit to specific user's personal room
                io.to(`user_${String(toUserId)}`).emit('new_message', envelope);
            } else if (room) {
                // emit to a room (e.g., forum_x or group_x)
                socket.to(room).emit('new_message', envelope); // exclude sender
                socket.emit('new_message', envelope); // also emit back to sender if desired
            } else {
                // broadcast to all excluding sender
                socket.broadcast.emit('new_message', envelope);
            }
        });

        socket.on('notify', (payload) => {
            // payload: { type, forumId?, toUserId?, data }
            const { type, forumId, toUserId, data } = payload || {};
            if (toUserId) {
                io.to(`user_${String(toUserId)}`).emit('notification_update', { type, data });
            } else if (forumId) {
                io.to(`forum_${String(forumId)}`).emit('notification_update', { type, data });
            } else {
                socket.broadcast.emit('notification_update', { type, data });
            }
        });

        // allow clients to mark notifications read via socket
        socket.on('clear_tab_notifications', async ({ forumId, tab }) => {
            // Validate & then emit back to client to update UI and optionally call backend
            socket.emit('tab_cleared', { forumId, tab });
        });

        socket.on('disconnect', (reason) => {
            console.log(`[WS] User disconnected: ${userId} (socket ${socket.id})`, reason);
            removeConnectedUser(userId, socket.id);
            // If no sockets for user, broadcast offline
            const remaining = getSocketIdsForUser(userId);
            if (remaining.length === 0) {
                socket.broadcast.emit('user_offline', { userId });
            }
        });
    });

    server.listen(port, () => {
        console.log(`Socket.IO server listening on port ${port}`);
    });

    return { io, server };
}

if (require.main === module) {
    // eslint-disable-next-line no-console
    startSocketServer();
}

module.exports = { startSocketServer };
