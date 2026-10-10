---
name: pitch-video
description: Record, assemble, render and upload the demo or promo video once its script exists — clip list per script section, recording setup, voice-over takes or TTS, overlay labels and captions in the product tokens, a 5-second teaser cut from real footage, assembly and render through the hyperframes plugin, final checks against the platform limits. Use for recording, editing, rendering or uploading a video — «записать видео», «смонтировать видео», «рендер видео», «залить видео», "record the demo", "edit the video", "render the video". The script itself is the `video-script` skill.
---

# Pitch video

The script comes first: skill `video-script` writes `video/script.<lang>.md`, the plain voice-over
`video/voice-over.<lang>.md` and the captions `video/captions.<lang>.srt`. This skill turns them into
the uploaded file. Nothing is claimed in the cut that the script does not say.

## 1. Before recording

- `npm run video:check -- --strict` passes and `npm run video:shots` passes on the stand that will
  be recorded.
- The stand runs the build that is submitted (same commit as the repository tag), seeded with the
  demo data, in the video language and theme.
- `context/PLATFORM.md` limits are at the top of the script: duration, resolution, format, language,
  where it is uploaded and with what visibility.

## 2. Recording

- Screen at 1920×1080, 30 fps or more, exported at least at 720p. Browser in a clean profile: no
  notifications, no bookmarks bar, no extensions, no secrets, no local paths, zoom 100%.
- One raw clip per script section, named `NN-part.mp4`, with one second of stillness at the start
  and the end of each clip for cuts.
- The cursor moves slowly along the path written in Screen and rests where the script says hold.
- Interactive parts follow `video/live-dialogue.<lang>.md`; record two takes and keep the one where
  the product answered as scripted.
- A live part that cannot be repeated reliably is recorded as a replay and labelled `replay` or
  `запись`, never `live`.

## 3. Voice

- Human voice: external microphone, quiet room, one take per section read from the voice-over file,
  peaks under clipping, the same distance to the microphone across takes.
- TTS: the voice-over file is the input, one file per section; listen to every number and term.
- The voice-over is cut per section and aligned so each Say line starts at its screen event.

## 4. Assembly and render

Assemble with the `hyperframes` plugin (entry skill `hyperframes`; the product-launch or general
video workflow):

- clips on the timeline in script order, the teaser cut from the section 5 take placed first;
- overlay labels exactly as the Overlay lines say, in the product fonts and colors, same corner in
  every scene;
- captions from `captions.<lang>.srt`, burned in for muted autoplay, retimed to the real voice;
- zooms where Screen asks for them, no transitions longer than 300 ms, no stock music over speech;
- the close holds the address on screen for at least 3 seconds.

Render to MP4 (H.264, AAC). After the cut, take the real section timecodes from the timeline and
put them back into the script headings, then run `npm run video:check -- --retime`.

## 5. Checks

The upload uses the thumbnail and title picked by `video-thumbnail`; the first two lines of the
description carry the promise and the stand URL.

Watch the whole file at 1× with sound and once muted at 1.5×: duration within limits, labels visible
and true, every number equal to `evidence.md`, captions match the voice, nothing private on screen,
the address in the close works. Upload, then open the link in a private window without logging in.

Done when the uploaded video plays logged out, fits every constraint from `context/PLATFORM.md`,
and the script, voice-over and captions match the final cut.
