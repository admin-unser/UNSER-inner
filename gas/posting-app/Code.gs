// =======================================================
//   ポスティングアプリ統合管理システム (デバッグ強化＆バックオフィス対応版)
// =======================================================

// ▼APIキーは Script Properties で管理することを推奨（リポジトリには commit しない）
// 設定: ファイル → プロジェクトのプロパティ → スクリプト プロパティ → GEMINI_API_KEY
const GEMINI_API_KEY = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY") || "YOUR_API_KEY_HERE";

// ▼画像の保存先フォルダ名
const IMAGE_FOLDER_NAME = "物件リスト_Images";

// -------------------------------------------------------
// 1. OCR処理＆判定ロボ
// -------------------------------------------------------
function processOCR() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("物件リスト");
  if (!sheet) {
    Logger.log("❌ シート「物件リスト」が見つかりません");
    return;
  }

  const modelName = getBestModel();
  if (!modelName) {
    Logger.log("❌ APIキーが無効か、モデルが見つかりません。");
    return;
  }

  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  // 列番号の確認
  const colName = headers.indexOf("物件名");
  const colPhoto = headers.indexOf("配布写真");
  const colJudge = headers.indexOf("AI判定");
  const colOCR = headers.indexOf("OCR結果");
  const colStatus = headers.indexOf("ステータス");
  const colProject = headers.indexOf("案件名");

  if (colName === -1 || colPhoto === -1 || colJudge === -1 || colOCR === -1) {
    Logger.log("❌ 必要な列が見つかりません。列名が正しいか確認してください。");
    return;
  }

  let processCount = 0;

  for (let i = 1; i < data.length; i++) {
    const masterName = data[i][colName];
    const photoPath = data[i][colPhoto];
    const currentJudge = String(data[i][colJudge]);
    const status = String(data[i][colStatus]).trim();

    const projectName = (colProject !== -1) ? data[i][colProject] : "";

    const isTargetStatus = (status === "配布完了");
    const isTargetJudge = (currentJudge === "" || currentJudge === "未着手" || currentJudge.startsWith("AIエラー") || currentJudge === "要確認" || currentJudge === "判定NG");

    const needsProcessing = photoPath && isTargetStatus && isTargetJudge;

    if (needsProcessing) {
      processCount++;
      Logger.log(`🚀 行${i+1}: 処理開始 [${masterName}]`);

      const ocrText = callGeminiVision(photoPath, modelName, projectName);
      const cleanOCR = ocrText.replace(/\n/g, "").replace(/\r/g, "").trim();
      const judgment = compareNames(masterName, cleanOCR);

      if (judgment === "要確認") {
        sheet.getRange(i + 1, colStatus + 1).setValue("差し戻し");
        sheet.getRange(i + 1, colJudge + 1).setValue("判定NG");
        sheet.getRange(i + 1, colOCR + 1).setValue(cleanOCR);
      } else {
        sheet.getRange(i + 1, colJudge + 1).setValue(judgment);
        sheet.getRange(i + 1, colOCR + 1).setValue(cleanOCR);
      }
      Utilities.sleep(1000);
    }
  }

  if (processCount === 0) {
    Logger.log("ℹ️ 処理対象の行はありませんでした。");
  }
}

