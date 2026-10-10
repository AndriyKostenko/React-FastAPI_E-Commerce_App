import { ComponentLoader } from 'adminjs';
import { fileURLToPath } from 'node:url';

const componentLoader = new ComponentLoader();

// Components are bundled for the browser by AdminJS from their TSX source,
// not from tsc's output, so the paths point into src/.
const source = (file: string): string => fileURLToPath(new URL(`../../src/admin/components/${file}`, import.meta.url));

export const Components = {
    // Password, then passkey: replaces AdminJS's email/password form.
    Login: componentLoader.override('Login', source('PasskeyLogin.tsx')),
    // The form of every workflow action (refund, return decisions, print queue steps).
    WorkflowForm: componentLoader.add('WorkflowForm', source('WorkflowForm.tsx')),
    PrintFile: componentLoader.add('PrintFile', source('PrintFile.tsx')),
    PackingSlip: componentLoader.add('PackingSlip', source('PackingSlip.tsx')),
    ReturnPhotos: componentLoader.add('ReturnPhotos', source('ReturnPhotos.tsx')),
};

export default componentLoader;
