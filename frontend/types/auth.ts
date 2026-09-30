export type CurrentUserShape = {
    name?: string | null | undefined;
    email?: string | null | undefined;
    image?: string | null | undefined;
};

export interface LoginFormProps {
    currentUser?: CurrentUserShape | null;
    /** A failed sign-in redirected here with this message (login page only). */
    authError?: string;
}

export type SearchParams = Record<string, string | string[] | undefined>;

export interface ReviewAuthorProps {
    id: string;
    name: string;
    email: string;
    role: string;
    image: string;
    createdAt: string;
}
