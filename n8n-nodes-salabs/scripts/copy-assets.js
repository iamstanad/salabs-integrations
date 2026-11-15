// Copy icons (and node JSON) next to the compiled files.
const fs = require('fs');
const path = require('path');
function walk(dir) {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    if (fs.statSync(p).isDirectory()) walk(p);
    else if (/\.(svg|png|json)$/.test(f)) {
      const out = path.join('dist', p);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.copyFileSync(p, out);
    }
  }
}
['nodes', 'credentials'].forEach(walk);
