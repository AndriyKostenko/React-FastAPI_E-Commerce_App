import React, { FormEvent, useEffect, useState } from 'react';
import { ActionProps, ApiClient, useActionResponseHandler } from 'adminjs';
import {
    Box, Button, CheckBox, FormGroup, Input, Label, Loader, MessageBox, Table, TableBody, TableCell, TableHead, TableRow, Text, TextArea,
} from '@adminjs/design-system';

/**
 * The form of a workflow action (resources/workflow-action.ts): the fields
 * come from the action's `custom.fields`, and the answer is posted back to
 * the same action, which calls the service. A confirmation-only action has
 * no fields and is just this description and a button.
 */

type FieldKind = 'text' | 'textarea' | 'boolean' | 'number' | 'refund-lines';

interface FormField {
    name: string;
    label: string;
    kind: FieldKind;
    required?: boolean;
    help?: string;
}

interface WorkflowCustom {
    label?: string;
    description?: string;
    fields?: FormField[];
}

/** One order line the refund form can give back. */
interface RefundableLine {
    id: string;
    label: string;
    quantity: number;
    price: string;
}

interface FormData {
    lines?: RefundableLine[];
}

type LineQuantities = Record<string, number>;
type Values = Record<string, string | number | boolean | Array<{ order_item_id: string; quantity: number }>>;

const api = new ApiClient();

const WorkflowForm: React.FC<ActionProps> = ({ action, resource, record }) => {
    const custom = action.custom as WorkflowCustom;
    const fields = custom.fields ?? [];
    const handleResponse = useActionResponseHandler();
    const [values, setValues] = useState<Record<string, string | boolean>>({});
    const [quantities, setQuantities] = useState<LineQuantities>({});
    const [formData, setFormData] = useState<FormData | null>(null);
    const [busy, setBusy] = useState(false);
    const needsData = fields.some((field) => field.kind === 'refund-lines');

    useEffect(() => {
        if (!needsData || !record) return;
        api.recordAction({ resourceId: resource.id, recordId: record.id, actionName: action.name })
            .then((response) => setFormData((response.data as { formData?: FormData }).formData ?? {}))
            .catch(() => setFormData({}));
    }, [needsData, record?.id]);

    if (!record) return null;

    const submit = async (event: FormEvent): Promise<void> => {
        event.preventDefault();
        setBusy(true);
        const payload: Values = { ...values };
        fields.filter((field) => field.kind === 'refund-lines').forEach((field) => {
            payload[field.name] = Object.entries(quantities)
                .filter(([, quantity]) => quantity > 0)
                .map(([orderItemId, quantity]) => ({ order_item_id: orderItemId, quantity }));
        });
        try {
            const response = await api.recordAction({
                resourceId: resource.id,
                recordId: record.id,
                actionName: action.name,
                // One JSON field: AdminJS would otherwise flatten nested values.
                data: { input: JSON.stringify(payload) },
            });
            handleResponse(response);
        } finally {
            setBusy(false);
        }
    };

    const renderField = (field: FormField): React.ReactNode => {
        switch (field.kind) {
            case 'boolean':
                return (
                    <Box flex alignItems="center">
                        <CheckBox
                            id={field.name}
                            checked={values[field.name] === true}
                            onChange={() => setValues({ ...values, [field.name]: values[field.name] !== true })}
                        />
                        <Label inline htmlFor={field.name} ml="default">{field.label}</Label>
                    </Box>
                );
            case 'textarea':
                return (
                    <TextArea
                        width={1}
                        rows={3}
                        value={String(values[field.name] ?? '')}
                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setValues({ ...values, [field.name]: e.target.value })}
                    />
                );
            case 'refund-lines':
                if (formData === null) return <Loader />;
                if (!formData.lines?.length) return <Text>This order has no lines.</Text>;
                return (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableCell>Line</TableCell>
                                <TableCell>Ordered</TableCell>
                                <TableCell>Price</TableCell>
                                <TableCell>Refund quantity</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {formData.lines.map((line) => (
                                <TableRow key={line.id}>
                                    <TableCell>{line.label}</TableCell>
                                    <TableCell>{line.quantity}</TableCell>
                                    <TableCell>{line.price}</TableCell>
                                    <TableCell>
                                        <Input
                                            type="number"
                                            min={0}
                                            max={line.quantity}
                                            value={quantities[line.id] ?? 0}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuantities({
                                                ...quantities,
                                                [line.id]: Math.max(0, Math.min(line.quantity, Number(e.target.value) || 0)),
                                            })}
                                        />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                );
            default:
                return (
                    <Input
                        width={1}
                        type={field.kind === 'number' ? 'number' : 'text'}
                        value={String(values[field.name] ?? '')}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setValues({ ...values, [field.name]: e.target.value })}
                    />
                );
        }
    };

    return (
        <Box as="form" onSubmit={submit} variant="container">
            {custom.description && <MessageBox mb="xl" variant="info" message={custom.description} />}
            {fields.map((field) => (
                <FormGroup key={field.name}>
                    {field.kind !== 'boolean' && <Label required={field.required}>{field.label}</Label>}
                    {renderField(field)}
                    {field.help && <Text variant="sm" mt="sm">{field.help}</Text>}
                </FormGroup>
            ))}
            <Button type="submit" variant={action.variant === 'danger' ? 'danger' : 'contained'} disabled={busy}>
                {busy ? 'Working…' : custom.label ?? action.label}
            </Button>
        </Box>
    );
};

export default WorkflowForm;
