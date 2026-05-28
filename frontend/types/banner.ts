export interface TShirtPreviewProps {
    color: "bg-white" | "bg-gray" | "bg-black";
    placement: string;
    designUrl: string;
    isGenerating?: boolean;
}
