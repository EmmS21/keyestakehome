type ErrorBannerProps = {
  message: string;
  onRetry?: () => void;
};

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div className="banner error" data-testid="error-banner" role="alert">
      <span>{message}</span>
      {onRetry ? (
        <button
          type="button"
          className="btn btn-sm"
          data-testid="retry-button"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
