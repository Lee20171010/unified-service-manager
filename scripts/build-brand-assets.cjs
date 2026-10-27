// Packaging-only resizing; the user-selected master remains unchanged.
// Requires Node.js and sharp. Generated assets are checked in for ordinary builds.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const source = path.join(root, 'assets/branding/unified-network-icon-v1.png');
const outputs = [
  ['web/assets/unified-brand.png', 256],
  ['web/assets/favicon.png', 64],
  ['web/assets/apple-touch-icon.png', 180],
  ['android/app/src/main/res/drawable-nodpi/unified_brand.png', 512],
];
(async () => {
  for (const [file, size] of outputs) {
    const target = path.join(root, file);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    await sharp(source).resize(size, size).png().toFile(target);
  }
  console.log('Generated Web and Android assets from the selected v1 master.');
})();
