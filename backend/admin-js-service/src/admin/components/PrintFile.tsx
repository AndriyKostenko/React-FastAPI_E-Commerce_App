import React from 'react';
import { ActionProps } from 'adminjs';
import { Box, Button, H4, Loader, MessageBox, Text } from '@adminjs/design-system';

import { useFormData } from './use-form-data.js';

/** A print job's artwork: preview, download and the facts the print is checked against. */
interface Artwork {
    download_url?: string;
    filename?: string;
    sha256?: string;
    width_px?: number;
    height_px?: number;
    embedded_dpi?: number;
    expires_in_seconds?: number;
}

const PrintFile: React.FC<ActionProps> = (props) => {
    const artwork = useFormData<Artwork>(props);
    if (artwork === null) return <Loader />;
    if (!artwork.download_url) return <MessageBox variant="danger" message="The print file could not be fetched." />;
    return (
        <Box variant="container">
            <H4>{artwork.filename}</H4>
            <Text mb="lg">
                {artwork.width_px} × {artwork.height_px} px at {artwork.embedded_dpi} DPI · SHA-256 {artwork.sha256}
            </Text>
            {/* A checkerboard behind it shows the transparent backdrop. */}
            <Box
                mb="lg"
                style={{
                    maxWidth: 480,
                    background: 'repeating-conic-gradient(#ddd 0% 25%, #fff 0% 50%) 50% / 20px 20px',
                }}
            >
                <img src={artwork.download_url} alt="Print file" style={{ width: '100%', display: 'block' }} />
            </Box>
            <Button as="a" href={artwork.download_url} download={artwork.filename} variant="contained">
                Download print file
            </Button>
            <Text variant="sm" mt="default">
                The link expires in {Math.round((artwork.expires_in_seconds ?? 0) / 60)} minutes; reopen this view for a new one.
            </Text>
        </Box>
    );
};

export default PrintFile;
