/**
 * build.js
 * سكربت تجهيز وبناء مشروع صفحة الهبوط للنشر على Vercel و Netlify
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PROJECT_DIR = __dirname;
const DIST_DIR = path.join(PROJECT_DIR, 'dist');
const PUBLIC_DIR = path.join(PROJECT_DIR, 'public');
const ROOT_WORKSPACE_DIR = path.resolve(PROJECT_DIR, '..');
const ROOT_DIST_DIR = path.join(ROOT_WORKSPACE_DIR, 'dist');
const ROOT_PUBLIC_DIR = path.join(ROOT_WORKSPACE_DIR, 'public');

console.log('🚀 بدء تجهيز ملفات النشر لـ Vercel و Netlify...');

// دالة مساعدة لنسخ المجلدات بشكل تكراري متوافق
function copyDirSync(src, dest) {
    if (!fs.existsSync(src)) return;
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

// دالة لتجهيز أي مجلد إخراج (dist أو public)
function prepareOutputDirectory(targetDir, dirName) {
    if (fs.existsSync(targetDir)) {
        fs.rmSync(targetDir, { recursive: true, force: true });
    }
    fs.mkdirSync(targetDir, { recursive: true });

    // نسخ الملفات الأساسية
    const filesToCopy = ['index.html', 'success.html', 'config.js'];
    filesToCopy.forEach(file => {
        const src = path.join(PROJECT_DIR, file);
        const dest = path.join(targetDir, file);
        if (fs.existsSync(src)) {
            fs.copyFileSync(src, dest);
        }
    });

    // نسخ مجلد assets
    const assetsSrc = path.join(PROJECT_DIR, 'assets');
    const assetsDest = path.join(targetDir, 'assets');
    if (fs.existsSync(assetsSrc)) {
        copyDirSync(assetsSrc, assetsDest);
    }

    // إعدادات Netlify (_headers و _redirects)
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
    fs.writeFileSync(path.join(targetDir, '_headers'), headersContent, 'utf8');

    const redirectsContent = `/success    /success.html    200
`;
    fs.writeFileSync(path.join(targetDir, '_redirects'), redirectsContent, 'utf8');

    // ملف vercel.json
    const vercelConfig = {
        cleanUrls: true,
        headers: [
            {
                source: "/config.js",
                headers: [
                    { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }
                ]
            },
            {
                source: "/assets/(.*)",
                headers: [
                    { key: "Cache-Control", value: "public, max-age=31536000, immutable" }
                ]
            }
        ]
    };
    fs.writeFileSync(path.join(targetDir, 'vercel.json'), JSON.stringify(vercelConfig, null, 2), 'utf8');

    // ملف netlify.toml
    const netlifyTomlSrc = path.join(PROJECT_DIR, 'netlify.toml');
    if (fs.existsSync(netlifyTomlSrc)) {
        fs.copyFileSync(netlifyTomlSrc, path.join(targetDir, 'netlify.toml'));
    }

    console.log(`✔ تم تجهيز مجلد ${dirName} بنجاح بكافة ملفات النشر.`);
}

// 1. تجهيز مجلد dist (لمنصة Netlify وأدوات البناء العامة)
prepareOutputDirectory(DIST_DIR, 'dist');

// 2. تجهيز مجلد public (لمنصة Vercel التي تبحث افتراضياً عن public)
prepareOutputDirectory(PUBLIC_DIR, 'public');

// 3. نسخ المخرجات لمسار الجذر لتسهيل الوصول المباشر
try {
    copyDirSync(DIST_DIR, ROOT_DIST_DIR);
    copyDirSync(PUBLIC_DIR, ROOT_PUBLIC_DIR);
} catch (e) {
    // تجاهل إن كان المسار غير متاح
}

// 4. إنشاء ملفات ZIP مضغوطة فقط على بيئة Windows (للاستخدام مع Netlify Drop المحلي)
if (process.platform === 'win32') {
    const psScriptFile = path.join(PROJECT_DIR, 'make-zip.ps1');
    if (fs.existsSync(psScriptFile)) {
        try {
            const cmd = `powershell.exe -ExecutionPolicy Bypass -File "${psScriptFile}"`;
            execSync(cmd, {
                shell: 'C:\\Windows\\System32\\cmd.exe',
                stdio: 'ignore'
            });
            console.log('✔ تم تحديث الملفات المضغوطة ZIP محلياً.');
        } catch (err) {
            // تجاهل خطأ الضغط في حال تعذره، فالمجلدات هي الأهم
        }
    }
}

console.log('\n==================================================');
console.log('🎉 اكتمل البناء بنجاح! مجلد public جاهز لـ Vercel ومجلد dist جاهز لـ Netlify.');
console.log('==================================================\n');
