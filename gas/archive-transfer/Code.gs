/**
 * 物件リストV2 → 配布完了アーカイブ 移管
 *
 * ステータスが「配布完了」のレコードを配布完了確認シートにコピーする。
 * トリガー設定は Apps Script の「トリガー」から行う。
 *
 * 設定が必要な定数:
 *   SOURCE_SHEET_ID - 物件リストV2 のスプレッドシート ID
 *   SOURCE_SHEET_NAME - ソースのタブ名
 *   TARGET_SHEET_ID - 配布完了確認シート ID
 *   TARGET_SHEET_NAME - 配布完了 タブ名
 */

// TODO: 実際の ID・タブ名に置き換える
const SOURCE_SHEET_ID = 'YOUR_SOURCE_SPREADSHEET_ID';
const SOURCE_SHEET_NAME = '物件リストV2'; // 要確認
const TARGET_SHEET_ID = '1wIE_FrIv4a7QoeMcKROAYesxbMIFmsHwAXFV6k-6h0Y';
const TARGET_SHEET_NAME = '配布完了';

/**
 * メイン処理。トリガーから呼ばれる。
 */
function archiveCompletedDistributions() {
  const source = SpreadsheetApp.openById(SOURCE_SHEET_ID).getSheetByName(SOURCE_SHEET_NAME);
  const target = SpreadsheetApp.openById(TARGET_SHEET_ID).getSheetByName(TARGET_SHEET_NAME);

  if (!source || !target) {
    Logger.log('Error: ソースまたはターゲットのシートが見つかりません');
    return;
  }

  const sourceData = source.getDataRange().getValues();
  const headers = sourceData[0];
  const statusCol = headers.indexOf('ステータス');
  if (statusCol < 0) {
    Logger.log('Error: ステータス列が見つかりません');
    return;
  }

  const rowsToArchive = [];
  for (let i = 1; i < sourceData.length; i++) {
    if (sourceData[i][statusCol] === '配布完了') {
      rowsToArchive.push(sourceData[i]);
    }
  }

  if (rowsToArchive.length === 0) {
    Logger.log('移管対象なし');
    return;
  }

  target.getRange(target.getLastRow() + 1, 1, target.getLastRow() + rowsToArchive.length, headers.length)
    .setValues(rowsToArchive);

  Logger.log(rowsToArchive.length + ' 件をアーカイブに移管しました');
}
