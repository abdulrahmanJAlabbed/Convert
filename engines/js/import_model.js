// Import/convert any assimp-supported 3D model to glTF2/GLB/OBJ/STL/PLY.
// Usage: node import_model.js <input> <glb2|gltf2|obj|stl|ply> <output>
const fs = require('fs');
const path = require('path');
const assimpjs = require('assimpjs');

const input = process.argv[2];
const outFmt = process.argv[3] || 'glb2';
const outPath = process.argv[4];

if (!input || !outPath) {
  console.error('usage: node import_model.js <input> <glb2|gltf2|obj|stl|ply> <output>');
  process.exit(2);
}

assimpjs().then((ajs) => {
  const fl = new ajs.FileList();
  const dir = path.dirname(input);
  const base = path.basename(input);
  fl.AddFile(base, new Uint8Array(fs.readFileSync(input)));

  // Include sibling texture/material files so materials survive the import.
  try {
    for (const sib of fs.readdirSync(dir)) {
      if (sib === base) continue;
      if (/\.(png|jpe?g|bmp|tga|dds|gif|mtl)$/i.test(sib)) {
        fl.AddFile(sib, new Uint8Array(fs.readFileSync(path.join(dir, sib))));
      }
    }
  } catch (e) { /* ignore */ }

  const result = ajs.ConvertFileList(fl, outFmt);
  if (!result.IsSuccess() || result.FileCount() === 0) {
    console.error('CONVERT_FAILED: ' + result.GetErrorCode());
    process.exit(1);
  }

  const outDir = path.dirname(outPath);
  fs.mkdirSync(outDir, { recursive: true });
  for (let i = 0; i < result.FileCount(); i++) {
    const f = result.GetFile(i);
    const content = Buffer.from(f.GetContent());
    const dest = (result.FileCount() === 1)
      ? outPath
      : path.join(outDir, path.basename(f.GetPath()));
    fs.writeFileSync(dest, content);
    console.log('WROTE ' + dest + ' ' + content.length);
  }
});