// -------------------------------------------------------
// 2. 画像読取＆AI連携
// -------------------------------------------------------
function callGeminiVision(imagePath, modelName, subFolderName) {
  try {
    const fileName = imagePath.split("/").pop();
    const folders = DriveApp.getFoldersByName(IMAGE_FOLDER_NAME);
    if (!folders.hasNext()) return "エラー:親フォルダなし";
    const parentFolder = folders.next();

    let targetFolder = parentFolder;

    if (subFolderName) {
      const subFolders = parentFolder.getFoldersByName(subFolderName);
      if (subFolders.hasNext()) {
        targetFolder = subFolders.next();
      }
    }

    let file = null;
    let attempts = 0;
    while (attempts < 3) {
      let files = targetFolder.getFilesByName(fileName);
      if (files.hasNext()) {
        file = files.next();
        break;
      }
      if (targetFolder.getId() !== parentFolder.getId()) {
        files = parentFolder.getFilesByName(fileName);
        if (files.hasNext()) {
          file = files.next();
          break;
        }
      }
      Utilities.sleep(1500);
      attempts++;
    }

    if (!file) return "エラー:画像なし";

    const base64Image = Utilities.base64Encode(file.getBlob().getBytes());
    let apiModelName = modelName.startsWith("models/") ? modelName : "models/" + modelName;

    const url = `https://generativelanguage.googleapis.com/v1beta/${apiModelName}:generateContent?key=${GEMINI_API_KEY}`;
    const promptText = `画像から【建物名（マンション名・看板の文字）】のみを抽出してください。貼り紙の文章や日付は無視してください。読めない場合は「不明」と返してください。`;
    const payload = { "contents": [{ "parts": [ {"text": promptText}, {"inline_data": { "mime_type": file.getMimeType(), "data": base64Image }} ] }] };
    const options = { "method": "post", "contentType": "application/json", "payload": JSON.stringify(payload), "muteHttpExceptions": true };
    const response = UrlFetchApp.fetch(url, options);
    const json = JSON.parse(response.getContentText());

    if (json.error) return "AIエラー: " + json.error.message;
    if (json.candidates && json.candidates[0].content) return json.candidates[0].content.parts[0].text;
    return "読み取り不可";

  } catch (e) { return "システムエラー: " + e.toString(); }
}

// -------------------------------------------------------
// 3. 半年リセット・自動更新ロボ
// -------------------------------------------------------
function autoResetTasks() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("物件リスト");
  if (!sheet) return;
  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  const colStatus = headers.indexOf("ステータス");
  const colDate = headers.indexOf("完了日時");
  const colPhoto = headers.indexOf("配布写真");
  const colJudge = headers.indexOf("AI判定");
  const colOCR = headers.indexOf("OCR結果");
  const colRound = headers.indexOf("周回数");

  if (colStatus === -1 || colDate === -1) return;

  const today = new Date();
  const sixMonthsAgo = new Date();
  sixMonthsAgo.setMonth(today.getMonth() - 6);

  for (let i = 1; i < data.length; i++) {
    const status = data[i][colStatus];
    const dateVal = data[i][colDate];

    if ((status === "配布完了" || status === "OK") && dateVal) {
      const finishDate = new Date(dateVal);
      if (finishDate < sixMonthsAgo) {
        sheet.getRange(i + 1, colStatus + 1).setValue("未着手");
        sheet.getRange(i + 1, colPhoto + 1).setValue("");
        sheet.getRange(i + 1, colJudge + 1).setValue("");
        sheet.getRange(i + 1, colOCR + 1).setValue("");
        sheet.getRange(i + 1, colDate + 1).setValue("");

        if (colRound !== -1) {
          const currentRound = data[i][colRound] || 1;
          sheet.getRange(i + 1, colRound + 1).setValue(currentRound + 1);
        }
      }
    }
  }
}

// -------------------------------------------------------
// 4. 朝刊ロボ（差し戻し連絡）
// -------------------------------------------------------
function sendDailyRemandReport() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("物件リスト");
  if (!sheet) return;
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const colStatus = headers.indexOf("ステータス");
  const colMember = headers.indexOf("担当者");
  const colName = headers.indexOf("物件名");
  const colOCR = headers.indexOf("OCR結果");
  if (colStatus === -1 || colMember === -1) return;
  const mailList = {};
  for (let i = 1; i < data.length; i++) {
    const status = String(data[i][colStatus]).trim();
    const member = data[i][colMember];
    if (status === "差し戻し") {
      if (!mailList[member]) mailList[member] = [];
      mailList[member].push({ name: data[i][colName], ocr: data[i][colOCR] });
    }
  }
  for (const email in mailList) {
    if (!email || !email.includes("@")) continue;
    const tasks = mailList[email];
    let body = "お疲れ様です。\n現在、以下の案件が「差し戻し」となっています。\nアプリから正しい写真を再撮影してください。\n\n----------------------------\n";
    tasks.forEach(t => { body += `■ 物件名: ${t.name}\n   (AI読取: ${t.ocr})\n\n`; });
    body += "----------------------------";
    MailApp.sendEmail(email, "【再提出依頼】差し戻し案件のお知らせ", body);
  }
}

