import React from 'react';
import { ActionProps } from 'adminjs';
import { Box, Button, Loader, MessageBox } from '@adminjs/design-system';

import { useFormData } from './use-form-data.js';

interface SlipAddress {
    name?: string | null;
    street?: string | null;
    city?: string | null;
    province?: string | null;
    postal_code?: string | null;
    country?: string | null;
    phone?: string | null;
}

interface Slip {
    job_id?: string;
    order_id?: string;
    order_placed_at?: string;
    customer_email?: string;
    merchant_name?: string;
    support_email?: string;
    ship_to?: SlipAddress;
    line?: { product_name: string; quantity: number };
    print_specification?: { size?: string; garment_color?: string; placement?: string; style?: string } | null;
    notes?: string | null;
}

/** The packing slip for one print job, laid out for printing. */
const PackingSlip: React.FC<ActionProps> = (props) => {
    const slip = useFormData<Slip>(props);
    if (slip === null) return <Loader />;
    if (!slip.order_id) return <MessageBox variant="danger" message="The packing slip could not be fetched." />;
    const to = slip.ship_to ?? {};
    const spec = slip.print_specification;
    return (
        <Box variant="container">
            <Box mb="lg" className="no-print">
                <Button variant="contained" onClick={() => window.print()}>Print</Button>
            </Box>
            <div style={{ fontFamily: 'system-ui, sans-serif', lineHeight: 1.5, maxWidth: 640 }}>
                <h2 style={{ margin: '0 0 4px' }}>{slip.merchant_name}</h2>
                <div>Order {slip.order_id} · placed {slip.order_placed_at?.slice(0, 10)}</div>
                <h3 style={{ margin: '20px 0 4px' }}>Ship to</h3>
                <div>{to.name}</div>
                <div>{to.street}</div>
                <div>{[to.city, to.province, to.postal_code].filter(Boolean).join(', ')}</div>
                <div>{to.country}</div>
                {to.phone && <div>{to.phone}</div>}
                <h3 style={{ margin: '20px 0 4px' }}>Contents</h3>
                <div>{slip.line?.quantity} × {slip.line?.product_name}</div>
                {spec && <div>{[spec.size, spec.garment_color, spec.style, spec.placement].filter(Boolean).join(' · ')}</div>}
                {slip.notes && <p>{slip.notes}</p>}
                <p style={{ marginTop: 24 }}>Questions? {slip.support_email}</p>
            </div>
            <style>{'@media print { .no-print, nav, header, aside { display: none !important; } }'}</style>
        </Box>
    );
};

export default PackingSlip;
