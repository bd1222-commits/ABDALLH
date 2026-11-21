/**
 * كود Google Apps Script لحفظ الإيميلات في Google Sheets
 * 
 * تم ضبط الكود وفق المعايير المطلوبة:
 * 1. استخدام معرّف Google Sheets (ID فقط).
 * 2. عدم الاعتماد على أي اسم تبويب (مثل Sheet1).
 * 3. اختيار ورقة البيانات الأولى تلقائياً عبر: spreadsheet.getSheets()[0]
 * 4. دعم فحص التكرار وحفظ التاريخ والحالة.
 */

// 1. معرّف جدول البيانات الصحيح (ID فقط)
var SPREADSHEET_ID = "1o_x6wBnAyToOyXLzo7YCxQEos7H5MmXWXF9PzpP0C58";

function doGet(e) {
  return handleRequest(e);
}

function doPost(e) {
  return handleRequest(e);
}

function handleRequest(e) {
  try {
    var email = '';

    // قراءة البريد الإلكتروني من الطلب (سواء كان GET أو POST JSON أو Form)
    if (e && e.parameter && e.parameter.email) {
      email = e.parameter.email.trim().toLowerCase();
    }
    
    if (!email && e && e.postData && e.postData.contents) {
      var contents = e.postData.contents;
      try {
        var json = JSON.parse(contents);
        if (json && json.email) {
          email = json.email.trim().toLowerCase();
        }
      } catch (err) {
        var params = contents.split('&');
        for (var i = 0; i < params.length; i++) {
          var pair = params[i].split('=');
          if (decodeURIComponent(pair[0]).trim() === 'email') {
            email = decodeURIComponent(pair[1] || '').trim().toLowerCase();
            break;
          }
        }
      }
    }

    // التحقق من إدخال البريد
    if (!email) {
      return createJsonResponse({
        success: false,
        status: 'error',
        message: 'يرجى إدخال بريد إلكتروني صحيح'
      });
    }

    var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return createJsonResponse({
        success: false,
        status: 'error',
        message: 'صيغة البريد الإلكتروني غير صحيحة'
      });
    }

    // فتح الجدول بالـ ID الصحيح
    var spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);

    // اختيار ورقة البيانات الأولى تلقائياً بدون الاعتماد على أي اسم
    var sheet = spreadsheet.getSheets()[0];
    var data = sheet.getDataRange().getValues();

    // التحقق من عدم تسجيل البريد مسبقاً
    for (var i = 1; i < data.length; i++) {
      if (data[i][0] && data[i][0].toString().toLowerCase().trim() === email) {
        return createJsonResponse({
          success: true,
          status: 'duplicate',
          message: 'هذا البريد مسجّل بالفعل مسبقًا'
        });
      }
    }

    // إضافة صف جديد: البريد، تاريخ التسجيل، الحالة
    var now = new Date();
    var formattedDate = Utilities.formatDate(now, 'Asia/Riyadh', 'yyyy-MM-dd HH:mm:ss');
    sheet.appendRow([email, formattedDate, 'نشط']);

    return createJsonResponse({
      success: true,
      status: 'success',
      message: 'تم حفظ البريد بنجاح في Google Sheets!'
    });

  } catch (error) {
    return createJsonResponse({
      success: false,
      status: 'error',
      message: 'خطأ: ' + error.toString()
    });
  }
}

function createJsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