// ★毎日11:30に連絡を送るためのトリガー設定関数
// （※1回だけ手動で実行してください）
function setRemandTrigger1130() {
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === "sendDailyRemandReport") {
      ScriptApp.deleteTrigger(trigger);
    }
  }
  ScriptApp.newTrigger("sendDailyRemandReport").timeBased().atHour(11).nearMinute(30).everyDays(1).create();
}

// -------------------------------------------------------
// ユーティリティ（★OCR判定精度 改善版）
// -------------------------------------------------------
function getBestModel() {
  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}`;
    const response = UrlFetchApp.fetch(url, { "muteHttpExceptions": true });
    const json = JSON.parse(response.getContentText());
    if (!json.models) return null;
    let bestModel = "";
    for (const model of json.models) {
      if (model.name.includes("gemini-1.5-flash") || model.name.includes("gemini-2.0-flash")) {
        bestModel = model.name;
        break;
      }
    }
    if (!bestModel && json.models.length > 0) bestModel = json.models[0].name;
    return bestModel;
  } catch (e) { return null; }
}

function compareNames(master, ocr) {
  if (!ocr || ocr.startsWith("AIエラー") || ocr === "読み取り不可") return "要確認";
  if (!master) return "マスタ空欄";

  // 文字の表記揺れを徹底的に吸収する関数
  const normalize = (str) => {
    let s = String(str).replace(/[\s　]/g, ""); // スペース削除
    // 全角英数字を半角に変換
    s = s.replace(/[Ａ-Ｚａ-ｚ０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));
    s = s.toLowerCase(); // 大文字を小文字に

    // ローマ数字をアラビア数字に変換
    s = s.replace(/ⅰ/g, "1").replace(/ⅱ/g, "2").replace(/ⅲ/g, "3").replace(/ⅳ/g, "4").replace(/ⅴ/g, "5")
         .replace(/ⅵ/g, "6").replace(/ⅶ/g, "7").replace(/ⅷ/g, "8").replace(/ⅸ/g, "9").replace(/ⅹ/g, "10");

    // ハイフンや伸ばし棒の統一
    s = s.replace(/[ー−‐―]/g, "-");

    return s;
  };

  const nMaster = normalize(master);
  const nOCR = normalize(ocr);
  return (nOCR.includes(nMaster) || nMaster.includes(nOCR)) ? "OK" : "要確認";
}

// =======================================================
//   5. 請求書発行ロボット
// =======================================================
const TEMPLATE_SHEET_NAME = "請求書テンプレート";
const ADMIN_EMAILS = "keiri@unser-inc.com,admin@unser-inc.com";
const IS_TEST_MODE = false;
const TEST_SEND_TO = "info@unser-inc.com";

function sendMonthlyInvoices() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetList = ss.getSheetByName("物件リスト");
  const sheetMember = ss.getSheetByName("メンバーマスタ");
  const sheetTemplate = ss.getSheetByName(TEMPLATE_SHEET_NAME);

  if (!sheetList || !sheetMember || !sheetTemplate) return;

  const today = new Date();
  const targetDate = new Date(today);
  targetDate.setMonth(today.getMonth() - 1);

  const targetYear = targetDate.getFullYear();
  const targetMonth = targetDate.getMonth();
  const displayMonth = targetMonth + 1;

  const memberData = sheetMember.getDataRange().getValues();
  const memberHeaders = memberData[0];

  let idxName = memberHeaders.indexOf("氏名");
  if (idxName === -1) idxName = memberHeaders.indexOf("担当者");
  let idxEmail = memberHeaders.indexOf("メールアドレス");
  const idxPrice = memberHeaders.indexOf("単価");

  const members = [];
  for (let i = 1; i < memberData.length; i++) {
    const mName = memberData[i][idxName];
    const mEmail = memberData[i][idxEmail];
    const mPrice = memberData[i][idxPrice];
    if (!mEmail || mEmail === "") continue;
    members.push({ name: mName, email: mEmail, unitPrice: mPrice });
  }

  const listData = sheetList.getDataRange().getValues();
  const headers = listData[0];

  const colStatus = headers.indexOf("ステータス");
  const colMember = headers.indexOf("担当者");
  const colDate = headers.indexOf("終了日時");
  // ★実配付枚数の列を直接参照
  const colActual = headers.indexOf("実配付枚数");

  const invoiceList = {};

  for (let i = 1; i < listData.length; i++) {
    const status = String(listData[i][colStatus]).trim();
    const dateVal = new Date(listData[i][colDate]);
    const email = listData[i][colMember];

    // ★シート上の「実配付枚数」を正しく取得（空欄やエラーなら0）
    let actualCount = 0;
    if (colActual !== -1) {
      actualCount = Number(listData[i][colActual]) || 0;
    }
    if (actualCount < 0) actualCount = 0;

    const isTargetMonth = (dateVal.getMonth() === targetMonth && dateVal.getFullYear() === targetYear);

    if ((status === "配布完了" || status === "OK") && isTargetMonth) {
      if (!invoiceList[email]) invoiceList[email] = { count: 0 };
      invoiceList[email].count += actualCount;
    }
  }

  let grandTotalAmount = 0;
  let adminReportBody = `【${displayMonth}月度 ポスティング報酬支払一覧】\n\n`;

  for (const member of members) {
    const data = invoiceList[member.email];
    if (!data || data.count === 0) continue;

    const totalAmount = data.count * member.unitPrice;
    grandTotalAmount += totalAmount;
    adminReportBody += `・${member.name} 様: ¥${totalAmount.toLocaleString()} (${data.count.toLocaleString()}部)\n`;

    const recipientEmail = IS_TEST_MODE ? TEST_SEND_TO : member.email;
    const tempSheet = sheetTemplate.copyTo(ss);
    tempSheet.setName("請求書_" + member.name);

    replaceText(tempSheet, "{name}", member.name);
    replaceText(tempSheet, "{date}", Utilities.formatDate(today, Session.getScriptTimeZone(), "yyyy/MM/dd"));
    replaceText(tempSheet, "{targetMonth}", displayMonth);
    replaceText(tempSheet, "{count}", data.count.toLocaleString());
    replaceText(tempSheet, "{price}", member.unitPrice.toLocaleString());
    replaceText(tempSheet, "{amount}", "¥" + totalAmount.toLocaleString());

    SpreadsheetApp.flush();

    const pdfBlob = createPDF(ss.getId(), tempSheet.getSheetId());
    pdfBlob.setName(`請求書_${displayMonth}月度_${member.name}様.pdf`);

    const subject = `【請求書】${displayMonth}月度 ポスティング報酬のご案内`;
    const body = `${member.name} 様\n\nお疲れ様です。\n${displayMonth}月度のポスティング報酬請求書をお送りします。\n\n・対象期間: ${targetYear}年${displayMonth}月\n・配布総数: ${data.count.toLocaleString()} 部\n・お振込金額: ¥${totalAmount.toLocaleString()}\n\n添付のPDFをご確認ください。\nよろしくお願いいたします。`;

    MailApp.sendEmail({ to: recipientEmail, subject: subject, body: body, attachments: [pdfBlob] });
    ss.deleteSheet(tempSheet);
    Utilities.sleep(2000);
  }

  if (grandTotalAmount > 0) {
    adminReportBody += `\n----------------------------\n■ 支払総額: ¥${grandTotalAmount.toLocaleString()}\n----------------------------\n`;
    const toAdmin = IS_TEST_MODE ? TEST_SEND_TO : ADMIN_EMAILS;
    MailApp.sendEmail(toAdmin, `【管理者レポート】${displayMonth}月度 支払一覧`, adminReportBody);
  }
}

function replaceText(sheet, findText, replaceText) {
  sheet.getDataRange().createTextFinder(findText).replaceAllWith(String(replaceText));
}

function createPDF(ssId, sheetId) {
  const url = `https://docs.google.com/spreadsheets/d/${ssId}/export?format=pdf&gid=${sheetId}&size=A4&portrait=true&fitw=true&gridlines=false`;
  const token = ScriptApp.getOAuthToken();
  const response = UrlFetchApp.fetch(url, { headers: { 'Authorization': 'Bearer ' + token } });
  return response.getBlob();
}


