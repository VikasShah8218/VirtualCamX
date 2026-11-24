import { useCameraState, usePutSection } from "@/api/queries"
import type { Camera, StreamOptions, VideoEncoder } from "@/api/types"
import { ErrorState, Field, Loading, Section } from "@/components/common"
import { SaveBar } from "@/components/SaveBar"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { useDraft } from "@/lib/useDraft"

const FPS = [1, 2, 3, 5, 8, 10, 12, 15, 20, 25, 30]

export function StreamsTab({ camera: c }: { camera: Camera }) {
  const state = useCameraState(c.id)
  const save = usePutSection(c.id, "video_encoders", "Streams saved (clients reconnect)")
  const { draft, setDraft, dirty, reset, saved } = useDraft(state.data?.video_encoders)

  if (state.isLoading || !draft) return <Loading />
  if (state.isError) return <ErrorState error={state.error} />
  const options = state.data!.capabilities.stream_options

  const update = (token: string, patch: Partial<VideoEncoder>) => setDraft((list) => list.map((e) => (e.token === token ? { ...e, ...patch } : e)))

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {draft.map((e) => <EncoderCard key={e.token} e={e} opts={options[e.stream_key]} onChange={(p) => update(e.token, p)} />)}
      </div>
      <SaveBar dirty={dirty} saving={save.isPending} note="Saving restarts the stream: NVRs reconnect, like on a real camera." onReset={reset} onSave={() => save.mutate(draft, { onSuccess: saved })} />
    </>
  )
}

function EncoderCard({ e, opts, onChange }: { e: VideoEncoder; opts?: StreamOptions; onChange: (p: Partial<VideoEncoder>) => void }) {
  const resolutions = opts?.resolutions ?? [[e.width, e.height]]
  const encodings = opts?.encodings ?? ["H264"]
  const fpsList = FPS.filter((f) => f <= (opts?.max_fps ?? 30))
  const isH26x = e.encoding !== "JPEG"
  return (
    <Section title={<span className="capitalize">{e.stream_key} stream</span>} description={`${e.token} · ONVIF name "${e.name}"`}>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Codec">
          <Select value={e.encoding} onValueChange={(v) => onChange({ encoding: v as VideoEncoder["encoding"] })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{encodings.map((x) => <SelectItem key={x} value={x}>{x === "JPEG" ? "MJPEG" : x}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="Resolution">
          <Select value={`${e.width}x${e.height}`} onValueChange={(v) => { const [w, h] = v.split("x").map(Number); onChange({ width: w, height: h }) }}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{resolutions.map(([w, h]) => <SelectItem key={`${w}x${h}`} value={`${w}x${h}`}>{w}×{h}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="Frame rate">
          <Select value={String(e.fps)} onValueChange={(v) => onChange({ fps: Number(v) })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{fpsList.map((f) => <SelectItem key={f} value={String(f)}>{f} fps</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="Bitrate control">
          <Select value={e.rc_mode} onValueChange={(v) => onChange({ rc_mode: v as "CBR" | "VBR" })} disabled={!isH26x}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="CBR">CBR (constant)</SelectItem><SelectItem value="VBR">VBR (variable)</SelectItem></SelectContent>
          </Select>
        </Field>
        <Field label={`Bitrate ${e.rc_mode === "VBR" ? "limit " : ""}(kbps)`} hint={opts ? `${opts.bitrate_min_kbps}–${opts.bitrate_max_kbps}` : undefined}>
          <Input type="number" min={opts?.bitrate_min_kbps} max={opts?.bitrate_max_kbps} value={e.bitrate_kbps} onChange={(ev) => onChange({ bitrate_kbps: Number(ev.target.value) || 0 })} />
        </Field>
        <Field label="GOP / I-frame interval" hint={`${(e.gov_length / Math.max(1, e.fps)).toFixed(1)} s`}>
          <Input type="number" min={1} max={400} value={e.gov_length} onChange={(ev) => onChange({ gov_length: Number(ev.target.value) || 1 })} disabled={!isH26x} />
        </Field>
        {e.encoding === "H264" && (
          <Field label="H.264 profile">
            <Select value={e.h264_profile} onValueChange={(v) => onChange({ h264_profile: v as VideoEncoder["h264_profile"] })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{["Baseline", "Main", "High"].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
            </Select>
          </Field>
        )}
        <Field label={`Quality ${e.quality}`} className="col-span-2" hint="Used by VBR and MJPEG (1 = smallest, 10 = best)">
          <Slider value={[e.quality]} min={1} max={10} step={1} onValueChange={([v]) => onChange({ quality: v })} />
        </Field>
      </div>
    </Section>
  )
}
