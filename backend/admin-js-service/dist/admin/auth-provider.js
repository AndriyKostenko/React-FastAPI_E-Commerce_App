import { DefaultAuthProvider } from 'adminjs';
import componentLoader from './component-loader.js';
const provider = new DefaultAuthProvider({
    componentLoader,
    authenticate: async ({ email, password }) => {
        try {
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);
            const response = await fetch(`${process.env.API_GATEWAY_SERVICE_URL + process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData.toString(),
            });
            if (!response.ok) {
                return null;
            }
            const data = await response.json();
            if (data.user_role !== process.env.SECRET_ROLE) {
                console.log('Unauthorized role:', data.user_role);
                return null;
            }
            return {
                email: data.user_email,
                id: data.user_id,
                role: data.user_role,
                token: data.access_token,
            };
        }
        catch (error) {
            console.error('Error during authentication:', error);
            return null;
        }
    },
});
export default provider;
