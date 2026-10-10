# Speaking in a video

The viewer hears each sentence once, at the speed of the voice, while watching something else. Write
for that.

## The voice says why, the screen shows what

The picture already shows the click, the form and the card. The voice adds what the picture cannot:
why the user does it, what the result means, what would have happened without the product.

| Reads the screen | Says why |
| --- | --- |
| «Как вы видите, здесь появилась карточка с результатом проверки.» | «Через три секунды оператор знает, что договор просрочен, и не звонит клиенту зря.» |
| «Нажимаем кнопку "Проверить".» | «Оператор вставляет номер договора, как делает это сорок раз в день.» |
| "Here you can see the dashboard with all the metrics." | "Every number here comes from last night's run, and each one links to its command." |
| "Let's click on Submit." | "The order goes out only when every field is proved." |

## Sentences

- One thought per sentence. At most 14 words in Russian, 16 in English; the check warns above that.
- Subject and verb first. No chains of participles, no «который, который», no parentheses, no
  lists longer than three.
- Present tense, active voice, «мы» for the team, the product by its name.
- The key word goes at the end of the sentence, where the voice lands: «Ответ «да» ничего не
  записывает.» not «Ничего не записывается при ответе «да».»
- Name the noun at the moment it appears on screen. Write lines in the order of the screen events.

## Numbers and names

- Numbers as spoken words, rounded the way a person says them: «сорок семь секунд вместо двух
  часов», "twenty of twenty". Written words also fix Russian case agreement for TTS.
- Ratios over percentages when the sample is small: «в девятнадцати случаях из двадцати».
- Each number once, with what it was measured on, and the same value as `evidence.md`.
- Addresses spelled as said: «ридбэк точка ру», "readback dot app". The address is also on screen.
- Abbreviations and terms that can be read two ways go to the `## Pronunciation` table at the end of
  the script, and Say uses the spoken form or avoids the term.
- English terms in Russian speech only where the UI shows them; otherwise the Russian word.

## Pace and silence

- Defaults: Russian 120 words per minute, English 150. Speech fills at most 90% of a slot; the rest
  is breath and the screen's own time.
- `[pause]` after a key result: one and a half seconds of silence sells the moment better than a
  sentence about it.
- Demo scenes may be quiet while the product works. Silence over a moving screen is fine; silence
  over a static screen is not.
- At 1.5× playback the speech still has to be clear: no mumbled clauses, no running two ideas into one
  breath.

## Openers and closers

| Never | Instead |
| --- | --- |
| «Всем привет, мы команда…», «В этом видео мы покажем…», «Добро пожаловать» | Start with the moment or the problem: «Оператор тратит два часа на одну заявку.» |
| "Hi everyone, we are team…", "In this video we will show…" | "A wrong drug name is still a real drug name." |
| «Спасибо за внимание», «Спасибо за просмотр» | Name, promise, address: «Ридбэк. Проверьте сами: ридбэк точка ру.» |
| "Thanks for watching" | "Readback. Try the replay at readback dot app." |

The team is named in the close or in the overlay, not in the first seconds.

## Honesty in the voice

- Say what is on screen: «это запись» for a replay, «на синтетических данных» once, «вдвое
  ускорено» for sped-up footage.
- Say what is not measured: «живые голоса мы ещё не мерили». A gap said aloud costs less than one a
  judge finds.
- Never say "AI decides", "high accuracy" or "works for any …" without the number and its scope.

## Words that do not belong

The check fails on openers, screen narration and thanks, and warns on fillers and hype; the lists
are `src/locales/ru/video.json` and `src/locales/en/video.json`. Beyond the lists:

- Russian: «осуществляет», «является», «данный», «производится», «в рамках», «с помощью
  искусственного интеллекта»: replace with a verb a person would say.
- English: "leverage", "utilize", "empower", "streamline", "robust", "in today's world".
- Em dashes, middle dots, arrows and check glyphs never appear in Say: they read as written text, and
  TTS stumbles on them.

## TTS or a human voice

- A human voice: one take per section, the voice-over file on a second screen, the script pace
  measured on the real speaker.
- TTS: the voice-over file is the input. Listen to every number and term once; fix a wrong stress
  by rewording, never by marks inside the script. If the platform asks, the overlay says the voice is
  synthesized.
