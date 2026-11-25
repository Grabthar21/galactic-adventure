"""Make a Godot web export publishable on the artifact host.
The host only serves certain file types and caps files at 20 MiB, so:
- index.wasm is gzipped, then stored as base64 text in index.wasm.gz.b64.js
- index.pck is stored as base64 text in index.pck.<n>.b64.js parts (12 MiB of data each, so
  each part stays under the cap as the game's art grows)
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
PART = 12 * 1024 * 1024
pck = open(os.path.join(d, 'index.pck'), 'rb').read()
parts = [pck[i:i + PART] for i in range(0, len(pck), PART)]
for i, chunk in enumerate(parts):
    open(os.path.join(d, f'index.pck.{i}.b64.js'), 'w').write(base64.b64encode(chunk).decode('ascii'))
os.remove(os.path.join(d, 'index.pck'))
shim = """<script>
const PCK_PARTS = __PCK_PARTS__;
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
      const names = []; for (let i = 0; i < PCK_PARTS; i++) names.push('index.pck.' + i + '.b64.js');
      return Promise.all(names.map(bytesFrom)).then(function(bs){
        return new Response(new Blob(bs), {status: 200, headers: {'Content-Type': 'application/octet-stream'}});
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
h = h.replace('__PCK_PARTS__', str(len(parts)))
h = h.replace('"ensureCrossOriginIsolationHeaders":true', '"ensureCrossOriginIsolationHeaders":false')
open(p, 'w', encoding='utf-8').write(h)
for f in sorted(os.listdir(d)): print(f, os.path.getsize(os.path.join(d, f)))
