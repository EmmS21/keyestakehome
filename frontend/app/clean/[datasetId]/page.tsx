import { CleaningWorkspacePage } from "@/components/CleaningWorkspacePage";

type Props = {
  params: Promise<{ datasetId: string }>;
};

export default async function CleaningWorkspaceRoute({ params }: Props) {
  const { datasetId } = await params;
  return <CleaningWorkspacePage datasetId={datasetId} />;
}
