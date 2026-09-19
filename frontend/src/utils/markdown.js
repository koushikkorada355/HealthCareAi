/* Shared mini-markdown renderer. Escapes raw HTML first so AI/server text
   can never inject markup (XSS-safe), then applies **bold**, `code`,
   [label](/relative-path) links and newlines. */
export function renderSafe(text) {
  const esc = String(text ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  return esc
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code class="bg-slate-100 px-1 rounded">$1</code>')
    .replace(/\[([^\]]+)\]\((\/[^)]+)\)/g, '<a href="$2" class="font-bold text-brand-deep underline">$1</a>')
    .replace(/\n/g, '<br/>')
}

/* Strip markdown for speech synthesis. */
export function plainForSpeech(text) {
  return String(text ?? '')
    .replace(/\*\*(.+?)\*\*/g, '$1').replace(/`(.+?)`/g, '$1')
    .replace(/\[([^\]]+)\]\((\/[^)]+)\)/g, '$1')
    .replace(/[*_`#]/g, '')
}
