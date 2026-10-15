import Link from "next/link";

interface ErrorPanelProps {
  title: string;
  message: string;
  /** Shown as a "Try again" button when the error can be retried. */
  onRetry?: () => void;
  /** A support reference (Next's error digest), so a report can be matched to the server log. */
  reference?: string;
}

/** The storefront's "something went wrong" card, shared by error and not-found pages. */
const ErrorPanel: React.FC<ErrorPanelProps> = ({ title, message, onRetry, reference }) => (
  <section role="alert" className="glass-card p-8 md:p-12 max-w-xl mx-auto my-8 flex flex-col items-center text-center gap-4">
    <h1 className="font-headline-lg text-primary">{title}</h1>
    <p className="text-secondary">{message}</p>
    <div className="flex flex-wrap justify-center gap-3">
      {onRetry && (
        <button type="button" onClick={onRetry} className="keycap font-label-bold text-sm py-2.5 px-6">
          Try again
        </button>
      )}
      <Link href="/" className="font-label-bold text-sm py-2.5 px-6 rounded-2xl border border-primary/20 text-primary hover:bg-white/40">
        Back to the shop
      </Link>
    </div>
    {reference && <p className="text-xs text-secondary">Reference: <span className="font-mono">{reference}</span></p>}
  </section>
);

export default ErrorPanel;
