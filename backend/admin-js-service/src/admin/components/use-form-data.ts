import { useEffect, useState } from 'react';
import { ActionProps, ApiClient } from 'adminjs';

const api = new ApiClient();

/**
 * The data a record view's handler loads (its `formData`), fetched once the
 * view opens. AdminJS passes the record to the component but not the rest of
 * the handler's response, so the component asks for it itself.
 */
export const useFormData = <T>({ action, resource, record }: ActionProps): T | null => {
    const [data, setData] = useState<T | null>(null);
    useEffect(() => {
        if (!record) return;
        api.recordAction({ resourceId: resource.id, recordId: record.id, actionName: action.name })
            .then((response) => setData(((response.data as { formData?: T }).formData ?? {}) as T))
            .catch(() => setData({} as T));
    }, [record?.id]);
    return data;
};
