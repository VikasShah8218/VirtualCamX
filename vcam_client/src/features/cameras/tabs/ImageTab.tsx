import { RotateCcw } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useCameraState, usePutSection } from "@/api/queries"
import type { Camera, Imaging } from "@/api/types"
import { ErrorState, Field, Loading, Section } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"

const DEFAULTS: Partial<Imaging> = { brightness: 50, contrast: 50, color_saturation: 50, sharpness: 50 }

/**
 * Image settings apply live while dragging (debounced), like a real camera's web page.
 * In Encode mode brightness / contrast / saturation / IR-cut change the picture without a restart.
 */
export function ImageTab({ camera: c }: { camera: Camera }) {
  const state = useCameraState(c.id)
  const save = usePutSection(c.id, "imaging", null)
  const [img, setImg] = useState<Imaging | undefined>(state.data?.imaging)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const editing = useRef(false)

  useEffect(() => {
    if (!editing.current && state.data) setImg(state.data.imaging)
  }, [state.data])

  if (state.isLoading || !img) return <Loading />
  if (state.isError) return <ErrorState error={state.error} />

  const change = (patch: Partial<Imaging>) => {
    const next = { ...img, ...patch }
    setImg(next)
    editing.current = true
    clearTimeout(timer.current)
    timer.current = setTimeout(() => save.mutate(next, { onSettled: () => { editing.current = false } }), 300)
  }

  const slider = (key: "brightness" | "contrast" | "color_saturation" | "sharpness", label: string) => (
    <Field label={<span className="flex justify-between"><span>{label}</span><span className="tabular-nums">{Math.round(img[key])}</span></span>}>
      <Slider value={[img[key]]} min={0} max={100} step={1} onValueChange={([v]) => change({ [key]: v })} />
    </Field>
  )

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section
        title="Picture"
        description={c.worker.mode === "encode" ? "Changes are visible in the live view above within a second." : "Passthrough mode: values are stored and reported over ONVIF, the picture does not change."}
        actions={<Button variant="ghost" size="xs" onClick={() => change(DEFAULTS)}><RotateCcw /> Defaults</Button>}
      >
        <div className="space-y-4">
          {slider("brightness", "Brightness")}
          {slider("contrast", "Contrast")}
          {slider("color_saturation", "Saturation")}
          {slider("sharpness", "Sharpness")}
        </div>
      </Section>
      <Section title="Day / night and exposure">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Day / Night (IR cut filter)" hint="Night = black and white picture">
            <Select value={img.ir_cut} onValueChange={(v) => change({ ir_cut: v as Imaging["ir_cut"] })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="AUTO">Auto</SelectItem>
                <SelectItem value="ON">Day (color)</SelectItem>
                <SelectItem value="OFF">Night (B/W)</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="WDR">
            <Select value={img.wdr_mode} onValueChange={(v) => change({ wdr_mode: v as "ON" | "OFF" })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="OFF">Off</SelectItem><SelectItem value="ON">On</SelectItem></SelectContent>
            </Select>
          </Field>
          <Field label="Backlight compensation">
            <Select value={img.backlight} onValueChange={(v) => change({ backlight: v as "ON" | "OFF" })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="OFF">Off</SelectItem><SelectItem value="ON">On</SelectItem></SelectContent>
            </Select>
          </Field>
          <Field label="Exposure">
            <Select value={img.exposure_mode} onValueChange={(v) => change({ exposure_mode: v as "AUTO" | "MANUAL" })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="AUTO">Auto</SelectItem><SelectItem value="MANUAL">Manual</SelectItem></SelectContent>
            </Select>
          </Field>
          <Field label="White balance">
            <Select value={img.white_balance} onValueChange={(v) => change({ white_balance: v as "AUTO" | "MANUAL" })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="AUTO">Auto</SelectItem><SelectItem value="MANUAL">Manual</SelectItem></SelectContent>
            </Select>
          </Field>
          <Field label="Focus">
            <Select value={img.focus_mode} onValueChange={(v) => change({ focus_mode: v as "AUTO" | "MANUAL" })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="AUTO">Auto</SelectItem><SelectItem value="MANUAL">Manual</SelectItem></SelectContent>
            </Select>
          </Field>
        </div>
        <div className="mt-4 flex flex-wrap gap-6 text-sm">
          <label className="flex items-center gap-2"><Switch checked={img.mirror} onCheckedChange={(v) => change({ mirror: v })} /> Mirror</label>
          <label className="flex items-center gap-2"><Switch checked={img.flip} onCheckedChange={(v) => change({ flip: v })} /> Flip</label>
          <span className="text-xs text-muted-foreground">Mirror/flip restart the stream.</span>
        </div>
      </Section>
    </div>
  )
}
