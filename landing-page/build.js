/**
 * build.js
 * سكربت تجهيز وبناء مشروع صفحة الهبوط للنشر على Netlify
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PROJECT_DIR = __dirname;
const DIST_DIR = path.join(PROJECT_DIR, 'dist');
const ROOT_WORKSPACE_DIR = path.resolve(PROJECT_DIR, '..');
const ROOT_DIST_DIR = path.join(ROOT_WORKSPACE_DIR, 'dist');

console.log('🚀 بدء تجهيز ملفات النشر لـ Netlify...');

// 1. تنظيف وإعادة إنشاء مجلد dist
if (fs.existsSync(DIST_DIR)) {
    fs.rmSync(DIST_DIR, { recursive: true, force: true });
}
fs.mkdirSync(DIST_DIR, { recursive: true });

// 2. نسخ الملفات الأساسية
const filesToCopy = ['index.html', 'success.html', 'config.js'];
filesToCopy.forEach(file => {
    const src = path.join(PROJECT_DIR, file);
    const dest = path.join(DIST_DIR, file);
    if (fs.existsSync(src)) {
        fs.copyFileSync(src, dest);
        console.log(`✔ تم نسخ ${file}`);
    } else {
        console.warn(`⚠ تحذير: لم يتم العثور على ${file}`);
    }
});

// 3. نسخ مجلد assets بالكامل (fonts + images)
function copyDirSync(src, dest) {
    fs.mkdirSync(dest, { recursive: true });
    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (let entry of entries) {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
            copyDirSync(srcPath, destPath);
        } else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

const assetsSrc = path.join(PROJECT_DIR, 'assets');
const assetsDest = path.join(DIST_DIR, 'assets');
if (fs.existsSync(assetsSrc)) {
    copyDirSync(assetsSrc, assetsDest);
    console.log('✔ تم نسخ مجلد assets بالكامل (الخطوط والصور)');
}

// 4. إنشاء ملف _headers لتحسين الأمان وسرعة الكاش على Netlify
const headersContent = `/*
  X-Frame-Options: SAMEORIGIN
  X-Content-Type-Options: nosniff
  X-XSS-Protection: 1; mode=block
  Referrer-Policy: strict-origin-when-cross-origin

/config.js
  Cache-Control: no-cache, no-store, must-revalidate

/assets/*
  Cache-Control: public, max-age=31536000, immutable
`;
fs.writeFileSync(path.join(DIST_DIR, '_headers'), headersContent, 'utf8');
console.log('✔ تم إنشاء ملف _headers');

// 5. إنشاء ملف _redirects لدعم الروابط النظيفة
const redirectsContent = `/success    /success.html    200
`;
fs.writeFileSync(path.join(DIST_DIR, '_redirects'), redirectsContent, 'utf8');
console.log('✔ تم إنشاء ملف _redirects');

// 6. نسخ إلى مجلد dist في مسار العمل الرئيسي لسهولة الوصول
try {
    if (fs.existsSync(ROOT_DIST_DIR)) {
        fs.rmSync(ROOT_DIST_DIR, { recursive: true, force: true });
    }
    copyDirSync(DIST_DIR, ROOT_DIST_DIR);
    console.log(`✔ تم نسخ مجلد dist إلى: ${ROOT_DIST_DIR}`);
} catch (e) {
    console.warn('تنبيه أثناء نسخ مجلد dist الرئيسي:', e.message);
}

// 7. إنشاء ملف مضغوط ZIP جاهز لـ Netlify Drop بمسارات قياسية (Forward Slashes /)
const psScriptFile = path.join(PROJECT_DIR, 'make-zip.ps1');
try {
    const cmd = `powershell.exe -ExecutionPolicy Bypass -File "${psScriptFile}"`;
    execSync(cmd, {
        shell: 'C:\\Windows\\System32\\cmd.exe',
        stdio: 'inherit'
    });
    console.log('✔ تم إنشاء وتحديث الملفات المضغوطة ZIP بنجاح:');
    console.log(`   1) ${path.join(PROJECT_DIR, 'dist.zip')}`);
    console.log(`   2) ${path.join(ROOT_WORKSPACE_DIR, 'dist.zip')}`);
    console.log(`   3) ${path.join(ROOT_WORKSPACE_DIR, 'landing-page-netlify.zip')}`);
} catch (err) {
    console.error('فشل إنشاء الملف المضغوط:', err.message);
}

console.log('\n==================================================');
console.log('🎉 تم تجهيز مجلد النشر dist والملفات المضغوطة بنجاح!');
console.log('==================================================\n');
