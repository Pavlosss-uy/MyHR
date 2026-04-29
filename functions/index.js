"use strict";

const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { getFirestore, FieldValue } = require("firebase-admin/firestore");
const { initializeApp, getApps } = require("firebase-admin/app");

if (!getApps().length) initializeApp();

const db = getFirestore();

// Firestore hard limit is 500 writes per batch; leave one slot for safety.
const BATCH_LIMIT = 499;

/**
 * Callable function invoked by the frontend after updateEmail() succeeds.
 *
 * The new email is read from the verified Auth token — it cannot be spoofed
 * by the client because Firebase has already committed and signed the change
 * before the frontend can force-refresh the token.
 *
 * Request payload: { oldEmail: string }
 * Returns: { updated: number }
 */
exports.syncEmailUpdate = onCall({ enforceAppCheck: false }, async (request) => {
    if (!request.auth) {
        throw new HttpsError("unauthenticated", "Authentication required.");
    }

    const uid = request.auth.uid;
    const newEmail = request.auth.token.email;
    const { oldEmail } = request.data;

    if (!oldEmail || typeof oldEmail !== "string") {
        throw new HttpsError("invalid-argument", "oldEmail must be a non-empty string.");
    }
    if (!newEmail) {
        throw new HttpsError(
            "internal",
            "New email not found in auth token. Ensure the token was force-refreshed after updateEmail().",
        );
    }
    if (oldEmail.toLowerCase() === newEmail.toLowerCase()) {
        return { updated: 0 };
    }

    const updated = await _syncEmail(uid, oldEmail, newEmail);
    return { updated };
});

/**
 * Gathers all stale references to oldEmail, then commits them in batches.
 * Two pass strategy:
 *   1. InvitationTokens.targetEmail — direct collection query, O(1) round-trips.
 *   2. Jobs/*/Candidates — fan-out per job doc, deduplicated by UID and email.
 */
async function _syncEmail(uid, oldEmail, newEmail) {
    const timestamp = FieldValue.serverTimestamp();
    const ops = []; // { ref, data }

    // ── 1. InvitationTokens ──────────────────────────────────────────────────
    const inviteSnaps = await db
        .collection("InvitationTokens")
        .where("targetEmail", "==", oldEmail)
        .get();

    inviteSnaps.forEach((doc) =>
        ops.push({ ref: doc.ref, data: { targetEmail: newEmail, emailUpdatedAt: timestamp } }),
    );

    // ── 2. Jobs/*/Candidates ─────────────────────────────────────────────────
    const jobSnaps = await db.collection("Jobs").get();

    await Promise.all(
        jobSnaps.docs.map(async (jobDoc) => {
            const candidatesRef = jobDoc.ref.collection("Candidates");

            // Query by UID (authoritative — survives prior email changes) and
            // by email (catches records created before UID was stored).
            const [byUid, byEmail] = await Promise.all([
                candidatesRef.where("uid", "==", uid).get(),
                candidatesRef.where("email", "==", oldEmail).get(),
            ]);

            const seen = new Set();
            for (const doc of [...byUid.docs, ...byEmail.docs]) {
                if (seen.has(doc.id)) continue;
                seen.add(doc.id);
                ops.push({ ref: doc.ref, data: { email: newEmail, emailUpdatedAt: timestamp } });
            }
        }),
    );

    // ── 3. Commit in chunks ──────────────────────────────────────────────────
    for (let i = 0; i < ops.length; i += BATCH_LIMIT) {
        const batch = db.batch();
        for (const { ref, data } of ops.slice(i, i + BATCH_LIMIT)) {
            batch.update(ref, data);
        }
        await batch.commit();
    }

    return ops.length;
}
