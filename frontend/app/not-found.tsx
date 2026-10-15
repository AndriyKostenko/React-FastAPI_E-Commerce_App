import ErrorPanel from "@/components/ui/ErrorPanel";

export default function NotFound() {
  return <ErrorPanel title="Page not found" message="The page you were looking for does not exist or has moved." />;
}
