# Documentation claim auditor

An offline auditor comparing documentation promises with Python call patterns.
Sources are parsed without execution. No network, telemetry, or file writes are used.

## Usage

```sh
python3 -m pip install .
image-style-transfer-claim-audit audit .
python3 -m image_style_transfer_claim_audit audit . --json
image-style-transfer-claim-audit audit . --fail-on medium --ignore vendor --ignore build
image-style-transfer-claim-audit --version
```

The default directory is the current directory. Root README.md and Markdown files
with a docs path component are checked. Fenced blocks are excluded; inline code
counts. Repeated ignore options exclude relative path prefixes. The default failure
threshold is high. Exit status is 0 below the threshold, 2 at or above it, and 1
for usage or I/O errors. JSON contains a verdict and findings with messages.
Verbose output includes evidence paths.

```text
documented-image-style-transfer-claim-false HIGH
documented-image-style-transfer-claim-false MEDIUM (test evidence only)
documented-no-image-style-transfer-claim-false HIGH
```

## Differentiation

The adjacent tools check different operations:

```text
image-generation-claim-audit: generating a new image from text or noise,
never a content-plus-style combination.
image-colorization-claim-audit: adding colour to a greyscale image,
no style reference image.
image-inpainting-claim-audit: filling missing regions, no style reference image.
super-resolution-claim-audit: upscaling, no style reference image.
image-denoising-claim-audit: removing noise, no style reference image.
```

## Honest limitations

The documented matching hazards are reproduced below.

```text
- The bare phrase "style transfer" is deliberately a STYLETRANSFER
  phrase: in image-tool docs it almost always names restyling a
  photo. A doc that means transferring a writing style, a coding
  style, or a design-system style is a false positive; the same
  accepted shape as other families' short phrases.
- "stylized images" / "stylised images" are deliberately phrases:
  they can describe a design choice (a stylised icon set) rather
  than a computed restyling. The tool flags the claim; only the
  code decides.
- "pencil sketch effect", "pencil sketch filter", "oil painting
  effect", "oil painting filter", "watercolor effect", and "cartoon
  effect" are deliberately phrases: they can describe a preset
  label in an editor UI rather than a computed operation. The tool
  flags the claim; only the code decides.
- "van gogh style", "picasso style", and "monet style" are
  deliberately phrases: they can describe a colour palette or a
  theme name rather than a style-transfer operation. The tool flags
  the claim; only the code decides.
- A generic `stylize(` / `stylise(` call can name a CSS helper or
  a text formatter rather than an image operation: same rule — the
  tool counts the call, the claim plus the code decide.
- A generic `oil_painting(` / `oil_paint(` call can name a brush
  preset in a drawing app rather than a photo operation: same rule.
- A generic `adain(` call names the AdaIN operation only by
  convention; an unrelated function that happens to share the name
  is counted, and the claim plus the code decide.
- A hand-rolled Gatys neural style transfer (VGG feature extractor
  plus Gram matrix plus an optimisation loop over the image, with
  no named style function) is NOT detected: the tool covers the
  OpenCV / Magenta / TransformerNet routes plus the listed generic
  names only. Say so in the README.
- A CycleGAN / pix2pix image-to-image translation pipeline is
  covered only if it uses a listed generic name (for example a
  function named `style_transfer`); a bare CycleGANModel
  construction with no listed call is NOT evidence, and `cyclegan`
  alone is not a listed generic name. Say so in the README.
- As with every family: static pattern matching, not semantic
  judgement; dead code counts; alias chains the tracer cannot follow
  are missed; exact phrases only, not semantics; denial handling
  depends on the denial phrase list; each pair must sit in a single
  module.
```
