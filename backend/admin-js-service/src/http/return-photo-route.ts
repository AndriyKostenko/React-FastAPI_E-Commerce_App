import express, { Request, Response, Router } from 'express';

import { isAdminIdentity } from '../auth/admin-session.js';
import { AdminGateway } from '../gateway/admin-gateway.js';
import { GatewayError } from '../gateway/gateway-client.js';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Return photos, streamed through admin-js for the signed-in admin.
 *
 * They are private: order-service serves them only to an admin, with no
 * presigned link that could be forwarded. The browser cannot call the
 * gateway as the admin (the tokens never reach it), so admin-js does, per
 * image, for whoever holds this session.
 */
export const returnPhotoRoute = (api: AdminGateway): Router => {
    const router = express.Router();
    router.get('/return-photos/:returnId/:index', async (req: Request, res: Response) => {
        const admin = req.session?.adminUser;
        const { returnId, index } = req.params;
        if (!isAdminIdentity(admin)) {
            res.sendStatus(401);
            return;
        }
        if (!UUID_PATTERN.test(returnId) || !/^\d{1,2}$/.test(index)) {
            res.sendStatus(404);
            return;
        }
        try {
            const upstream = await api.download(admin, `/admin/returns/${returnId}/photos/${index}`);
            const contentType = upstream.headers.get('content-type') ?? 'application/octet-stream';
            // Only images are passed on, so nothing else can be rendered on this origin.
            if (!/^image\/(jpeg|png|webp)$/.test(contentType)) {
                res.sendStatus(415);
                return;
            }
            res.set({ 'Content-Type': contentType, 'Cache-Control': 'private, no-store', 'Content-Disposition': 'inline' });
            res.send(Buffer.from(await upstream.arrayBuffer()));
        } catch (error) {
            res.sendStatus(error instanceof GatewayError ? error.status : 502);
        }
    });
    return router;
};
