type LoadingSpinnerProps = {
  size?: number;
  message?: string;
};

export function LoadingSpinner({ size = 48, message }: LoadingSpinnerProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 'var(--space-md)',
      }}
    >
      <img
        src="/loading.gif"
        alt="Loading"
        width={size}
        height={size}
        style={{ opacity: 0.8 }}
      />
      {message && (
        <p className="text-secondary" style={{ fontSize: '0.875rem' }}>
          {message}
        </p>
      )}
    </div>
  );
}