// =======================================================
//   6. アーカイブロボット（ステータスごとにタブ分割）
//   ※AppSheet等の連携変更準備が整ってから手動で実行してください
// =======================================================
function archiveDataByStatus() {
  const mainSS = SpreadsheetApp.getActiveSpreadsheet();
  const mainSheet = mainSS.getSheetByName("物件リスト");

  // ▼アーカイブ先スプレッドシートID
  const archiveSSId = "1wIE_FrIv4a7QoeMcKROAYesxbMIFmsHwAXFV6k-6h0Y";
  const archiveSS = SpreadsheetApp.openById(archiveSSId);

  const data = mainSheet.getDataRange().getValues();
  if (data.length <= 1) return;
  const headers = data[0];

  const statusIdx = headers.indexOf("ステータス");

  if (statusIdx === -1) {
    Logger.log("❌ ステータス列が見つかりません");
    return;
  }

  let rowsCompleted = [];
  let rowsProhibited = [];
  let rowsToKeep = [headers]; // 元シートに残すデータ

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const status = String(row[statusIdx]).trim();

    // ステータスに応じて振り分け
    if (status === "配布完了" || status === "OK") {
      rowsCompleted.push(row);
    } else if (status === "投函禁止") {
      rowsProhibited.push(row);
    } else {
      rowsToKeep.push(row); // 未着手などはそのまま残す
    }
  }

  // ヘルパー関数：指定したシートにデータを追記する
  function appendToSheet(sheetName, appendData) {
    if (appendData.length === 0) return;
    let targetSheet = archiveSS.getSheetByName(sheetName);
    // もしタブが存在しなければ新規作成する
    if (!targetSheet) {
      targetSheet = archiveSS.insertSheet(sheetName);
      targetSheet.appendRow(headers); // ヘッダーをセット
    }
    const startRow = targetSheet.getLastRow() + 1;
    targetSheet.getRange(startRow, 1, startRow + appendData.length - 1, appendData[0].length).setValues(appendData);
  }

  // 1. アーカイブ先にそれぞれ書き出し
  if (rowsCompleted.length > 0) appendToSheet("配布完了", rowsCompleted);
  if (rowsProhibited.length > 0) appendToSheet("投函禁止", rowsProhibited);

  // 2. 元のシートを上書きして軽くする
  // ★準備が整うまではここをコメントアウトしてテストすることをお勧めします
  mainSheet.clearContents();
  mainSheet.getRange(1, 1, rowsToKeep.length, headers.length).setValues(rowsToKeep);

  Logger.log(`✅ アーカイブ完了: 配布完了[${rowsCompleted.length}件], 投函禁止[${rowsProhibited.length}件]`);
}
