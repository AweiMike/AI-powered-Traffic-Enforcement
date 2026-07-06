# -*- coding: utf-8 -*-
"""
匯入後自動資料健檢（防污染防線）

背景：本系統歷史上發生過「EIS 值域假設錯誤」型態的資料污染
（年齡 -1 表未知被誤判青少年、性別欄出現「無或物(動物、堆置物)」、
派出所名全稱/短名不一、severity 隨匯出時間變化）。解析層已針對這些
已知污染修正，但「未來新型污染」（EIS 改版換欄名、新哨兵值）無法
事先窮舉規則防堵，必須在匯入當下比對「本批 vs 全庫基線」的統計
分布，異常就攔截提醒，而不是等事後看報表才發現。

用法：匯入 commit 之後呼叫 run_batch_health_checks(db, batch_ids)，
batch_ids 可傳單一 batch_id/前綴字串，也可傳本次匯入產生的多個
batch_id（批次/多檔上傳每個檔案各自獨立時間戳，需要收集全部）。
"""

from typing import List, Union

from sqlalchemy import or_

from app.models.core import Crash


def run_batch_health_checks(db, batch_ids: Union[str, List[str]]) -> List[str]:
    """對「本批」匯入資料做五項健檢，回傳繁中警示訊息清單（無異常則為空清單）。

    「本批」：import_batch_id 開頭符合 batch_ids 任一前綴的案件。
    「基線」：全庫排除本批之外的案件。
    本批 0 筆時直接回傳 []（無資料可比對，跳過健檢）。
    """
    if isinstance(batch_ids, str):
        prefixes = [batch_ids]
    else:
        prefixes = list(batch_ids)

    if not prefixes:
        return []

    batch_filter = or_(*[Crash.import_batch_id.like(f"{p}%") for p in prefixes])

    warnings: List[str] = []

    # 撈本批全部案件（欄位不多，匯入是低頻操作，效率不苛求）
    batch_rows = (
        db.query(
            Crash.driver_age_group,
            Crash.driver_gender,
            Crash.sub_unit,
            Crash.severity,
            Crash.latitude,
        )
        .filter(batch_filter)
        .all()
    )

    batch_total = len(batch_rows)
    if batch_total == 0:
        return []

    # 基線（全庫排除本批）
    baseline_rows = (
        db.query(
            Crash.driver_age_group,
            Crash.driver_gender,
            Crash.sub_unit,
            Crash.severity,
        )
        .filter(~batch_filter)
        .all()
    )
    baseline_total = len(baseline_rows)

    # ============================================
    # 規則 1：年齡未知率
    # ============================================
    batch_unknown_age = sum(1 for r in batch_rows if r.driver_age_group == "未知")
    batch_unknown_age_rate = batch_unknown_age / batch_total * 100

    baseline_unknown_age = sum(1 for r in baseline_rows if r.driver_age_group == "未知")
    baseline_unknown_age_rate = (
        baseline_unknown_age / baseline_total * 100 if baseline_total > 0 else 0.0
    )

    if (
        batch_unknown_age_rate > 30
        and (batch_unknown_age_rate - baseline_unknown_age_rate) > 15
    ):
        warnings.append(
            f"⚠️ 本批年齡未知率 {batch_unknown_age_rate:.1f}%"
            f"（全庫基線 {baseline_unknown_age_rate:.1f}%），"
            f"請確認匯出檔含年齡欄位或值域正常（EIS 以 -1 表未知）"
        )

    # ============================================
    # 規則 2：性別值域
    # ============================================
    VALID_GENDERS = {"男", "女"}
    invalid_gender_values = [
        r.driver_gender
        for r in batch_rows
        if r.driver_gender is not None and r.driver_gender not in VALID_GENDERS
    ]
    if len(invalid_gender_values) > 0:
        sample = list(dict.fromkeys(invalid_gender_values))[:3]  # 保序去重取前3個
        warnings.append(
            f"⚠️ 本批性別欄出現 {len(invalid_gender_values)} 筆非男/女值"
            f"（如：{'、'.join(sample)}），解析層可能遇到新值域"
        )

    # ============================================
    # 規則 3：轄區首見值
    # ============================================
    baseline_sub_units = {r.sub_unit for r in baseline_rows if r.sub_unit}
    batch_sub_units = {r.sub_unit for r in batch_rows if r.sub_unit}
    new_sub_units = sorted(batch_sub_units - baseline_sub_units)
    if new_sub_units:
        warnings.append(
            f"⚠️ 本批出現首見轄區單位：{'、'.join(new_sub_units)}——"
            f"若非新設單位，可能是名稱格式變異（全稱/異體字）"
        )

    # ============================================
    # 規則 4：severity 分布（A3 占比異常偏高）
    # ============================================
    batch_a3 = sum(1 for r in batch_rows if r.severity == "A3")
    batch_a3_rate = batch_a3 / batch_total * 100

    baseline_a3 = sum(1 for r in baseline_rows if r.severity == "A3")
    baseline_a3_rate = baseline_a3 / baseline_total * 100 if baseline_total > 0 else 0.0

    if (batch_a3_rate - baseline_a3_rate) > 25:
        warnings.append(
            f"⚠️ 本批 A3 占比 {batch_a3_rate:.1f}%（基線 {baseline_a3_rate:.1f}%），"
            f"疑似缺「事故類別」欄改用死傷推導，A2 可能被低估"
        )

    # ============================================
    # 規則 5：GPS 率（latitude 缺失率）
    # ============================================
    batch_null_gps = sum(1 for r in batch_rows if r.latitude is None)
    batch_null_gps_rate = batch_null_gps / batch_total * 100

    if batch_null_gps_rate > 20:
        warnings.append(
            f"⚠️ 本批 GPS 缺失率 {batch_null_gps_rate:.1f}%，"
            f"地圖與熱點分析將退化為行政區中心點"
        )

    return warnings
