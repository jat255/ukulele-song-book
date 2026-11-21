# AI conversion settings

Open Settings → Configure AI conversion. The dialog manages one active service.
Choose Anthropic or OpenAI-compatible, enter the service name, API base URL and
an image-capable model ID, and supply a key if required. The NVIDIA preset uses
`https://integrate.api.nvidia.com/v1`; supply the exact vision model ID from your
NVIDIA account. Available models, credits, quotas and pricing are provider/account
dependent. The app does not promise a free tier or universal model compatibility.

OpenAI-compatible services use Chat Completions with inline PNG image content.
Use the API base URL without `/chat/completions`. HTTPS is required except for
HTTP loopback endpoints (`localhost`, `127.0.0.1`, `::1`). In a container,
loopback refers to that container. URL credentials, query parameters and redirects
are not supported. Custom services must accept image requests and return a
complete JSON draft with `source` and `uncertainties`; providers/models that do
not support this contract return a visible failure rather than fabricated music.

Saving settings never contacts the service. **Enable AI conversion** makes it
available for future imports; each import still requires explicit authorization
of the selected pages and service/model. At most five full pages can be submitted
per request. Cropped AI imports are not supported. Ordinary local PDF extraction
does not contact an AI service. Output always enters draft review.

**Test connection** requires saved settings and a separate synthetic-image
checkbox. It sends only an app-generated test image, can consume provider credits,
and does not send library content. A successful test means that a structured
draft was returned; it does not establish real-song transcription quality.
Settings can be tested while conversion is disabled. Save changes and reopen the
dialog before testing. Development verification uses HTTP mock transports and
browser interception; no live model or account has been verified.

Keys are sent only to the local API when saved. Responses contain only a saved-key
indicator. Leave the field blank to retain a key, enter a new key to replace it,
or select Remove saved key. Changing protocol or endpoint drops an old retained
key so it cannot be forwarded to a different service. Each save creates a new
configuration revision. Jobs authorized under an old revision fail rather than
silently using the new endpoint/model/key; submit a fresh import with new consent.
An HTTP request already in flight cannot be recalled by disabling the service.

The server stores settings, including the key, in `.ai-provider.json` inside the
managed library volume. Writes use atomic replacement, fsync and owner-only
0600 permissions. **This file is not encrypted.** Protect access to the volume.
The file is excluded from both portable exports and operational backup archives;
restore requires re-entering this configuration and credentials separately.
No secrets are stored in browser local storage, canonical music, or export metadata.
Do not add the private configuration file to git or public artifacts.

API and worker load the same configuration. Saving takes effect for new jobs
without a worker restart. Before any saved configuration exists, the existing
`SONGBOOK_ALLOW_EXTERNAL_AI`, `ANTHROPIC_API_KEY` and `SONGBOOK_ANTHROPIC_MODEL`
environment settings remain supported. Once a configuration is saved, it takes
precedence, including an explicit disabled setting. A corrupt private settings
file reports unavailable and does not enable a fallback provider; restore that
file from a protected operator copy or remove it deliberately to use environment
configuration again.

The provider endpoint format follows NVIDIA's multimodal API documentation:
https://docs.nvidia.com/nim/large-language-models/latest/advanced-use-cases/multimodal-input.html

## Chord placement and trying again

Both adapters now share the `chord-placement-v3` transcription prompt. It teaches
inline character/syllable anchoring with authored synthetic examples, including
changes inside a word. It asks the model to separate source columns, preserve
chord/lyric row association, avoid spacing-based guesses with proportional fonts,
and check that removing inserted chord markers leaves the lyrics unchanged.
Ambiguous placement is retained as a nearby chord-only line with a review note,
rather than presented as a confident attachment. This is still a model-produced
draft: mock request tests establish that instructions are sent, not that a live
model follows them. No before/after real-song alignment accuracy was measured.

For an unwanted attempt, use **Discard attempt** in the import queue. It removes
only unaccepted drafts. Managed originals, accepted songs and accepted import
provenance remain. If a multi-song import is partially accepted, its accepted
history remains in the queue. Processing attempts cannot be discarded; wait
until processing finishes. A changed draft or acceptance in progress produces
a conflict rather than silently removing newer work.

**Start over** discards pending work and prepares the retained source for a new
import, preserving the unaccepted page/crop selection without requiring another
upload. Review the settings and click Import source. AI is deliberately off for
this new attempt until you select the external-submission checkbox again. Merely
preparing a retry does not contact a provider. A new AI submission may consume
credits. Existing drafts are not rewritten when the prompt changes.
