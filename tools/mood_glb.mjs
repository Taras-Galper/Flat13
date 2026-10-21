// Compress an exported part of the flat for the web without merging materials: every material keeps its
// name and its atlas (the @S / @L / @R copies differ only by name, which a normal dedup would fold together).
//   node tools/mood_glb.mjs mood/v2/living_raw.glb mood/living.gltf
// .gltf output writes the textures as shared files (tex/<hash>.webp), so the browser fetches a texture used
// by the shell, the living room and the bedrooms only once.  Needs @gltf-transform/core, functions,
// extensions, meshoptimizer and sharp.  SIMPLIFY_ERR=0.0006 by default.
import { NodeIO, PropertyType } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, weld, textureCompress, meshopt, simplify } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder, MeshoptSimplifier } from 'meshoptimizer';
import sharp from 'sharp';
const [src, dst] = process.argv.slice(2);
await MeshoptEncoder.ready; await MeshoptDecoder.ready; await MeshoptSimplifier.ready;
const ERR = Number(process.env.SIMPLIFY_ERR || 0.0006);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(src);
await doc.transform(
  dedup({ propertyTypes: [PropertyType.ACCESSOR, PropertyType.TEXTURE] }),
  prune({ keepAttributes: true, keepExtras: true }),
  weld(),
  // small detail goes first: the lightmap UVs are attribute seams, so islands keep their borders
  simplify({ simplifier: MeshoptSimplifier, ratio: 0.0, error: ERR, lockBorder: false }),
  // surface detail maps at 512, colour at 1024
  textureCompress({ encoder: sharp, targetFormat: 'webp', slots: /^(normal|metallicRoughness|occlusion)/, resize: [512, 512], quality: 80 }),
  textureCompress({ encoder: sharp, targetFormat: 'webp', resize: [1024, 1024], quality: 82 }),
  meshopt({ encoder: MeshoptEncoder, level: 'medium' }),
);
// .gltf output: textures as shared files (tex/<hash>.webp). The shell, the living room and the bedrooms
// use many of the same materials, and the browser then downloads each texture once.
if (dst.endsWith('.gltf')) {
  const fs = await import('fs'), path = await import('path'), { createHash } = await import('crypto');
  const dir = path.dirname(dst), base = path.basename(dst, '.gltf');
  fs.mkdirSync(path.join(dir, 'tex'), { recursive: true });
  doc.getRoot().listBuffers().forEach((b, i) => b.setURI(i ? `${base}_${i}.bin` : `${base}.bin`));
  const { json, resources } = await io.writeJSON(doc);
  for (const im of json.images || []) {
    const data = resources[im.uri]; delete resources[im.uri];
    const ext = (im.mimeType || 'image/webp').split('/')[1];
    const name = `tex/${createHash('sha1').update(data).digest('hex').slice(0, 16)}.${ext}`;
    fs.writeFileSync(path.join(dir, name), data); im.uri = name;
  }
  for (const [uri, data] of Object.entries(resources)) fs.writeFileSync(path.join(dir, uri), data);
  fs.writeFileSync(dst, JSON.stringify(json));
} else {
  await io.write(dst, doc);
}
console.log('written', dst);
