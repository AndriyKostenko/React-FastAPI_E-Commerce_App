import type { NextFunction, Request, Response } from 'express';

/**
 * Response headers for a back office that shows customers' personal data.
 *
 * No full Content-Security-Policy: AdminJS's pages depend on inline scripts
 * (the page state is written into one), so only `frame-ancestors` is set,
 * which forbids framing (clickjacking) without touching script loading.
 */
export const securityHeaders = (req: Request, res: Response, next: NextFunction): void => {
    res.set({
        'Content-Security-Policy': "frame-ancestors 'none'",
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'same-origin',
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Permissions-Policy':
            'camera=(), microphone=(), geolocation=(), payment=(), ' +
            'publickey-credentials-get=(self), publickey-credentials-create=(self)',
    });
    // Admin pages and data must not be kept by the browser or any proxy;
    // AdminJS's static bundles may be.
    if (!req.path.includes('/frontend/assets/')) {
        res.set('Cache-Control', 'no-store');
    }
    next();
};
