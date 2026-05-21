import Link from "next/link";

type Props = {
  params: Promise<{ datasetId: string }>;
};

export default async function CleaningWorkspacePage({ params }: Props) {
  const { datasetId } = await params;

  return (
    <div data-testid="workspace-shell" className="workspace-shell">
      <p>
        Cleaning workspace for dataset <strong>{datasetId}</strong>
      </p>
      <p style={{ marginTop: 12, fontSize: "0.85rem", color: "#666" }}>
        Full workspace UI is coming in the next page.
      </p>
      <p style={{ marginTop: 16 }}>
        <Link href="/" className="link">
          ← Explorer
        </Link>
      </p>
    </div>
  );
}
