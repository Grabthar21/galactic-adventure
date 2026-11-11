"""Make a Godot web export publishable on the artifact host.
The host only serves certain file types and caps files at 20 MiB, so:
- index.wasm is gzipped, then stored as base64 text in index.wasm.gz.b64.js
- index.pck is stored as base64 text in index.pck.b64.js
A small fetch shim in index.html decodes them in the browser before Godot sees them."""
import base64, gzip, os, sys
d = sys.argv[1]
def pack(src, dst, compress):
    data = open(src, 'rb').read()
    if compress:
        data = gzip.compress(data, compresslevel=9)
    open(dst, 'w').write(base64.b64encode(data).decode('ascii'))
    os.remove(src)
pack(os.path.join(d, 'index.wasm'), os.path.join(d, 'index.wasm.gz.b64.js'), True)
pack(os.path.join(d, 'index.pck'), os.path.join(d, 'index.pck.b64.js'), False)
shim = """<script>
(function(){
  const orig = window.fetch.bind(window);
  function bytesFrom(url){
    return orig(url).then(function(r){ if(!r.ok) throw new Error('load failed: '+url); return r.text(); })
      .then(function(t){ const s = atob(t.trim()); const b = new Uint8Array(s.length);
        for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i); return b; });
  }
  window.fetch = function(input, init){
    const url = (typeof input === 'string') ? input : (input && input.url) || '';
    if (/index\\.wasm(\\?|$)/.test(url)) {
      return bytesFrom('index.wasm.gz.b64.js').then(function(b){
        const ds = new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'));
        return new Response(ds, {status: 200, headers: {'Content-Type': 'application/wasm'}});
      });
    }
    if (/index\\.pck(\\?|$)/.test(url)) {
      return bytesFrom('index.pck.b64.js').then(function(b){
        return new Response(b, {status: 200, headers: {'Content-Type': 'application/octet-stream'}});
      });
    }
    return orig(input, init);
  };
})();
</script>
"""
p = os.path.join(d, 'index.html')
h = open(p, encoding='utf-8').read()
if 'bytesFrom' not in h:
    h = h.replace('<script src="index.js"></script>', shim + '<script src="index.js"></script>', 1)
h = h.replace('"ensureCrossOriginIsolationHeaders":true', '"ensureCrossOriginIsolationHeaders":false')
open(p, 'w', encoding='utf-8').write(h)
for f in sorted(os.listdir(d)): print(f, os.path.getsize(os.path.join(d, f)))
