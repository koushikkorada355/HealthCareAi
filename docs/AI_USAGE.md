# How AI Was Used in This Project

This is a health booking demo. AI helped in two ways. First, AI helped us build it faster. Second, AI works inside the app to talk to patients and help with booking.

## How we built it with AI help

We used OpenCode as our coding helper. It helped us write new code, fix errors, explain old code, and draft documents quickly.

The helper brain behind OpenCode was Muse Spark version 1.3. It gave ideas, wrote first drafts of code and text, and suggested fixes when things broke.

I checked everything at the end. AI never made the final choice alone. Safety rules, booking checks, and test results were all reviewed by a person.

## Which smart models the app itself uses

The app talks to smart models when a patient chats or speaks. Think of them as three helpers: a thinker, a backup thinker, and an ear. Speaking is done by the browser itself.

- Main thinker: Mercury 2.5. This answers booking questions, understands dates, finds doctors, and plans steps. It is used first for every chat.
- Backup thinker: gpt-oss-120b on Groq. This is used only if the main thinker fails or has no key. It keeps chat working during outages.
- Ear: whisper-large-v3-turbo on Groq. This turns voice into text when you tap the mic and speak.
- Mouth: normal browser voice. This reads answers out loud. It needs no key and no download.

Voice does not change booking logic. It only adds hearing and speaking around the same chat flow. Real slots, verification, and safe booking stay the same.

## What you need to run it

You must add two keys in the settings file. One key is for the main thinker. One key is for Groq, which powers the backup thinker and the ear.

Without keys, chat and voice-to-text will not work. The app will show a safe error instead of guessing. No telephone system and no local download is needed.

## Helper tools used

In simple words, we use LangChain and LangGraph to ask the models, remember short chat history, and move step by step from understanding to booking to reply. We use a common OpenAI-style way of talking so both thinkers work the same way.

## Limits and safety in simple words

Free voice use has daily limits. If too many people speak at once, the app will ask you to wait and retry.

The app does not save voice clips or voice text in logs. Health details stay in safe storage, not in plain logs.

AI can make mistakes. It never invents slots or doctors. It never gives medical advice. It only helps with admin tasks like finding, booking, moving, or cancelling visits. Always let the user confirm the final slot before booking.
