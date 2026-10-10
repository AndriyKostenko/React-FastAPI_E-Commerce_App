import React, { FormEvent, useRef, useState } from 'react';
import { Box, Button, FormGroup, H2, H5, Input, Label, MessageBox, Text } from '@adminjs/design-system';

/**
 * The admin login page: password, then passkey.
 *
 * 1. The password goes to admin-js (`<root>/passkey/options`), which asks
 *    user-service for a challenge; a wrong password stops here.
 * 2. The device signs the challenge (with its PIN or biometric).
 * 3. Only the signed answer is posted to the AdminJS login handler, which has
 *    user-service verify it and only then creates the session.
 */

interface LoginState {
    action: string;
    errorMessage?: string;
}

interface AdminWindow {
    __APP_STATE__?: Partial<LoginState>;
    REDUX_STATE?: { paths?: { rootPath?: string } };
}

interface OptionsResponse {
    challengeId?: string;
    options?: PublicKeyCredentialRequestOptionsJSON;
    detail?: string;
}

const adminWindow = window as unknown as AdminWindow;

const PasskeyLogin: React.FC = () => {
    const action = adminWindow.__APP_STATE__?.action ?? '/admin/login';
    const rootPath = adminWindow.REDUX_STATE?.paths?.rootPath ?? '/admin';
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(adminWindow.__APP_STATE__?.errorMessage ?? '');
    const [busy, setBusy] = useState(false);
    const answerForm = useRef<HTMLFormElement>(null);
    const challengeInput = useRef<HTMLInputElement>(null);
    const credentialInput = useRef<HTMLInputElement>(null);

    const supported = typeof PublicKeyCredential !== 'undefined'
        && typeof PublicKeyCredential.parseRequestOptionsFromJSON === 'function';

    const signIn = async (event: FormEvent): Promise<void> => {
        event.preventDefault();
        setError('');
        setBusy(true);
        try {
            const response = await fetch(`${rootPath}/passkey/options`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ email, password }),
            });
            const body: OptionsResponse = await response.json();
            if (!response.ok || !body.challengeId || !body.options) {
                setError(body.detail ?? 'Sign-in failed.');
                return;
            }
            const publicKey = PublicKeyCredential.parseRequestOptionsFromJSON(body.options);
            const credential = await navigator.credentials.get({ publicKey });
            if (!(credential instanceof PublicKeyCredential)) {
                setError('No passkey was used.');
                return;
            }
            // The password is not sent again: the answer form carries only the signature.
            setPassword('');
            if (challengeInput.current && credentialInput.current && answerForm.current) {
                challengeInput.current.value = body.challengeId;
                credentialInput.current.value = JSON.stringify(credential.toJSON());
                answerForm.current.submit();
            }
        } catch (reason) {
            // NotAllowedError: the prompt was cancelled or timed out.
            setError(reason instanceof DOMException && reason.name === 'NotAllowedError'
                ? 'The passkey prompt was cancelled or timed out.'
                : 'Sign-in failed. Start again.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <Box flex variant="grey" height="100%" alignItems="center" justifyContent="center" flexDirection="column">
            <Box bg="white" p="x3" boxShadow="login" width={['100%', '480px']}>
                <H5 marginBottom="lg">Admin panel</H5>
                <H2 fontWeight="lighter">Sign in</H2>
                <Text mb="xl">Your password, then your passkey.</Text>
                {!supported && (
                    <MessageBox my="lg" variant="danger" message="This browser does not support passkeys. Use a current Chrome, Safari, Edge or Firefox." />
                )}
                {error && <MessageBox my="lg" variant="danger" message={error} />}
                <form onSubmit={signIn}>
                    <FormGroup>
                        <Label required>Email</Label>
                        <Input
                            name="email"
                            type="email"
                            autoComplete="username webauthn"
                            value={email}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                        />
                    </FormGroup>
                    <FormGroup>
                        <Label required>Password</Label>
                        <Input
                            name="password"
                            type="password"
                            autoComplete="current-password"
                            value={password}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
                        />
                    </FormGroup>
                    <Text mt="xl" textAlign="center">
                        <Button variant="contained" type="submit" disabled={busy || !supported || !email || !password}>
                            {busy ? 'Waiting for your passkey…' : 'Continue with passkey'}
                        </Button>
                    </Text>
                </form>
                {/* Posted to AdminJS's login handler once the device has signed. */}
                <form ref={answerForm} action={action} method="POST" style={{ display: 'none' }}>
                    <input ref={challengeInput} type="hidden" name="challengeId" />
                    <input ref={credentialInput} type="hidden" name="credential" />
                </form>
            </Box>
        </Box>
    );
};

export default PasskeyLogin;
