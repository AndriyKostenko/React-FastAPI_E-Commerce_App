import { ComponentLoader } from 'adminjs';
import { fileURLToPath } from 'node:url';
const componentLoader = new ComponentLoader();
const source = (file) => fileURLToPath(new URL(`../../src/admin/components/${file}`, import.meta.url));
export const Components = {
    Login: componentLoader.override('Login', source('PasskeyLogin.tsx')),
    WorkflowForm: componentLoader.add('WorkflowForm', source('WorkflowForm.tsx')),
    PrintFile: componentLoader.add('PrintFile', source('PrintFile.tsx')),
    PackingSlip: componentLoader.add('PackingSlip', source('PackingSlip.tsx')),
    ReturnPhotos: componentLoader.add('ReturnPhotos', source('ReturnPhotos.tsx')),
};
export default componentLoader;
