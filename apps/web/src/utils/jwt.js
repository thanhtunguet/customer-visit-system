/**
 * JWT utility functions for client-side token handling
 * Note: This is for reading token claims only - never use for validation
 */
/**
 * Decode JWT token payload (client-side only, not for validation)
 */
export function decodeJWT(token) {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) {
            return null;
        }
        const payload = parts[1];
        const decoded = JSON.parse(atob(payload));
        return decoded;
    }
    catch (error) {
        console.error('Failed to decode JWT:', error);
        return null;
    }
}
/**
 * Check if JWT token is expired
 */
export function isTokenExpired(token) {
    const payload = decodeJWT(token);
    if (!payload) {
        return true;
    }
    return Date.now() >= payload.exp * 1000;
}
/**
 * Get tenant ID from JWT token
 */
export function getTenantIdFromToken(token) {
    const payload = decodeJWT(token);
    return payload?.tenant_id || null;
}
/**
 * Get user role from JWT token
 */
export function getRoleFromToken(token) {
    const payload = decodeJWT(token);
    return payload?.role || null;
}
/**
 * Get site ID from JWT token
 */
export function getSiteIdFromToken(token) {
    const payload = decodeJWT(token);
    return payload?.site_id || null;
}
