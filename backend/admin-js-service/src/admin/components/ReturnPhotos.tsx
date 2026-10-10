import React from 'react';
import { ActionProps } from 'adminjs';
import { Box, Loader, Text } from '@adminjs/design-system';

import { useFormData } from './use-form-data.js';

interface Photos {
    urls?: string[];
}

/** The customer's evidence photos, streamed through admin-js (see http/return-photo-route.ts). */
const ReturnPhotos: React.FC<ActionProps> = (props) => {
    const photos = useFormData<Photos>(props);
    if (photos === null) return <Loader />;
    if (!photos.urls?.length) return <Text>No photos were sent with this return.</Text>;
    return (
        <Box variant="container" flex flexWrap="wrap">
            {photos.urls.map((url) => (
                <a key={url} href={url} target="_blank" rel="noreferrer" style={{ margin: 8 }}>
                    <img src={url} alt="Return evidence" style={{ maxWidth: 320, maxHeight: 320, display: 'block' }} />
                </a>
            ))}
        </Box>
    );
};

export default ReturnPhotos;
