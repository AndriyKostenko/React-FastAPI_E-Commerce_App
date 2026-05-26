export type CurrentUserShape = {
    name?: string | null | undefined;
    email?: string | null | undefined;
    image?: string | null | undefined;
};

export interface LoginFormProps {
    currentUser?: CurrentUserShape | null;
}

export interface ReviewAuthorProps {
    id: string;
    name: string;
    email: string;
    role: string;
    image: string;
    createdAt: string;
}
