import { useEffect, useRef, useState } from 'react';
import { Check, Copy } from 'lucide-react';

const toBlob = canvas => new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG export failed')), 'image/png'));
async function download(canvas, name) {
  const url = URL.createObjectURL(await toBlob(canvas)); const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
}

export default function CopyImageButton({ label, image, filename, onNotice }) {
  const [state, setState] = useState('idle'), timer = useRef(null), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; clearTimeout(timer.current); }; }, []);
  async function copy() {
    clearTimeout(timer.current);
    setState('copying');
    let result;
    try {
      if (!navigator.clipboard?.write || !window.ClipboardItem) throw new Error('Clipboard unavailable');
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': toBlob(image()) })]);
      result = 'copied';
    } catch {
      try { await download(image(), filename); result = 'downloaded'; onNotice('Image clipboard unavailable; PNG downloaded instead.'); }
      catch (error) { result = 'idle'; onNotice(error.message); }
    }
    if (!mounted.current) return;
    setState(result);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { if (mounted.current) setState('idle'); }, 1000);
  }
  return <button className={`response-button energy-copy-button ${state === 'copied' ? 'is-copied' : ''}`} disabled={state === 'copying'} onClick={copy} aria-label={state === 'idle' ? label : `${label}: ${state}`}>
    {state === 'copied' ? <Check size={14} /> : <Copy size={14} />}<span aria-live="polite">{state === 'copied' ? 'Copied' : state === 'copying' ? 'Copying…' : state === 'downloaded' ? 'Downloaded' : 'Copy'}</span>
  </button>;
}
