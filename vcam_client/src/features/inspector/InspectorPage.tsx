import { PageHeader } from "@/components/common"
import { InspectorView } from "./InspectorView"

export function InspectorPage() {
  return (
    <>
      <PageHeader title="ONVIF Inspector" description="Every ONVIF request NVRs sent to the virtual cameras, with the full SOAP XML. Failures are red." />
      <InspectorView />
    </>
  )
}
