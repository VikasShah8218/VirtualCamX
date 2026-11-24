/** Pretty-print XML (SOAP envelopes) with 2-space indentation. Falls back to the input on parse errors. */
export function prettyXml(xml: string): string {
  if (!xml.trim()) return ""
  const doc = new DOMParser().parseFromString(xml, "application/xml")
  if (doc.getElementsByTagName("parsererror").length) return xml
  const out: string[] = []
  const walk = (node: Node, depth: number) => {
    const pad = "  ".repeat(depth)
    if (node.nodeType === Node.TEXT_NODE) {
      const t = node.textContent?.trim()
      if (t) out.push(pad + escapeText(t))
      return
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return
    const el = node as Element
    const attrs = Array.from(el.attributes).map((a) => ` ${a.name}="${escapeAttr(a.value)}"`).join("")
    const kids = Array.from(el.childNodes).filter((n) => n.nodeType === Node.ELEMENT_NODE || n.textContent?.trim())
    if (kids.length === 0) out.push(`${pad}<${el.tagName}${attrs}/>`)
    else if (kids.length === 1 && kids[0].nodeType === Node.TEXT_NODE) out.push(`${pad}<${el.tagName}${attrs}>${escapeText(kids[0].textContent!.trim())}</${el.tagName}>`)
    else {
      out.push(`${pad}<${el.tagName}${attrs}>`)
      kids.forEach((k) => walk(k, depth + 1))
      out.push(`${pad}</${el.tagName}>`)
    }
  }
  walk(doc.documentElement, 0)
  return out.join("\n")
}

const escapeText = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
const escapeAttr = (s: string) => escapeText(s).replace(/"/g, "&quot;")

export interface XmlToken {
  kind: "tag" | "attr" | "value" | "text" | "punct"
  text: string
}

/** Tiny tokenizer for coloring pretty-printed XML (tags, attribute names, values, text). */
export function tokenizeXml(xml: string): XmlToken[] {
  const tokens: XmlToken[] = []
  const re = /(<\/?)([\w:.-]+)|([\w:.-]+)(=)("[^"]*")|(\/?>)|([^<]+)/g
  let m: RegExpExecArray | null
  let inTag = false
  while ((m = re.exec(xml))) {
    if (m[1]) {
      tokens.push({ kind: "punct", text: m[1] }, { kind: "tag", text: m[2] })
      inTag = true
    } else if (m[3] && inTag) {
      tokens.push({ kind: "attr", text: m[3] }, { kind: "punct", text: m[4] }, { kind: "value", text: m[5] })
    } else if (m[6]) {
      tokens.push({ kind: "punct", text: m[6] })
      inTag = false
    } else {
      tokens.push({ kind: inTag ? "punct" : "text", text: m[0] })
    }
  }
  return tokens
}
