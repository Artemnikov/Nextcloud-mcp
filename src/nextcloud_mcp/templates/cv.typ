// CV template — call `cv(...)` from a content file (cv-en.typ, cv-he.typ).
// Mirrors the 2-col header (name | subtitle) and 2x2 contact layout.

#let accent = rgb("#1a56b3")
#let muted  = rgb("#5a5a5a")

#let cv(
  name: "",
  title: "",
  contacts: ((),),       // list of rows, each row = (left, right)
  links: (:),            // dict: text -> url (renders as hyperlink)
  body,
  right-to-left: false,
  body-font: ("Lato", "Noto Sans Hebrew"),
  heading-font: ("Lato", "Noto Sans Hebrew"),
) = {
  set document(title: name + " - CV", author: name)
  set page(
    paper: "a4",
    margin: (x: 1.6cm, y: 1.4cm),
  )
  set text(
    font: body-font,
    size: 10pt,
    lang: if right-to-left { "he" } else { "en" },
    dir: if right-to-left { rtl } else { ltr },
  )
  set par(justify: true, leading: 0.55em)

  // Section heading style (used as the function `section()` below)
  show heading.where(level: 2): it => {
    v(0.4em)
    block(
      below: 0.3em,
      stroke: (bottom: 0.6pt + accent),
      inset: (bottom: 0.25em),
      text(
        font: heading-font,
        weight: "semibold",
        size: 12pt,
        fill: accent,
        upper(it.body),
      ),
    )
    v(0.1em)
  }
  show heading.where(level: 3): it => {
    text(font: heading-font, weight: "semibold", size: 10.5pt, it.body)
  }

  // Linkify any text that matches a key in `links`
  show regex("\b(?:linkedin\.com\S+|github\.com\S+|[\w.+-]+@[\w.-]+)"): it => {
    let key = it.text
    if key in links { link(links.at(key))[#it] } else { it }
  }

  // ---- Header: 2-col borderless (name | title) ----
  table(
    columns: (1fr, 1fr),
    stroke: none,
    inset: (x: 0pt, y: 4pt),
    align: (start + horizon, end + horizon),
    text(font: heading-font, size: 26pt, weight: "bold", name),
    text(size: 11pt, fill: muted, title),
  )

  // ---- Contact: NxN borderless (each row = (left, right)) ----
  table(
    columns: (1fr, 1fr),
    stroke: none,
    inset: (x: 0pt, y: 2pt),
    align: (start, end),
    ..contacts.flatten().map(c => text(size: 9.5pt, fill: muted, c))
  )

  v(0.3em)
  line(length: 100%, stroke: 0.4pt + muted.lighten(50%))
  v(0.3em)

  body
}

// Helpers used inside the body
#let role(company, title, period) = {
  block(below: 0.3em, {
    text(weight: "semibold", company)
    h(0.4em); text(fill: muted, [— #title])
    h(1fr)
    text(fill: muted, period)
  })
}

#let bullets(..items) = list(..items.pos().map(i => i))
