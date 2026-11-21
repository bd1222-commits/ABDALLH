const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

// دالة قراءة وتفسير ملف .env دون الحاجة لمكتبات خارجية
function loadEnv() {
    const envPath = path.join(__dirname, '.env');
    if (fs.existsSync(envPath)) {
        const content = fs.readFileSync(envPath, 'utf8');
        content.split('\n').forEach(line => {
            const trimmed = line.trim();
            if (trimmed && !trimmed.startsWith('#')) {
                const eqIdx = trimmed.indexOf('=');
                if (eqIdx !== -1) {
                    const key = trimmed.slice(0, eqIdx).trim();
                    let val = trimmed.slice(eqIdx + 1).trim();
                    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
                        val = val.slice(1, -1);
                    }
                    process.env[key] = val;
                }
            }
        });
        console.log('✔ تم تحميل متغيرات البيئة من .env بنجاح');
    } else {
        console.log('⚠ لم يتم العثور على ملف .env، سيتم استخدام القيم الافتراضية');
    }
}

loadEnv();

const PORT = parseInt(process.env.PORT, 10) || 3000;

// أنواع الملفات المدعومة (MIME Types)
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.pdf': 'application/pdf'
};

const server = http.createServer((req, res) => {
    const parsedUrl = url.parse(req.url);
    let pathname = decodeURIComponent(parsedUrl.pathname);

    // توجيه المسار الرئيسي إلى index.html
    if (pathname === '/') {
        pathname = '/index.html';
    }

    // نقطة تزويد الإعدادات الحية للواجهة الأمامية
    if (pathname === '/config.js') {
        loadEnv(); // إعادة قراءة .env ديناميكياً لضمان تحديث القيم فوراً
        const configScript = `window.APP_CONFIG = {
    GOOGLE_APPS_SCRIPT_URL: ${JSON.stringify(process.env.GOOGLE_APPS_SCRIPT_URL || '')},
    PDF_DOWNLOAD_URL: ${JSON.stringify(process.env.PDF_DOWNLOAD_URL || '')},
    INSTAGRAM_URL: "https://www.instagram.com/abdullah.aicreator?jplx=MWZxbGx1a2tydXg0cw=="
};`;
        res.writeHead(200, {
            'Content-Type': 'application/javascript; charset=utf-8',
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache'
        });
        return res.end(configScript);
    }

    const filePath = path.join(__dirname, pathname);

    // التأكد من عدم الخروج عن مجلد المشروع (Security check)
    if (!filePath.startsWith(__dirname)) {
        res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
        return res.end('ممنوع الوصول');
    }

    fs.stat(filePath, (err, stats) => {
        if (err || !stats.isFile()) {
            res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
            return res.end('<h1>404 — الصفحة غير موجودة</h1><p><a href="/">العودة للرئيسية</a></p>');
        }

        const ext = path.extname(filePath).toLowerCase();
        const contentType = MIME_TYPES[ext] || 'application/octet-stream';

        res.writeHead(200, { 'Content-Type': contentType });
        const stream = fs.createReadStream(filePath);
        stream.pipe(res);
    });
});

server.on('error', (err) => {
    console.error('❌ حدث خطأ في الخادم:', err.message);
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`\n==================================================`);
    console.log(`🚀 خادم صفحة الهبوط يعمل الآن بنجاح!`);
    console.log(`🔗 الرابط المحلي: http://localhost:${PORT}`);
    console.log(`🔗 أو الرابط المباشر: http://127.0.0.1:${PORT}`);
    console.log(`==================================================\n`);
});
