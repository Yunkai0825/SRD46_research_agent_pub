// Download what only claude.ai can serve for build_renderings.py: the image previews Claude
// saw with the view tool, and output files (e.g. published HTML) that no export has.
//
// Use: open https://claude.ai while logged in, DevTools > Console, paste this whole file, press Enter.
// When prompted, paste the contents of Renderings/_plan/fetch_list.json. A file named
// claude_assets.zip is downloaded, containing view_images/<file_uuid>.<ext> and
// outputs/<chat_id>/<path>. Only GET requests are made; nothing in your chats changes.
(async () => {
  const list = JSON.parse(prompt('Paste fetch_list.json') || '{"view_images":[],"outputs":[]}');
  const orgs = await fetch('/api/organizations').then(r => r.json());
  const org = (orgs.find(o => (o.capabilities || []).includes('chat')) || orgs[0]).uuid;

  const crcTable = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = u8 => { let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = crcTable[(c ^ u8[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  async function buildZip(entries) {
    const enc = new TextEncoder(), parts = [], central = []; let offset = 0;
    for (const e of entries) {
      const data = new Uint8Array(await e.blob.arrayBuffer()), crc = crc32(data), name = enc.encode(e.name);
      const lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true);
      lh.setUint32(14, crc, true); lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true); lh.setUint16(26, name.length, true);
      parts.push(lh.buffer, name, data);
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true);
      ch.setUint32(16, crc, true); ch.setUint32(20, data.length, true); ch.setUint32(24, data.length, true); ch.setUint16(28, name.length, true); ch.setUint32(42, offset, true);
      central.push(ch.buffer, name); offset += 30 + name.length + data.length;
    }
    const size = central.reduce((a, b) => a + (b.byteLength ?? b.length), 0), end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true); end.setUint32(12, size, true); end.setUint32(16, offset, true);
    return new Blob([...parts, ...central, end.buffer], { type: 'application/zip' });
  }

  const entries = [], failed = [];
  for (const u of list.view_images) {
    const r = await fetch(`/api/${org}/files/${u}/preview`);
    if (r.ok) { const b = await r.blob(); entries.push({ name: `view_images/${u}.${b.type.split('/')[1] || 'img'}`, blob: b }); } else failed.push(['view', u, r.status]);
  }
  for (const [cid, path] of list.outputs) {
    const r = await fetch(`/api/organizations/${org}/conversations/${cid}/wiggle/download-file?path=${encodeURIComponent(path)}`);
    if (r.ok) entries.push({ name: `outputs/${cid}${path}`, blob: await r.blob() }); else failed.push(['output', cid, path, r.status]);
  }
  entries.push({ name: 'fetch_report.json', blob: new Blob([JSON.stringify({ fetched: entries.length, failed }, null, 1)]) });
  const zip = await buildZip(entries), a = document.createElement('a');
  a.href = URL.createObjectURL(zip); a.download = 'claude_assets.zip'; document.body.appendChild(a); a.click(); a.remove();
  console.log(`claude_assets.zip: ${entries.length - 1} files, ${failed.length} failed`, failed);
})();
